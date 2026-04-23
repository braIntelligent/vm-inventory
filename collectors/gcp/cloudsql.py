"""
collectors/gcp/cloudsql.py
Collector de instancias Cloud SQL — hereda de BaseCollector.
Usa la API REST via googleapiclient ya que no hay SDK dedicado liviano.
"""

import logging
import re

import google.auth
import google.auth.transport.requests
from googleapiclient import discovery

from core.base_collector import BaseCollector
from core.models import Resource

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "RUNNABLE":       "ENCENDIDA",
    "STOPPED":        "APAGADA",
    "SUSPENDED":      "SUSPENDIDA",
    "PENDING_DELETE": "ELIMINANDO",
    "PENDING_CREATE": "CREANDO",
    "MAINTENANCE":    "MANTENIMIENTO",
    "FAILED":         "ERROR",
    "UNKNOWN_STATE":  "DESCONOCIDO",
}

# activationPolicy determina si realmente esta encendida o apagada
# RUNNABLE + NEVER = instancia apagada manualmente
ACTIVATION_POLICY_MAP = {
    "ALWAYS": None,       # respetar STATUS_MAP
    "NEVER":  "APAGADA",  # configurada para no arrancar
    "ON_DEMAND": None,    # respetar STATUS_MAP
}

DATABASE_VERSION_MAP = {
    "MYSQL_8_0":        "MySQL 8.0",
    "MYSQL_8_0_31":     "MySQL 8.0.31",
    "MYSQL_5_7":        "MySQL 5.7",
    "MYSQL_5_6":        "MySQL 5.6",
    "POSTGRES_15":      "PostgreSQL 15",
    "POSTGRES_14":      "PostgreSQL 14",
    "POSTGRES_13":      "PostgreSQL 13",
    "POSTGRES_12":      "PostgreSQL 12",
    "POSTGRES_11":      "PostgreSQL 11",
    "SQLSERVER_2022_STANDARD":   "SQL Server 2022 Standard",
    "SQLSERVER_2022_ENTERPRISE": "SQL Server 2022 Enterprise",
    "SQLSERVER_2022_EXPRESS":    "SQL Server 2022 Express",
    "SQLSERVER_2022_WEB":        "SQL Server 2022 Web",
    "SQLSERVER_2019_STANDARD":   "SQL Server 2019 Standard",
    "SQLSERVER_2019_ENTERPRISE": "SQL Server 2019 Enterprise",
    "SQLSERVER_2017_STANDARD":   "SQL Server 2017 Standard",
    "SQLSERVER_2017_ENTERPRISE": "SQL Server 2017 Enterprise",
}


class CloudSQLCollector(BaseCollector):

    resource_type = "CLOUD SQL"

    def __init__(self, credentials):
        super().__init__(credentials)
        # refrescar token si es necesario
        request = google.auth.transport.requests.Request()
        if hasattr(credentials, 'refresh'):
            credentials.refresh(request)
        self.service = discovery.build(
            "sqladmin", "v1beta4",
            credentials=credentials,
            cache_discovery=False
        )

    def _get_db_version(self, raw: str) -> str:
        return DATABASE_VERSION_MAP.get(raw, raw.replace("_", " ").title())

    def _get_engine(self, raw: str) -> str:
        raw = raw.upper()
        if "MYSQL"     in raw: return "MYSQL"
        if "POSTGRES"  in raw: return "POSTGRESQL"
        if "SQLSERVER" in raw: return "SQL SERVER"
        return raw

    def _get_ip(self, instance: dict, ip_type: str) -> str:
        for ip in instance.get("ipAddresses", []):
            if ip.get("type") == ip_type:
                return ip.get("ipAddress", "")
        return ""

    def _get_ha(self, instance: dict) -> str:
        availability = instance.get("settings", {}).get("availabilityType", "")
        return "SI" if availability == "REGIONAL" else "NO"

    def _get_backup(self, instance: dict) -> str:
        backup_cfg = instance.get("settings", {}).get("backupConfiguration", {})
        return "SI" if backup_cfg.get("enabled") else "NO"

    def _parse_tier(self, tier: str) -> tuple:
        """Extrae (vcpus, ram_gb) del tier de Cloud SQL."""
        t = tier.upper()

        # db-custom-{vcpus}-{memory_mb}
        m = re.match(r"DB-CUSTOM-(\d+)-(\d+)", t)
        if m:
            return int(m.group(1)), round(int(m.group(2)) / 1024, 1)

        # db-n1-standard-{n}: 3.75 GB RAM por vCPU
        m = re.match(r"DB-N1-STANDARD-(\d+)", t)
        if m:
            n = int(m.group(1))
            return n, round(n * 3.75, 1)

        # db-n1-highmem-{n}: 6.5 GB RAM por vCPU
        m = re.match(r"DB-N1-HIGHMEM-(\d+)", t)
        if m:
            n = int(m.group(1))
            return n, round(n * 6.5, 1)

        # db-perf-optimized-N-{vcpus} (generacion actual)
        m = re.match(r"DB-PERF-OPTIMIZED-N-(\d+)", t)
        if m:
            n = int(m.group(1))
            return n, round(n * 3.75, 1)

        # instancias compartidas
        if t == "DB-F1-MICRO":  return 1, 0.6
        if t == "DB-G1-SMALL":  return 1, 1.7

        return 0, 0.0

    def _get_disk_info(self, instance: dict) -> tuple:
        settings  = instance.get("settings", {})
        disco_gb  = int(settings.get("dataDiskSizeGb", 0))
        tipo_disk = settings.get("dataDiskType", "")
        tipo_disk = "SSD" if "SSD" in tipo_disk.upper() else "HDD"
        return disco_gb, tipo_disk

    def collect(self, project: str) -> list[Resource]:
        logger.debug(f"[CloudSQL] ── {project} ──────────────")
        resources = []
        errores   = 0

        try:
            result    = self.service.instances().list(project=project).execute()
            instances = result.get("items", [])

            if not instances:
                logger.debug(f"  └─ Sin instancias Cloud SQL")
                return []

            logger.debug(f"  ├─ {len(instances)} instancias encontradas")

            for inst in instances:
                try:
                    settings    = inst.get("settings", {})
                    tier        = settings.get("tier", "")
                    db_version  = inst.get("databaseVersion", "")
                    region      = inst.get("region", "").upper()
                    zone        = inst.get("gceZone", "").upper()
                    disco_gb, tipo_disco = self._get_disk_info(inst)
                    vcpus, ram_gb = self._parse_tier(tier)

                    raw_state  = inst.get("state", "UNKNOWN_STATE")
                    activation = settings.get("activationPolicy", "ALWAYS")
                    # si activationPolicy es NEVER, la instancia esta apagada
                    # independiente del estado que reporte la API
                    override   = ACTIVATION_POLICY_MAP.get(activation)
                    status     = override if override else STATUS_MAP.get(raw_state, raw_state)

                    ip_privada = self._get_ip(inst, "PRIVATE")
                    ip_publica = self._get_ip(inst, "PRIMARY")

                    r = Resource(
                        nombre               = inst.get("name", "").upper(),
                        estado               = status,
                        tipo_recurso         = self.resource_type,
                        fuente               = "GCP",
                        proyecto             = project.upper(),
                        region               = region,
                        zona                 = zone,
                        vcpus                = vcpus,
                        ram_gb               = ram_gb,
                        disco_gb             = disco_gb,
                        tipo_disco           = tipo_disco,
                        sistema_operativo    = self._get_db_version(db_version),
                        ip_interna           = ip_privada,
                        ip_externa           = ip_publica,
                        fecha_creacion       = self._parse_date(inst.get("createTime", "")),
                        ultima_actualizacion = self.now,
                        metadata             = {
                            "motor":              self._get_engine(db_version),
                            "version":            self._get_db_version(db_version),
                            "tier":               tier.upper(),
                            "alta_disponibilidad": self._get_ha(inst),
                            "backup_automatico":  self._get_backup(inst),
                            "ip_publica":         "SI" if ip_publica else "NO",
                            "ip_privada":         ip_privada,
                            "ventana_backup":     inst.get("settings", {})
                                                     .get("backupConfiguration", {})
                                                     .get("startTime", ""),
                            "replica_lectura":    "SI" if inst.get("instanceType") == "READ_REPLICA_INSTANCE" else "NO",
                        }
                    )
                    resources.append(r)

                except Exception as e:
                    errores += 1
                    logger.debug(f"  │  Error en instancia {inst.get('name')}: {e}")

            if errores:
                logger.debug(f"  ├─ Con errores: {errores}")
            logger.debug(f"  └─ Total      : {len(resources)}")

        except Exception as e:
            logger.debug(f"  API no habilitada o sin acceso — Cloud SQL en {project}: {e}")

        return resources
