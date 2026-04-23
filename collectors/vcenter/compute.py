"""
collectors/vcenter/compute.py
Collector de VMs vCenter — soporta GCVE y Bridge.
"""

import logging
import ssl
import time

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

from core.base_collector import BaseCollector
from core.models import Resource

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "poweredOn":  "ENCENDIDA",
    "poweredOff": "APAGADA",
    "suspended":  "SUSPENDIDA",
}


class VCenterComputeCollector(BaseCollector):

    resource_type = "VIRTUAL MACHINE"

    def __init__(self, credentials, host: str, user: str, password: str,
                 port: int = 443, source: str = "VCENTER",
                 retries: int = 3, delay: int = 10):
        super().__init__(credentials)
        self.host     = host
        self.user     = user
        self.password = password
        self.port     = port
        self.source   = source
        self.retries  = retries
        self.delay    = delay

    def _connect(self):
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode    = ssl.CERT_NONE
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                logger.debug(f"Intento {attempt}/{self.retries} → {self.host}:{self.port}")
                si = SmartConnect(host=self.host, user=self.user, pwd=self.password,
                                  port=self.port, sslContext=ssl_context)
                return si
            except Exception as e:
                last_error = e
                if attempt < self.retries:
                    time.sleep(self.delay)
        logger.debug(f"Sin conexion tras {self.retries} intentos: {last_error}")
        return None

    def _get_ips(self, vm) -> tuple:
        ip_interna = ip_externa = ""
        if vm.guest and vm.guest.net:
            for nic in vm.guest.net:
                for ip in nic.ipAddress:
                    if ":" in ip: continue
                    if ip.startswith(("10.", "172.", "192.168.")):
                        if not ip_interna: ip_interna = ip
                    else:
                        if not ip_externa: ip_externa = ip
        return ip_interna, ip_externa

    def _get_os(self, vm) -> str:
        if vm.guest and vm.guest.guestFullName:
            return vm.guest.guestFullName.upper()
        if vm.config and vm.config.guestFullName:
            return vm.config.guestFullName.upper()
        return "DESCONOCIDO"

    def _get_disk_total(self, vm) -> float:
        total_kb = 0
        if vm.config and vm.config.hardware:
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualDisk):
                    total_kb += device.capacityInKB
        return round(total_kb / 1024 / 1024, 1)

    def _get_datacenter(self, vm) -> str:
        parent = vm.parent
        while parent:
            if isinstance(parent, vim.Datacenter):
                return parent.name
            parent = getattr(parent, "parent", None)
        return ""

    def collect(self, project: str = "") -> list[Resource]:
        si = self._connect()
        if not si:
            return []

        resources = []
        try:
            content_vc = si.RetrieveContent()
            view       = content_vc.viewManager.CreateContainerView(
                content_vc.rootFolder, [vim.VirtualMachine], True
            )
            for vm in view.view:
                try:
                    if vm.config and vm.config.template:
                        continue
                    datacenter         = self._get_datacenter(vm)
                    ip_interna, ip_ext = self._get_ips(vm)
                    status             = STATUS_MAP.get(vm.runtime.powerState, vm.runtime.powerState.upper())
                    vcpus              = vm.config.hardware.numCPU if vm.config else 0
                    ram_gb             = round(vm.config.hardware.memoryMB / 1024, 1) if vm.config else 0.0
                    zona               = vm.runtime.host.name.upper() if vm.runtime.host else ""
                    region             = datacenter.upper() if datacenter else "CLOUD-PRIVADA-LOCAL"

                    resources.append(Resource(
                        nombre               = vm.name.upper(),
                        estado               = status,
                        tipo_recurso         = self.resource_type,
                        fuente               = self.source,
                        proyecto             = datacenter.upper() if datacenter else self.host.upper(),
                        region               = region,
                        zona                 = zona or region,
                        vcpus                = vcpus,
                        ram_gb               = ram_gb,
                        disco_gb             = self._get_disk_total(vm),
                        sistema_operativo    = self._get_os(vm),
                        ip_interna           = ip_interna,
                        ip_externa           = ip_ext,
                        ultima_actualizacion = self.now,
                    ))
                except Exception as e:
                    logger.debug(f"Error en VM {vm.name}: {e}")
        finally:
            Disconnect(si)

        return resources
