"""``AlmacenamientoS3``: los videos en un bucket privado de AWS S3 (RESTR04) o de un servicio compatible con S3.

- ``video.url`` guarda ``s3://bucket/videos/AAAA/MM/bitacora-N.mp4``: la ubicación, nunca una URL pública.
- El bucket es privado; el navegador nunca habla con S3. Reproducir los videos será del módulo RF13 (pendiente):
  por la API, con un enlace firmado de corta duración (RNF08).
- boto3 es síncrono: cada llamada corre en un hilo (``asyncio.to_thread``) para no bloquear el monitoreo ni el SSE.
"""

from __future__ import annotations

import asyncio
from typing import Any

import boto3
from botocore.config import Config as ConfigBoto
from botocore.exceptions import BotoCoreError, ClientError

from app.integraciones.almacenamiento.interfaz import ErrorAlmacenamiento, IAlmacenamientoCloud

_ERRORES = (BotoCoreError, ClientError)


class AlmacenamientoS3(IAlmacenamientoCloud):
    def __init__(
        self,
        bucket: str,
        *,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        clave_acceso: str | None = None,
        clave_secreta: str | None = None,
        cliente: Any | None = None,
    ) -> None:
        self.bucket = bucket
        self._prefijo = f"s3://{bucket}/"
        self._cliente = cliente or boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=clave_acceso,
            aws_secret_access_key=clave_secreta,
            config=ConfigBoto(connect_timeout=5, read_timeout=30, retries={"max_attempts": 3}),
        )

    def _clave(self, url: str) -> str:
        if not url.startswith(self._prefijo):
            raise ErrorAlmacenamiento(f"El objeto {url} no es del bucket {self.bucket}.")
        return url.removeprefix(self._prefijo)

    async def _llamar(self, descripcion: str, operacion: str, **parametros: Any) -> Any:
        try:
            return await asyncio.to_thread(getattr(self._cliente, operacion), **parametros)
        except _ERRORES as error:
            raise ErrorAlmacenamiento(f"S3 no pudo {descripcion}: {error}") from error

    async def subir(self, archivo: bytes, nombre: str) -> str:
        await self._llamar(
            f"guardar {nombre}", "put_object", Bucket=self.bucket, Key=nombre, Body=archivo, ContentType="video/mp4"
        )
        return self._prefijo + nombre

    async def obtener(self, url: str) -> bytes:
        respuesta = await self._llamar(f"leer {url}", "get_object", Bucket=self.bucket, Key=self._clave(url))
        return await asyncio.to_thread(respuesta["Body"].read)

    async def eliminar(self, url: str) -> None:
        # En S3 borrar un objeto que ya no existe no es un error.
        await self._llamar(f"borrar {url}", "delete_object", Bucket=self.bucket, Key=self._clave(url))

    async def tamano(self, url: str) -> int:
        respuesta = await self._llamar(f"consultar {url}", "head_object", Bucket=self.bucket, Key=self._clave(url))
        return int(respuesta["ContentLength"])

    async def obtener_rango(self, url: str, inicio: int, fin: int) -> bytes:
        respuesta = await self._llamar(
            f"leer {url}", "get_object", Bucket=self.bucket, Key=self._clave(url), Range=f"bytes={inicio}-{fin}"
        )
        return await asyncio.to_thread(respuesta["Body"].read)

    async def revisar(self) -> None:
        await self._llamar(f"acceder al bucket {self.bucket}", "head_bucket", Bucket=self.bucket)
