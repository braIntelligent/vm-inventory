"""
models.py
Contrato unico de datos para todos los recursos del inventario.
Cada collector retorna una lista de Resource sin importar la fuente.
"""

from dataclasses import dataclass, field


@dataclass
class Resource:

    # ── IDENTIDAD ─────────────────────────────────────────────────────────────
    nombre: str                = ""
    estado: str                = ""
    tipo_recurso: str          = ""
    fuente: str                = ""
    proyecto: str              = ""

    # ── UBICACION ─────────────────────────────────────────────────────────────
    region: str                = ""
    zona: str                  = ""
    vpc: str                   = ""
    subred: str                = ""

    # ── COMPUTO ───────────────────────────────────────────────────────────────
    tipo_maquina: str          = ""
    vcpus: int                 = 0
    ram_gb: float              = 0.0
    disco_gb: float            = 0.0
    tipo_disco: str            = ""

    # ── SISTEMA ───────────────────────────────────────────────────────────────
    sistema_operativo: str     = ""

    # ── RED ───────────────────────────────────────────────────────────────────
    ip_interna: str            = ""
    ip_externa: str            = ""

    # ── TIEMPO ────────────────────────────────────────────────────────────────
    fecha_creacion: str        = ""
    ultimo_encendido: str      = ""
    ultimo_apagado: str        = ""
    programa_encendido: str    = ""
    ultima_actualizacion: str  = ""

    # ── MANUALES ──────────────────────────────────────────────────────────────
    ambiente: str              = ""
    criticidad: str            = ""
    categoria: str             = ""
    proveedor_responsable: str = ""
    pam: str                   = ""
    version_cylance: str       = ""
    version_focus: str         = ""
    grupo_tenable: str         = ""
    descripcion: str           = ""

    # ── METADATA EXTRA ────────────────────────────────────────────────────────
    metadata: dict             = field(default_factory=dict)

    def to_dict(self) -> dict:
        from dataclasses import asdict
        d = asdict(self)
        d.pop("metadata")
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Resource":
        valid = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in valid}
        return cls(**filtered)
