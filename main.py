"""
main.py
Punto de entrada del inventario de recursos.
Escanea cada proyecto con todos los collectors — arquitectura por proyecto.
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from collectors.gcp.compute     import GCPComputeCollector
from collectors.gcp.gke         import GKECollector
from collectors.gcp.cloudsql    import CloudSQLCollector
from collectors.gcp.storage     import CloudStorageCollector
from collectors.gcp.apis        import APIsCollector
from collectors.gcp.cloudrun    import CloudRunCollector
from collectors.vcenter.compute import VCenterComputeCollector
from core                       import merger
from exporter.excel_writer      import write_all
from utils.gcp_auth             import get_credentials
from utils                      import logger as log

TIPO_LABELS = {
    "VIRTUAL MACHINE": "Maquinas Virtuales",
    "GKE CLUSTER":     "GKE Clusters",
    "CLOUD SQL":       "Bases de Datos",
    "CLOUD STORAGE":   "Almacenamiento",
    "API HABILITADA":  "Servicios / APIs",
    "CLOUD RUN":       "Cloud Run",
}


def interpolate(value, env: dict):
    if isinstance(value, str):
        def replace(match):
            var = match.group(1)
            if var not in env:
                raise KeyError(f"Variable de entorno no definida: {var}")
            return env[var]
        return re.sub(r"\$\{(\w+)\}", replace, value)
    if isinstance(value, list):
        return [interpolate(v, env) for v in value]
    if isinstance(value, dict):
        return {k: interpolate(v, env) for k, v in value.items()}
    return value


def load_config(path: str) -> dict:
    env_path = BASE_DIR / ".env"
    load_dotenv(env_path if env_path.exists() else None)
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return interpolate(raw, os.environ)


def main():
    parser = argparse.ArgumentParser(description="Inventario de Recursos")
    parser.add_argument("--config", default="config/settings.yaml")
    args   = parser.parse_args()

    config = load_config(args.config)
    log.setup(config["log"]["path"])
    log.header(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    all_resources = []
    # acumulador para el resumen: {(fuente, tipo): count}
    summary_data  = {}

    # ── GCP — escaneo por proyecto ────────────────────────────────────────────
    gcp_cfg  = config.get("gcp", {})
    projects = gcp_cfg.get("projects", [])
    cred_cfg = gcp_cfg.get("credentials", "ADC")

    if isinstance(projects, str):
        projects = [p.strip() for p in projects.split(",") if p.strip()]

    if projects:
        creds           = get_credentials(cred_cfg)
        default_project = projects[0]

        # instanciar collectors una sola vez
        gcp_collectors = [
            GCPComputeCollector(creds),
            GKECollector(creds),
            CloudSQLCollector(creds),
            CloudStorageCollector(creds, default_project=default_project),
            APIsCollector(creds),
            CloudRunCollector(creds),
        ]

        for project in projects:
            log.project_start(project)
            for collector in gcp_collectors:
                try:
                    resources = collector.collect(project)
                    all_resources.extend(resources)
                    label = TIPO_LABELS.get(collector.resource_type, collector.resource_type)
                    log.collector_result(label, len(resources))
                    key = ("GCP", collector.resource_type)
                    summary_data[key] = summary_data.get(key, 0) + len(resources)
                except Exception as e:
                    import logging
                    logging.getLogger("inventory").error(
                        f"    ✗ {collector.name} — {e}"
                    )
    else:
        import logging
        logging.getLogger("inventory").warning("  GCP — sin proyectos configurados")

    # ── vCenter — escaneo por host ────────────────────────────────────────────
    vc_cfg     = config.get("vcenter", {})
    vc_enabled = vc_cfg.get("enabled", False)
    if isinstance(vc_enabled, str):
        vc_enabled = vc_enabled.lower() == "true"

    if vc_enabled:
        retries = int(vc_cfg.get("retries", 3))
        delay   = int(vc_cfg.get("delay", 10))

        for vc_host in vc_cfg.get("hosts", []):
            source = vc_host.get("source", "VCENTER")
            log.project_start(f"{vc_host['host']} ({source})")
            try:
                collector = VCenterComputeCollector(
                    credentials = None,
                    host        = vc_host["host"],
                    user        = vc_host["user"],
                    password    = vc_host["password"],
                    port        = int(vc_host.get("port", 443)),
                    source      = source,
                    retries     = retries,
                    delay       = delay,
                )
                resources = collector.collect()
                all_resources.extend(resources)
                label = TIPO_LABELS.get(collector.resource_type, collector.resource_type)
                log.collector_result(label, len(resources))
                key = (source, collector.resource_type)
                summary_data[key] = summary_data.get(key, 0) + len(resources)
            except Exception as e:
                import logging
                logging.getLogger("inventory").error(f"    ✗ {vc_host['host']} — {e}")

    if not all_resources:
        import logging
        logging.getLogger("inventory").error(
            "No se recolectaron recursos. Verificar configuracion y credenciales."
        )
        sys.exit(1)

    # ── Merge idempotente ─────────────────────────────────────────────────────
    output_path = config["output"]["path"]
    final       = merger.merge(all_resources, output_path)

    # ── Exportar Excel multi-hoja ─────────────────────────────────────────────
    by_type = {}
    for r in final:
        by_type.setdefault(r.tipo_recurso, []).append(r)
    write_all(by_type, output_path)

    # ── Resumen final ─────────────────────────────────────────────────────────
    log.summary(summary_data, output_path)


if __name__ == "__main__":
    main()
