"""
utils/logger.py
Logging limpio y profesional para el inventario.
"""

import logging
import os
from datetime import datetime

TIPO_ORDER = [
    "VIRTUAL MACHINE",
    "GKE CLUSTER",
    "CLOUD SQL",
    "CLOUD STORAGE",
    "API HABILITADA",
]

TIPO_LABELS = {
    "VIRTUAL MACHINE": "Maquinas Virtuales",
    "GKE CLUSTER":     "GKE Clusters",
    "CLOUD SQL":       "Bases de Datos",
    "CLOUD STORAGE":   "Almacenamiento",
    "API HABILITADA":  "Servicios / APIs",
}

_log = logging.getLogger("inventory")


def setup(log_dir: str) -> None:
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")

    # silenciar warnings de google auth
    logging.getLogger("google.auth._default").setLevel(logging.ERROR)
    logging.getLogger("google.auth.transport").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def header(ts: str) -> None:
    sep = "=" * 58
    _log.info(sep)
    _log.info(f"  INVENTARIO DE RECURSOS  —  {ts}")
    _log.info(sep)


def project_start(project: str) -> None:
    _log.info(f"\n  {project}")


def collector_result(tipo: str, count: int) -> None:
    label = TIPO_LABELS.get(tipo, tipo)
    if count > 0:
        _log.info(f"    {label:<26} {count:>5} recursos")
    # si count == 0 no logueamos nada — log mas limpio


def summary(results: dict, output_path: str) -> None:
    sep   = "=" * 58
    total = 0

    _log.info(f"\n{sep}")
    _log.info("  RESUMEN")
    _log.info(sep)
    _log.info(f"  {'Tipo':<26} {'Fuente':<10} {'Total':>7}")
    _log.info(f"  {'':─<46}")

    # ordenar segun TIPO_ORDER
    ordered = []
    for tipo in TIPO_ORDER:
        for (fuente, t), count in results.items():
            if t == tipo:
                ordered.append((fuente, tipo, count))

    # cualquier tipo no contemplado al final
    known = {(f, t) for f, t, _ in ordered}
    for (fuente, tipo), count in results.items():
        if (fuente, tipo) not in known:
            ordered.append((fuente, tipo, count))

    for fuente, tipo, count in ordered:
        label = TIPO_LABELS.get(tipo, tipo)
        _log.info(f"  {label:<26} {fuente:<10} {count:>7}")
        total += count

    _log.info(f"  {'':─<46}")
    _log.info(f"  {'TOTAL':<38} {total:>7}")
    _log.info(f"\n  Archivo: {output_path}")
    _log.info(sep)
