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
| `INSTANCIAS` | VMs (GCP + GCVE + Bridge) + Cloud SQL + GKE Clusters |
| `ALMACENAMIENTO` | Buckets Cloud Storage |
| `CLOUD RUN` | Servicios Cloud Run |
| `SERVICIOS` | APIs y servicios habilitados por proyecto |

> **Nota:** Cloud SQL y GKE se muestran dentro de la hoja `INSTANCIAS`. La columna `TIPO RECURSO` distingue entre `VIRTUAL MACHINE`, `CLOUD SQL` y `GKE CLUSTER`.

---

## Campos del Excel

### Hoja INSTANCIAS

Contiene VMs (GCP + GCVE + Bridge) e instancias Cloud SQL. La columna `TIPO RECURSO` distingue el tipo de cada fila.

| Campo | Descripcion |
|---|---|
| `NOMBRE` | Nombre del recurso |
| `ESTADO` | VMs: `ENCENDIDA` `APAGADA` `INICIANDO` `SUSPENDIDA` · SQL: `ENCENDIDA` `APAGADA` `MANTENIMIENTO` `ERROR` |
| `TIPO RECURSO` | `VIRTUAL MACHINE`, `CLOUD SQL` o `GKE CLUSTER` |
| `FUENTE` | `GCP`, `GCVE` o `BRIDGE` (origen del dato) |
| `PROYECTO` | Proyecto GCP o etiqueta del host vCenter |
| `REGION` | Region donde corre el recurso |
| `ZONA` | Zona de disponibilidad |
| `VPC` | Red VPC a la que pertenece (solo VMs) |
| `SUBRED` | Subred dentro de la VPC (solo VMs) |
| `TIPO MAQUINA` | Familia de maquina (ej: `e2-standard-4`) o tier SQL (ej: `DB-CUSTOM-2-8192`) |
| `VCPUS` | Cantidad de CPUs virtuales |
| `RAM (GB)` | Memoria RAM en GB |
| `DISCO (GB)` | Tamaño total de disco en GB |
| `TIPO DISCO` | `SSD`, `HDD` o tipo especifico del proveedor |
| `SISTEMA OPERATIVO` | VM: OS detectado desde la imagen · SQL: version del motor (ej: `PostgreSQL 15`) |
| `IP INTERNA` | IP privada dentro de la red VPC |
| `IP EXTERNA` | IP publica asignada (vacia si no tiene) |
| `FECHA CREACION` | Fecha en que se creo el recurso |
| `ULTIMO ENCENDIDO` | Ultima vez que se inicio la VM (solo VMs) |
| `ULTIMO APAGADO` | Ultima vez que se detuvo la VM (solo VMs) |
| `PROGRAMA DE ENCENDIDO` | Schedule de encendido/apagado automatico configurado (solo VMs GCP) |
| `ULTIMA ACTUALIZACION` | Timestamp de la ultima ejecucion del script |
| `MOTOR` | Motor de base de datos: `MYSQL`, `POSTGRESQL`, `SQL SERVER` (solo Cloud SQL) |
| `VERSION DB` | Version especifica del motor (ej: `MySQL 8.0`, `PostgreSQL 15`) (solo Cloud SQL) |
| `TIER` | Tier de la instancia que define CPU y RAM (ej: `db-custom-4-16384`) (solo Cloud SQL) |
| `ALTA DISPONIBILIDAD` | `SI` si tiene replica regional activa · `NO` si es zona unica (solo Cloud SQL) |
| `REPLICA LECTURA` | `SI` si la instancia es una replica de lectura (solo Cloud SQL) |
| `BACKUP AUTOMATICO` | `SI` si tiene backups automaticos habilitados (solo Cloud SQL) |
| `VENTANA BACKUP` | Hora de inicio del backup automatico en UTC (ej: `03:00`) (solo Cloud SQL) |

**Manuales — el script nunca los toca:**

| Campo | Descripcion |
|---|---|
| `AMBIENTE` | `PRODUCCION` o `DESARROLLO` (dropdown) |
| `CRITICIDAD` | `ALTA`, `MEDIA` o `BAJA` (dropdown) |
| `CATEGORIA` | Clasificacion interna del recurso |
| `PROVEEDOR RESPONSABLE` | Empresa o equipo responsable |
| `PAM` | Si el acceso esta gestionado por PAM |
| `VERSION CYLANCE` | Version del agente Cylance instalado |
| `VERSION FOCUS` | Version del agente Focus instalado |
| `GRUPO TENABLE` | Grupo de escaneo en Tenable.io |
| `DESCRIPCION` | Descripcion libre |

---

### Hoja GKE

| Campo | Descripcion |
|---|---|
| `NOMBRE CLUSTER` | Nombre del cluster GKE |
| `ESTADO` | `ENCENDIDO` `APROVISIONANDO` `RECONCILIANDO` `DETENIENDO` `ERROR` `DEGRADADO` |
| `FUENTE` / `PROYECTO` / `REGION` / `ZONA` | Origen y ubicacion del cluster |
| `VPC` / `SUBRED` | Red VPC donde esta el cluster |
| `VERSION KUBERNETES` | Version del plano de control (master) |
| `VERSION NODOS` | Version de los nodos worker |
| `AUTOPILOT` | `SI` = Google gestiona los nodos automaticamente · `NO` = cluster Standard con nodos propios |
| `TOTAL NODOS` | Cantidad actual de nodos worker activos |
| `NODOS MIN` / `NODOS MAX` | Rango de autoscaling configurado en los node pools |
| `TIPO MAQUINA NODOS` | Tipo de maquina de los nodos (del primer node pool) |
| `NODE POOLS` | Cantidad de node pools en el cluster |
| `RELEASE CHANNEL` | Canal de actualizaciones automaticas: `RAPID` (mas nuevo) · `REGULAR` · `STABLE` (mas conservador) |
| `WORKLOAD IDENTITY` | `SI` si permite que los pods se autentiquen con APIs de GCP sin usar claves (recomendado para seguridad) |
| `IP CLUSTER (CIDR)` | Rango de IPs asignado a los pods del cluster |
| `ENDPOINT API SERVER` | Direccion del servidor de API de Kubernetes |
| `FECHA CREACION` / `ULTIMA ACTUALIZACION` | Fechas de creacion y ultimo escaneo |

**Manuales:** `AMBIENTE` · `CRITICIDAD` · `PROVEEDOR RESPONSABLE` · `DESCRIPCION`

---

### Hoja ALMACENAMIENTO

| Campo | Descripcion |
|---|---|
| `NOMBRE BUCKET` | Nombre del bucket (unico global en GCP) |
| `ESTADO` | Siempre `ACTIVO` |
| `FUENTE` / `PROYECTO` / `REGION` | Origen y ubicacion del bucket |
| `TIPO UBICACION` | `REGION` (una region) · `DUAL_REGION` (dos regiones pareadas) · `MULTI_REGION` (continente entero) |
| `CLASE ALMACENAMIENTO` | `STANDARD` (acceso frecuente) · `NEARLINE` (acceso ~mensual) · `COLDLINE` (acceso ~trimestral) · `ARCHIVE` (acceso anual, mas economico) |
| `ACCESO PUBLICO` | `PUBLICO` si permite acceso anonimo · `PRIVADO` si esta restringido · `REVISAR` si no hubo permisos para verificar |
| `VERSIONADO` | `SI` si guarda versiones anteriores de cada objeto (permite recuperar versiones borradas) |
| `ENCRIPTACION` | `GOOGLE-MANAGED` (por defecto) · `CUSTOMER-MANAGED (CMEK)` si usa clave propia en Cloud KMS |
| `RETENTION POLICY` | Tiempo minimo que deben conservarse los objetos antes de poder eliminarlos (ej: `365 dias`) |
| `LIFECYCLE RULES` | `SI` si tiene reglas automaticas de transicion de clase o eliminacion de objetos |
| `FECHA CREACION` / `ULTIMA ACTUALIZACION` | Fechas de creacion y ultimo escaneo |

**Manuales:** `AMBIENTE` · `CRITICIDAD` · `PROVEEDOR RESPONSABLE` · `DESCRIPCION`

---

### Hoja SERVICIOS

Lista de APIs y servicios GCP habilitados por proyecto. Util para auditar que servicios estan activos y detectar APIs innecesarias o riesgosas.

| Campo | Descripcion |
|---|---|
| `API ID` | Identificador tecnico del servicio (ej: `compute.googleapis.com`, `run.googleapis.com`) |
| `NOMBRE LEGIBLE` | Nombre comercial del servicio (ej: `Compute Engine API`, `Cloud Run Admin API`) |
| `ESTADO` | Siempre `HABILITADA` (solo se listan APIs activas) |
| `FUENTE` / `PROYECTO` | Origen y proyecto donde esta habilitada la API |
| `ULTIMA ACTUALIZACION` | Timestamp de la ultima ejecucion del script |

> Solo se reportan APIs de infraestructura relevantes (compute, storage, networking, AI, seguridad, etc.). Las APIs internas de Google se filtran automaticamente.

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
