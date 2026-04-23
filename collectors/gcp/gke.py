"""
collectors/gcp/gke.py
Collector de clusters GKE.
"""

import logging

from google.cloud import container_v1

from core.base_collector import BaseCollector
from core.models import Resource

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "RUNNING":            "ENCENDIDO",
    "PROVISIONING":       "APROVISIONANDO",
    "RECONCILING":        "RECONCILIANDO",
    "STOPPING":           "DETENIENDO",
    "ERROR":              "ERROR",
    "DEGRADED":           "DEGRADADO",
    "STATUS_UNSPECIFIED": "DESCONOCIDO",
}


class GKECollector(BaseCollector):

    resource_type = "GKE CLUSTER"

    def __init__(self, credentials):
        super().__init__(credentials)
        self.client = container_v1.ClusterManagerClient(credentials=credentials)

    def _get_node_pool_machine(self, pool) -> str:
        try:
            return pool.config.machine_type.upper() if pool.config.machine_type else ""
        except Exception:
            return ""

    def _is_autopilot(self, cluster) -> str:
        try:
            return "SI" if cluster.autopilot.enabled else "NO"
        except Exception:
            return "NO"

    def _get_release_channel(self, cluster) -> str:
        try:
            return container_v1.ReleaseChannel.Channel(cluster.release_channel.channel).name
        except Exception:
            return ""

    def _get_workload_identity(self, cluster) -> str:
        try:
            return "SI" if cluster.workload_identity_config.workload_pool else "NO"
        except Exception:
            return "NO"

    def _get_node_totals(self, cluster) -> tuple:
        total_nodos = min_nodos = max_nodos = 0
        try:
            total_nodos = cluster.current_node_count
            for pool in cluster.node_pools:
                if pool.autoscaling and pool.autoscaling.enabled:
                    min_nodos += pool.autoscaling.min_node_count
                    max_nodos += pool.autoscaling.max_node_count
        except Exception:
            pass
        return total_nodos, min_nodos, max_nodos

    def collect(self, project: str) -> list[Resource]:
        resources = []
        try:
            response = self.client.list_clusters(parent=f"projects/{project}/locations/-")
            for cluster in response.clusters:
                try:
                    status       = STATUS_MAP.get(container_v1.Cluster.Status(cluster.status).name, "DESCONOCIDO")
                    zone         = cluster.location.upper()
                    region       = self._parse_region(zone) if "-" in zone else zone
                    total, mn, mx = self._get_node_totals(cluster)
                    tipo_maquina = self._get_node_pool_machine(cluster.node_pools[0]) if cluster.node_pools else ""

                    resources.append(Resource(
                        nombre               = cluster.name.upper(),
                        estado               = status,
                        tipo_recurso         = self.resource_type,
                        fuente               = "GCP",
                        proyecto             = project.upper(),
                        region               = region,
                        zona                 = zone,
                        vpc                  = self._parse_last(cluster.network).upper(),
                        subred               = self._parse_last(cluster.subnetwork).upper(),
                        tipo_maquina         = tipo_maquina,
                        vcpus                = total,
                        sistema_operativo    = cluster.current_master_version,
                        ip_interna           = cluster.cluster_ipv4_cidr,
                        ip_externa           = cluster.endpoint,
                        fecha_creacion       = self._parse_date(cluster.create_time),
                        ultima_actualizacion = self.now,
                        metadata             = {
                            "autopilot":          self._is_autopilot(cluster),
                            "version_kubernetes": cluster.current_master_version,
                            "version_nodos":      cluster.current_node_version,
                            "total_nodos":        total,
                            "nodos_min":          mn,
                            "nodos_max":          mx,
                            "release_channel":    self._get_release_channel(cluster),
                            "workload_identity":  self._get_workload_identity(cluster),
                            "node_pools":         len(cluster.node_pools),
                        }
                    ))
                except Exception as e:
                    logger.debug(f"Error en cluster {cluster.name}: {e}")
        except Exception as e:
            logger.debug(f"GKE no disponible en {project}: {str(e).splitlines()[0]}")
        return resources
