"""``IAlmacenamientoCloud`` y sus adaptadores (RF12, RESTR04).

- ``AlmacenamientoLocal``: carpeta en disco (desarrollo y pruebas).
- ``AlmacenamientoS3``: AWS S3 o un servicio compatible (RESTR04).
"""

from __future__ import annotations

from app.config import Configuracion
from app.integraciones.almacenamiento.interfaz import ErrorAlmacenamiento, IAlmacenamientoCloud
from app.integraciones.almacenamiento.local import AlmacenamientoLocal
from app.integraciones.almacenamiento.s3 import AlmacenamientoS3

__all__ = [
    "AlmacenamientoLocal",
    "AlmacenamientoS3",
    "ErrorAlmacenamiento",
    "IAlmacenamientoCloud",
    "crear_almacenamiento",
]


def crear_almacenamiento(config: Configuracion) -> IAlmacenamientoCloud:
    """Adaptador según ``ALMACENAMIENTO`` (``local`` o ``s3``)."""
    if config.almacenamiento == "s3":
        if not config.s3_bucket:
            raise ValueError("Con ALMACENAMIENTO=s3 hay que indicar S3_BUCKET en el .env.")
        return AlmacenamientoS3(
            config.s3_bucket,
            region=config.s3_region,
            endpoint_url=config.s3_endpoint_url,
            clave_acceso=config.aws_access_key_id,
            clave_secreta=config.aws_secret_access_key,
        )
    return AlmacenamientoLocal(config.almacenamiento_local_dir)
