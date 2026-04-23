"""
collectors/gcp/compute.py
Collector de VMs GCP.
"""

import logging
import re

from google.cloud import compute_v1

from core.base_collector import BaseCollector
from core.models import Resource

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "RUNNING":    "ENCENDIDA",
    "TERMINATED": "APAGADA",
    "STAGING":    "INICIANDO",
    "SUSPENDED":  "SUSPENDIDA",
    "STOPPING":   "APAGANDO",
    "REPAIRING":  "EN REPARACION",
}


class GCPComputeCollector(BaseCollector):

    resource_type = "VIRTUAL MACHINE"

    def __init__(self, credentials):
        super().__init__(credentials)
        self.instances_client = compute_v1.InstancesClient(credentials=credentials)
        self.mt_client        = compute_v1.MachineTypesClient(credentials=credentials)
        self.disks_client     = compute_v1.DisksClient(credentials=credentials)
        self.policies_client  = compute_v1.ResourcePoliciesClient(credentials=credentials)

    def _parse_os(self, disks: list) -> str:
        for disk in disks:
            for lic in disk.get("licenses", []):
                key = self._parse_last(lic)
                if not key:
                    continue
                key = re.sub(r"-v\d{8}$", "", key)
                return key.upper()
        return "DESCONOCIDO"

    def _parse_machine_type(self, machine_type_url: str, project: str, zone: str) -> tuple:
        mt_name = self._parse_last(machine_type_url)
        try:
            mt = self.mt_client.get(project=project, zone=zone, machine_type=mt_name)
            return mt.guest_cpus, round(mt.memory_mb / 1024, 1)
        except Exception:
            match = re.search(r"custom-(\d+)-(\d+)", mt_name)
            if match:
                return int(match.group(1)), round(int(match.group(2)) / 1024, 1)
            match = re.search(r"custom-(?:medium|small)-(\d+)", mt_name)
            if match:
                return 1, round(int(match.group(1)) / 1024, 1)
            return 0, 0.0

    def _parse_disk_type(self, inst_disks, project: str, zone: str) -> str:
        for disk in inst_disks:
            if disk.boot and disk.source:
                disk_name = self._parse_last(disk.source)
                try:
                    d = self.disks_client.get(project=project, zone=zone, disk=disk_name)
                    dtype = self._parse_last(d.type_)
                    return dtype.upper() if dtype else "DESCONOCIDO"
                except Exception:
                    pass
        return "DESCONOCIDO"

    def _parse_ip_external(self, network_interfaces: list) -> str:
        for iface in network_interfaces:
            for ac in iface.get("accessConfigs", []):
                nat_ip = ac.get("natIP", "")
                if nat_ip:
                    return nat_ip
        return ""

    def _parse_disk_total(self, disks: list) -> int:
        return sum(int(d.get("diskSizeGb", 0)) for d in disks)

    def _get_schedule(self, project: str, region: str, policy_url: str) -> str:
        policy_name = self._parse_last(policy_url)
        try:
            rp_region = policy_url.split("/regions/")[1].split("/")[0]
        except (IndexError, AttributeError):
            rp_region = region.lower()
        try:
            policy = self.policies_client.get(
                project=project, region=rp_region, resource_policy=policy_name
            )
            sched = policy.instance_schedule_policy
            if not sched:
                return policy_name.upper()
            tz     = sched.time_zone or "UTC"
            inicio = self._cron_to_time(sched.vm_start_schedule.schedule if sched.vm_start_schedule else "")
            fin    = self._cron_to_time(sched.vm_stop_schedule.schedule  if sched.vm_stop_schedule  else "")
            parts  = []
            if inicio: parts.append(f"INICIO: {inicio}")
            if fin:    parts.append(f"FIN: {fin}")
            return " | ".join(parts) + f" ({tz})" if parts else policy_name.upper()
        except Exception as e:
            logger.debug(f"No se pudo obtener schedule {policy_name}: {e}")
            return policy_name.upper()

    def _cron_to_time(self, cron_expr: str) -> str:
        if not cron_expr:
            return ""
        try:
            parts = cron_expr.strip().split()
            return f"{parts[1].zfill(2)}:{parts[0].zfill(2)}"
        except Exception:
            return cron_expr

    def collect(self, project: str) -> list[Resource]:
        resources  = []
        try:
            agg_result = self.instances_client.aggregated_list(project=project)
            for zone_path, zone_data in agg_result:
                instances = getattr(zone_data, "instances", [])
                if not instances:
                    continue
                zone_name = zone_path.replace("zones/", "").upper()
                region    = self._parse_region(zone_name)
                zone_key  = zone_path.replace("zones/", "")

                for inst in instances:
                    try:
                        iface0 = inst.network_interfaces[0] if inst.network_interfaces else None
                        vcpus, ram_gb = self._parse_machine_type(inst.machine_type, project, zone_key)
                        disks = [{"diskSizeGb": str(d.disk_size_gb), "licenses": list(d.licenses)} for d in inst.disks]
                        network_interfaces = [{"networkIP": i.network_i_p, "accessConfigs": [{"natIP": ac.nat_i_p} for ac in i.access_configs]} for i in inst.network_interfaces]
                        raw_policies = list(inst.resource_policies)
                        schedule     = self._get_schedule(project, region.lower(), raw_policies[0]) if raw_policies else ""
                        estado       = STATUS_MAP.get(inst.status, inst.status)

                        resources.append(Resource(
                            nombre               = inst.name.upper(),
                            estado               = estado,
                            tipo_recurso         = self.resource_type,
                            fuente               = "GCP",
                            proyecto             = project.upper(),
                            region               = region,
                            zona                 = zone_name,
                            vpc                  = self._parse_last(iface0.network).upper()    if iface0 else "",
                            subred               = self._parse_last(iface0.subnetwork).upper() if iface0 else "",
                            tipo_maquina         = self._parse_last(inst.machine_type).upper(),
                            vcpus                = vcpus,
                            ram_gb               = ram_gb,
                            disco_gb             = self._parse_disk_total(disks),
                            tipo_disco           = self._parse_disk_type(inst.disks, project, zone_key),
                            sistema_operativo    = self._parse_os(disks),
                            ip_interna           = iface0.network_i_p if iface0 else "",
                            ip_externa           = self._parse_ip_external(network_interfaces),
                            fecha_creacion       = self._parse_date(inst.creation_timestamp),
                            ultimo_encendido     = self._parse_date(inst.last_start_timestamp),
                            ultimo_apagado       = self._parse_date(inst.last_stop_timestamp),
                            programa_encendido   = schedule,
                            ultima_actualizacion = self.now,
                        ))
                    except Exception as e:
                        logger.debug(f"Error en instancia {inst.name}: {e}")
        except Exception as e:
            logger.debug(f"Error escaneando compute en {project}: {e}")
        return resources
