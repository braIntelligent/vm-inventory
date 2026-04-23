"""
collectors/gcp/storage.py
Collector de buckets Cloud Storage — hereda de BaseCollector.
"""

import logging

from google.cloud import storage

from core.base_collector import BaseCollector
from core.models import Resource

logger = logging.getLogger(__name__)


class CloudStorageCollector(BaseCollector):

    resource_type = "CLOUD STORAGE"

    def __init__(self, credentials, default_project: str = None):
        super().__init__(credentials)
        # storage.Client requiere un proyecto — se usa solo para inicializar
        # el proyecto real se pasa en cada llamada a list_buckets()
        self.client = storage.Client(
            credentials=credentials,
            project=default_project or "placeholder"
        )

    def _get_public_access(self, bucket) -> str:
        """
        Determina acceso publico.
        - enforced         -> PRIVADO
        - get_iam_policy() -> PUBLICO si allUsers/allAuthenticatedUsers
        - sin permisos     -> REVISAR (cuando se tengan permisos, se resolvera automaticamente)
        """
        try:
            iam = bucket.iam_configuration
            if getattr(iam, "public_access_prevention", "").lower() == "enforced":
                return "PRIVADO"
            policy = bucket.get_iam_policy()
            for binding in policy.bindings:
                if "allUsers" in binding.get("members", []) or                    "allAuthenticatedUsers" in binding.get("members", []):
                    return "PUBLICO"
            return "PRIVADO"
        except Exception:
            return "REVISAR"

    def _get_versioning(self, bucket) -> str:
        try:
            return "SI" if bucket.versioning_enabled else "NO"
        except Exception:
            return "NO"

    def _get_retention(self, bucket) -> str:
        try:
            if bucket.retention_period:
                days = bucket.retention_period // 86400
                return f"{days} dias"
        except Exception:
            pass
        return ""

    def _get_lifecycle(self, bucket) -> str:
        try:
            rules = list(bucket.lifecycle_rules)
            return "SI" if rules else "NO"
        except Exception:
            return "NO"

    def _get_encryption(self, bucket) -> str:
        try:
            if bucket.default_kms_key_name:
                return "CUSTOMER-MANAGED (CMEK)"
            return "GOOGLE-MANAGED"
        except Exception:
            return "GOOGLE-MANAGED"

    def collect(self, project: str) -> list[Resource]:
        logger.debug(f"[Storage] ── {project} ──────────────")
        resources = []
        errores   = 0

        try:
            buckets = list(self.client.list_buckets(project=project))

            if not buckets:
                logger.debug(f"  └─ Sin buckets")
                return []

            logger.debug(f"  ├─ {len(buckets)} buckets encontrados")

            for bucket in buckets:
                try:
                    bucket.reload()
                    region = bucket.location.upper() if bucket.location else ""

                    r = Resource(
                        nombre               = bucket.name.upper(),
                        estado               = "ACTIVO",
                        tipo_recurso         = self.resource_type,
                        fuente               = "GCP",
                        proyecto             = project.upper(),
                        region               = region,
                        zona                 = bucket.location_type.upper() if bucket.location_type else "",
                        fecha_creacion       = self._parse_date(
                            str(bucket.time_created) if bucket.time_created else ""
                        ),
                        ultima_actualizacion = self.now,
                        metadata             = {
                            "clase_almacenamiento": bucket.storage_class or "",
                            "acceso_publico":       self._get_public_access(bucket),
                            "versionado":           self._get_versioning(bucket),
                            "encriptacion":         self._get_encryption(bucket),
                            "retention_policy":     self._get_retention(bucket),
                            "lifecycle_rules":      self._get_lifecycle(bucket),
                            "location_type":        bucket.location_type.upper() if bucket.location_type else "",
                        }
                    )
                    resources.append(r)

                except Exception as e:
                    errores += 1
                    logger.debug(f"  │  Error en bucket {bucket.name}: {e}")

            if errores:
                logger.debug(f"  ├─ Con errores: {errores}")
            logger.debug(f"  └─ Total      : {len(resources)}")

        except Exception as e:
            logger.debug(f"  API no habilitada o sin acceso — Storage en {project}: {e}")

        return resources
