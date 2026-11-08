"""``IAlmacenamientoCloud``: dónde se guardan los videos (RF12, RF13, RF26, RESTR04).

Cambios frente al diagrama (decisión D2): ``tamano`` y ``obtener_rango`` para transmitir con ``Range`` sin cargar el
objeto completo, y ``revisar`` para ``/health``. ``subir`` devuelve la **ubicación** del objeto (por ejemplo
``s3://bucket/videos/…`` o ``local://videos/…``), que es lo que se guarda en ``video.url``; nunca una URL pública.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ErrorAlmacenamiento(Exception):
    """El almacenamiento no respondió o el objeto no existe."""


class IAlmacenamientoCloud(ABC):
    @abstractmethod
    async def subir(self, archivo: bytes, nombre: str) -> str:
        """Guarda el archivo con ese nombre (``videos/2026/11/bitacora-12.mp4``) y devuelve su ubicación."""

    @abstractmethod
    async def obtener(self, url: str) -> bytes:
        """Contenido completo del objeto."""

    @abstractmethod
    async def eliminar(self, url: str) -> None:
        """Borra el objeto (RF26). Borrar uno que ya no existe no es un error."""

    @abstractmethod
    async def tamano(self, url: str) -> int:
        """Tamaño del objeto en bytes."""

    @abstractmethod
    async def obtener_rango(self, url: str, inicio: int, fin: int) -> bytes:
        """Bytes ``inicio``…``fin`` (ambos incluidos), para responder con ``Range`` (RF13)."""

    @abstractmethod
    async def revisar(self) -> None:
        """Comprueba que el almacenamiento esté disponible (``/health``). Lanza ``ErrorAlmacenamiento`` si no."""
