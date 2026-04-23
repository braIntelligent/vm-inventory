"""
collectors/gcp/cloudrun.py
Collector de servicios Cloud Run — hereda de BaseCollector.
Usa la API REST via googleapiclient (Cloud Run Admin API v1).
"""

import logging

from googleapiclient import discovery

from core.base_collector import BaseCollector
from core.models import Resource

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "True":    "ACTIVO",
    "False":   "ERROR",
    "Unknown": "DESPLEGANDO",
}


class CloudRunCollector(BaseCollector):

    resource_type = "CLOUD RUN"

    def __init__(self, credentials):
        super().__init__(credentials)
        self.service = discovery.build(
            "run", "v1",
            credentials=credentials,
            cache_discovery=False,
        )

    def _parse_status(self, conditions: list) -> str:
        for cond in conditions:
            if cond.get("type") == "Ready":
                return STATUS_MAP.get(cond.get("status", ""), "DESCONOCIDO")
        return "DESCONOCIDO"

    def _parse_cpu(self, cpu_str: str) -> float:
        if not cpu_str:
            return 0.0
        cpu_str = cpu_str.strip()
        if cpu_str.endswith("m"):
            return round(int(cpu_str[:-1]) / 1000, 2)
        try:
            return float(cpu_str)
        except ValueError:
            return 0.0

    def _parse_memory(self, mem_str: str) -> float:
        if not mem_str:
            return 0.0
        mem_str = mem_str.strip()
        if mem_str.endswith("Gi"):
            return round(float(mem_str[:-2]), 1)
        if mem_str.endswith("Mi"):
            return round(float(mem_str[:-2]) / 1024, 2)
        if mem_str.endswith("G"):
            return round(float(mem_str[:-1]), 1)
        if mem_str.endswith("M"):
            return round(float(mem_str[:-1]) / 1024, 2)
        return 0.0

    def collect(self, project: str) -> list[Resource]:
        logger.debug(f"[CloudRun] ── {project} ──────────────")
        resources = []
        errores   = 0

        try:
            result = (
                self.service
                .projects()
                .locations()
                .services()
                .list(parent=f"projects/{project}/locations/-")
                .execute()
            )
            items = result.get("items", [])

            if not items:
                logger.debug("  └─ Sin servicios Cloud Run")
                return []

            logger.debug(f"  ├─ {len(items)} servicios encontrados")

            for item in items:
                try:
                    metadata   = item.get("metadata", {})
                    spec       = item.get("spec", {})
                    status     = item.get("status", {})
                    labels     = metadata.get("labels", {})
                    annotations = metadata.get("annotations", {})

                    # nombre: ultimo segmento del nombre completo
                    nombre  = metadata.get("name", "").split("/")[-1].upper()
                    region  = labels.get("cloud.googleapis.com/location", "").upper()

                    # estado via condicion Ready
                    conditions = status.get("conditions", [])
                    estado     = self._parse_status(conditions)

                    # recursos del primer contenedor
                    containers = spec.get("template", {}).get("spec", {}).get("containers", [{}])
                    container  = containers[0] if containers else {}
                    limits     = container.get("resources", {}).get("limits", {})
                    cpu        = self._parse_cpu(limits.get("cpu", ""))
                    memory_gb  = self._parse_memory(limits.get("memory", ""))

                    # anotaciones de escalado
                    tmpl_annotations = spec.get("template", {}).get("metadata", {}).get("annotations", {})
                    min_inst = tmpl_annotations.get("autoscaling.knative.dev/minScale", "0")
                    max_inst = tmpl_annotations.get("autoscaling.knative.dev/maxScale", "")
                    ingress  = annotations.get("run.googleapis.com/ingress", "")

                    concurrencia    = spec.get("template", {}).get("spec", {}).get("containerConcurrency", "")
                    ultima_revision = status.get("latestCreatedRevisionName", "")
                    url             = status.get("url", "")

                    resources.append(Resource(
                        nombre               = nombre,
                        estado               = estado,
                        tipo_recurso         = self.resource_type,
                        fuente               = "GCP",
                        proyecto             = project.upper(),
                        region               = region,
                        ip_externa           = url,
                        vcpus                = cpu,
                        ram_gb               = memory_gb,
                        fecha_creacion       = self._parse_date(metadata.get("creationTimestamp", "")),
                        ultima_actualizacion = self.now,
                        metadata             = {
                            "min_instancias":  str(min_inst),
                            "max_instancias":  str(max_inst) if max_inst else "SIN LIMITE",
                            "concurrencia":    str(concurrencia) if concurrencia else "",
                            "ingress":         ingress.upper() if ingress else "",
                            "ultima_revision": ultima_revision,
                        },
                    ))

                except Exception as e:
                    errores += 1
                    logger.debug(f"  │  Error en servicio {item.get('metadata', {}).get('name', '')}: {e}")

            if errores:
                logger.debug(f"  ├─ Con errores: {errores}")
            logger.debug(f"  └─ Total      : {len(resources)}")

        except Exception as e:
            logger.debug(f"  API no habilitada o sin acceso — Cloud Run en {project}: {e}")

        return resources
