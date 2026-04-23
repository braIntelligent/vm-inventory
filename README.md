# Cloud Infrastructure Inventory

Script Python que extrae, unifica y mantiene actualizado un inventario completo de recursos de infraestructura cloud e híbrida, generando un Excel multi-hoja con lógica idempotente — preserva los campos llenados manualmente entre ejecuciones.

---

## Fuentes soportadas

| Fuente | Recursos |
|---|---|
| **GCP** | VMs, GKE Clusters, Cloud SQL, Cloud Storage, Cloud Run, APIs habilitadas |
| **VMware GCVE** | VMs via vCenter |
| **VMware Bridge** | VMs via vCenter (on-premise) |

---

## Estructura del proyecto

```
vm-inventory/
├── main.py                        # Punto de entrada
├── requirements.txt
├── config/
│   └── settings.yaml              # Configuracion (usa variables de .env)
├── collectors/
│   ├── gcp/
│   │   ├── compute.py             # VMs GCP
│   │   ├── gke.py                 # Clusters GKE
│   │   ├── cloudsql.py            # Bases de datos Cloud SQL
│   │   ├── storage.py             # Buckets Cloud Storage
│   │   ├── cloudrun.py            # Servicios Cloud Run
│   │   └── apis.py                # APIs/servicios habilitados
│   └── vcenter/
│       └── compute.py             # VMs vCenter (GCVE / Bridge)
├── core/
│   ├── models.py                  # Dataclass Resource — contrato unico
│   ├── base_collector.py          # Clase abstracta BaseCollector
│   └── merger.py                  # Logica idempotente de merge
├── exporter/
│   └── excel_writer.py            # Generacion del Excel multi-hoja
└── utils/
    ├── gcp_auth.py                # Manejo de credenciales GCP
    └── logger.py                  # Logging limpio y profesional
```

---

## Hojas del Excel generado

| Hoja | Contenido |
|---|---|
| `INSTANCIAS` | VMs (GCP + GCVE + Bridge) + instancias Cloud SQL |
| `GKE` | Clusters GKE y su configuracion |
| `ALMACENAMIENTO` | Buckets Cloud Storage |
| `CLOUD RUN` | Servicios Cloud Run |
| `SERVICIOS` | APIs y servicios habilitados por proyecto |

> **Nota:** Cloud SQL se muestra dentro de la hoja `INSTANCIAS`. La columna `TIPO RECURSO` distingue entre `VIRTUAL MACHINE` y `CLOUD SQL`.

---

## Campos del Excel

### Hoja INSTANCIAS

#### Automaticos — el script actualiza en cada ejecucion

**Identidad:** `NOMBRE` · `ESTADO` · `TIPO RECURSO` · `FUENTE` · `PROYECTO`

**Ubicacion:** `REGION` · `ZONA` · `VPC` · `SUBRED`

**Computo (VMs):** `TIPO MAQUINA` · `VCPUS` · `RAM (GB)`

**Almacenamiento:** `DISCO (GB)` · `TIPO DISCO`

**Sistema:** `SISTEMA OPERATIVO`

**Red:** `IP INTERNA` · `IP EXTERNA`

**Tiempo:** `FECHA CREACION` · `ULTIMO ENCENDIDO` · `ULTIMO APAGADO` · `PROGRAMA DE ENCENDIDO` · `ULTIMA ACTUALIZACION`

**Base de datos (Cloud SQL):** `MOTOR` · `VERSION DB` · `TIER` · `ALTA DISPONIBILIDAD` · `REPLICA LECTURA` · `BACKUP AUTOMATICO` · `VENTANA BACKUP`

#### Manuales — el script nunca los toca

`AMBIENTE` · `CRITICIDAD` · `CATEGORIA` · `PROVEEDOR RESPONSABLE` · `PAM` · `VERSION CYLANCE` · `VERSION FOCUS` · `GRUPO TENABLE` · `DESCRIPCION`

---

### Hoja CLOUD RUN

| Campo | Descripcion |
|---|---|
| `NOMBRE SERVICIO` | Nombre del servicio Cloud Run (identificador unico dentro del proyecto y region) |
| `ESTADO` | `ACTIVO` = listo y sirviendo trafico · `ERROR` = ultimo despliegue fallo · `DESPLEGANDO` = actualizacion en curso |
| `FUENTE` | Siempre `GCP` |
| `PROYECTO` | Proyecto GCP donde esta deployado el servicio |
| `REGION` | Region donde corre (ej: `southamerica-west1`, `us-central1`) |
| `URL` | Endpoint publico del servicio (ej: `https://mi-api-abc123-uc.a.run.app`). Vacio si el acceso es solo interno |
| `CPU` | vCPUs asignadas por instancia. Puede ser fraccion: `0.5` = 500 millicores |
| `MEMORIA (GB)` | RAM asignada por instancia en GB |
| `MIN INSTANCIAS` | Instancias minimas siempre activas. `0` = escala a cero (cold start al llegar trafico, sin costo en reposo). Valores > 0 eliminan cold start pero generan costo constante |
| `MAX INSTANCIAS` | Tope de escalado automatico. `SIN LIMITE` = sin tope configurado |
| `CONCURRENCIA` | Maximo de requests simultaneos que procesa una sola instancia (default: 80 para HTTP) |
| `INGRESS` | Controla que trafico puede llegar al servicio: `ALL` = acceso publico desde internet · `INTERNAL` = solo desde VPC interna · `INTERNAL_AND_CLOUD_LOAD_BALANCING` = interno + Load Balancer de Google |
| `ULTIMA REVISION` | Nombre de la revision mas reciente. Cada deploy o cambio de config crea una nueva revision (ej: `mi-servicio-00042-xyz`) |
| `FECHA CREACION` | Fecha en que se creo el servicio por primera vez |
| `ULTIMA ACTUALIZACION` | Timestamp de la ultima ejecucion del script |

**Manuales:** `AMBIENTE` · `CRITICIDAD` · `PROVEEDOR RESPONSABLE` · `DESCRIPCION`

---

## Logica idempotente

| Situacion | Comportamiento |
|---|---|
| Recurso nuevo | Se agrega con campos manuales vacios |
| Recurso existente | Se actualizan solo campos automaticos — los manuales se preservan |
| Recurso eliminado (su fuente respondio) | Se marca como `ELIMINADA` — no se borra la fila |
| Recurso de fuente que fallo | Se conserva intacto hasta proxima ejecucion exitosa |

La clave de merge es `nombre + proyecto`, evitando colisiones entre recursos con el mismo nombre en distintos proyectos.

---

## Instalacion

### Requisitos
- Python 3.10+
- gcloud CLI instalado y autenticado

### Dependencias
```bash
pip install -r requirements.txt
```

### Autenticacion GCP

**Usuario personal (desarrollo/pruebas):**
```bash
gcloud auth application-default login
```

**Service Account (produccion):**
```bash
# Descargar key JSON y referenciarla en .env
GCP_CREDENTIALS=config/sa-key.json
```

---

## Configuracion

Copia `.env.example` a `.env` y completa los valores:

```env
# GCP
GCP_CREDENTIALS=ADC
GCP_PROJECTS=proyecto-1,proyecto-2,proyecto-3

# vCenter
VCENTER_ENABLED=true

VCENTER_HOST_1=vcenter01.empresa.local
VCENTER_USER_1=svc-inventory@empresa.local
VCENTER_PASS_1=password
VCENTER_PORT_1=443

VCENTER_HOST_2=vcenter02.empresa.cloud
VCENTER_USER_2=svc-inventory@empresa.local
VCENTER_PASS_2=password
VCENTER_PORT_2=443

# Output
OUTPUT_PATH=output/vm_inventory.xlsx
LOG_PATH=logs/
```

`settings.yaml` usa interpolacion de variables `${VAR}` — nunca escribas credenciales directamente en el YAML.

---

## Ejecucion

```bash
python main.py
# o especificando config:
python main.py --config config/settings.yaml
```

### Log de ejemplo

```
==========================================================
  INVENTARIO DE RECURSOS  —  2026-04-10 07:00:00
==========================================================

  proyecto-produccion
    Maquinas Virtuales          12 recursos
    GKE Clusters                 2 recursos
    Bases de Datos               4 recursos
    Almacenamiento              18 recursos
    Cloud Run                    6 recursos
    Servicios / APIs            52 recursos

  vcenter-gcve (GCVE)
    Maquinas Virtuales          87 recursos

==========================================================
  RESUMEN
==========================================================
  Tipo                       Fuente       Total
  ──────────────────────────────────────────────
  Maquinas Virtuales         GCP            109
  GKE Clusters               GCP              4
  Bases de Datos             GCP             28
  Almacenamiento             GCP            155
  Cloud Run                  GCP             18
  Servicios / APIs           GCP            948
  Maquinas Virtuales         GCVE           115
  Maquinas Virtuales         BRIDGE          24
  ──────────────────────────────────────────────
  TOTAL                                    1401

  Archivo: output/vm_inventory.xlsx
==========================================================
```

---

## Automatizacion — Task Scheduler (Windows)

Crea un archivo `run.bat`:
```bat
@echo off
cd /d C:\inventory\vm-inventory
python main.py
```

Configura la tarea:
- **Trigger:** Diario — 07:00 AM
- **Accion:** `run.bat`
- **Start in:** carpeta del proyecto
- **Reintentos:** 3 intentos cada 30 minutos

---

## Agregar nuevos collectors

La arquitectura esta disenada para crecer. Para agregar un nuevo tipo de recurso:

1. Crear `collectors/gcp/nuevo_recurso.py` heredando de `BaseCollector`
2. Implementar `collect(project) -> list[Resource]`
3. Registrar en `main.py` dentro de `gcp_collectors` y en `TIPO_LABELS`
4. Agregar columnas y hoja en `exporter/excel_writer.py` (`SHEET_REGISTRY`)

```python
# collectors/gcp/nuevo_recurso.py
class NuevoCollector(BaseCollector):
    resource_type = "NUEVO RECURSO"

    def collect(self, project: str) -> list[Resource]:
        # extraer recursos...
        return [Resource(nombre=..., tipo_recurso=self.resource_type, ...)]
```

---

## Permisos GCP requeridos

| Permiso / Rol | Para que sirve |
|---|---|
| `compute.instances.list` | VMs |
| `compute.machineTypes.get` | CPU y RAM de VMs |
| `compute.disks.get` | Tipo de disco |
| `compute.resourcePolicies.list` | Programas de encendido |
| `container.clusters.list` | Clusters GKE |
| `cloudsql.instances.list` | Instancias Cloud SQL |
| `storage.buckets.list` | Buckets |
| `storage.buckets.getIamPolicy` | Acceso publico de buckets |
| `run.routes.list` / `roles/run.viewer` | Servicios Cloud Run |
| `serviceusage.services.list` | APIs habilitadas |
| `resourcemanager.projects.get` | Acceso al proyecto |

### Habilitar API de Cloud Run por proyecto

```bash
gcloud services enable run.googleapis.com --project=TU_PROYECTO
```
