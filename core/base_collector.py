"""
base_collector.py
Clase abstracta que deben implementar todos los collectors.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from core.models import Resource


class BaseCollector(ABC):

    resource_type: str = ""

    def __init__(self, credentials):
        self.credentials = credentials
        self.now = datetime.now().strftime("%Y-%m-%d %H:%M")

    @abstractmethod
    def collect(self, project: str) -> list[Resource]:
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def _parse_last(self, url: str) -> str:
        return url.split("/")[-1] if url else ""

    def _parse_date(self, timestamp: str) -> str:
        return timestamp[:10] if timestamp else ""

    def _parse_region(self, zone: str) -> str:
        parts = zone.split("-")
        return "-".join(parts[:-1]) if len(parts) > 1 else zone
