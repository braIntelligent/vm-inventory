"""
collectors/gcp/apis.py
Collector de APIs/servicios habilitados por proyecto.
"""

import logging

import google.auth.transport.requests
from googleapiclient import discovery

from core.base_collector import BaseCollector
from core.models import Resource

logger = logging.getLogger(__name__)

RELEVANT_PREFIXES = [
    "compute.", "container.", "sqladmin.", "storage-api.", "storage.",
    "bigquery.", "run.", "cloudfunctions.", "cloudkms.", "secretmanager.",
    "servicenetworking.", "vpcaccess.", "dns.", "monitoring.", "logging.",
    "cloudbuild.", "artifactregistry.", "iam.", "cloudresourcemanager.",
    "cloudscheduler.", "pubsub.", "dataflow.", "dataproc.", "redis.",
    "memcache.", "spanner.", "firestore.", "bigtable.", "notebooks.",
    "aiplatform.", "ml.", "translate.", "vision.", "speech.", "language.",
    "networkmanagement.", "networksecurity.", "gkehub.", "anthos.",
]


class APIsCollector(BaseCollector):

    resource_type = "API HABILITADA"

    def __init__(self, credentials):
        super().__init__(credentials)
        request = google.auth.transport.requests.Request()
        if hasattr(credentials, 'refresh'):
            credentials.refresh(request)
        self.service = discovery.build(
            "serviceusage", "v1",
            credentials=credentials,
            cache_discovery=False
        )

    def _is_relevant(self, service_name: str) -> bool:
        api_id = service_name.split("/")[-1]
        return any(api_id.startswith(p) for p in RELEVANT_PREFIXES)

    def collect(self, project: str) -> list[Resource]:
        resources = []
        try:
            request      = self.service.services().list(parent=f"projects/{project}", filter="state:ENABLED", pageSize=200)
            all_services = []
            while request:
                response     = request.execute()
                all_services.extend(response.get("services", []))
                request      = self.service.services().list_next(request, response)

            for svc in all_services:
                if not self._is_relevant(svc.get("name", "")):
                    continue
                try:
                    api_id = svc.get("name", "").split("/")[-1]
                    title  = svc.get("config", {}).get("title", api_id)
                    resources.append(Resource(
                        nombre               = api_id.upper(),
                        estado               = "HABILITADA",
                        tipo_recurso         = self.resource_type,
                        fuente               = "GCP",
                        proyecto             = project.upper(),
                        ultima_actualizacion = self.now,
                        metadata             = {
                            "api_id":         api_id,
                            "nombre_legible": title,
                            "estado":         "HABILITADA",
                        }
                    ))
                except Exception as e:
                    logger.debug(f"Error en API {svc.get('name')}: {e}")
        except Exception as e:
            logger.debug(f"APIs no disponibles en {project}: {str(e).splitlines()[0]}")
        return resources
