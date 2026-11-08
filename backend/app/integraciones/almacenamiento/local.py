"""``AlmacenamientoLocal``: los videos en una carpeta del disco (un volumen de Docker en desarrollo).

Sirve para desarrollar y probar sin nube. Para cumplir RESTR04 en la demo se usa el adaptador S3.
"""

from __future__ import annotations

import asyncio
from pathlib import Path, PurePosixPath

from app.integraciones.almacenamiento.interfaz import ErrorAlmacenamiento, IAlmacenamientoCloud

PREFIJO = "local://"


class AlmacenamientoLocal(IAlmacenamientoCloud):
    def __init__(self, carpeta: Path) -> None:
        self.carpeta = Path(carpeta)

    def _ruta(self, url_o_nombre: str) -> Path:
        nombre = url_o_nombre.removeprefix(PREFIJO)
        relativa = PurePosixPath(nombre)
        if relativa.is_absolute() or ".." in relativa.parts or not relativa.parts:
            raise ErrorAlmacenamiento(f"Nombre de objeto no válido: {nombre!r}")
        return self.carpeta.joinpath(*relativa.parts)

    async def subir(self, archivo: bytes, nombre: str) -> str:
        ruta = self._ruta(nombre)

        def escribir() -> None:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            temporal = ruta.with_suffix(ruta.suffix + ".parcial")
            temporal.write_bytes(archivo)
            temporal.replace(ruta)  # el objeto aparece completo o no aparece

        try:
            await asyncio.to_thread(escribir)
        except OSError as error:
            raise ErrorAlmacenamiento(f"No se pudo guardar {nombre}: {error}") from error
        return PREFIJO + nombre

    async def obtener(self, url: str) -> bytes:
        try:
            return await asyncio.to_thread(self._ruta(url).read_bytes)
        except OSError as error:
            raise ErrorAlmacenamiento(f"No se pudo leer {url}: {error}") from error

    async def eliminar(self, url: str) -> None:
        try:
            await asyncio.to_thread(self._ruta(url).unlink, missing_ok=True)
        except OSError as error:
            raise ErrorAlmacenamiento(f"No se pudo borrar {url}: {error}") from error

    async def tamano(self, url: str) -> int:
        try:
            return (await asyncio.to_thread(self._ruta(url).stat)).st_size
        except OSError as error:
            raise ErrorAlmacenamiento(f"No existe {url}: {error}") from error

    async def obtener_rango(self, url: str, inicio: int, fin: int) -> bytes:
        ruta = self._ruta(url)

        def leer() -> bytes:
            with ruta.open("rb") as archivo:
                archivo.seek(inicio)
                return archivo.read(fin - inicio + 1)

        try:
            return await asyncio.to_thread(leer)
        except OSError as error:
            raise ErrorAlmacenamiento(f"No se pudo leer {url}: {error}") from error

    async def revisar(self) -> None:
        def probar() -> None:
            self.carpeta.mkdir(parents=True, exist_ok=True)
            prueba = self.carpeta / ".salud"
            prueba.write_bytes(b"ok")
            prueba.unlink()

        try:
            await asyncio.to_thread(probar)
        except OSError as error:
            raise ErrorAlmacenamiento(f"La carpeta {self.carpeta} no se puede usar: {error}") from error
