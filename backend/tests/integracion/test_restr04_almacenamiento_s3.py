"""RESTR04 — Videos en un servicio tipo S3. Las pruebas usan ``moto`` (S3 simulado): ninguna sale a internet."""

from __future__ import annotations

from collections.abc import Iterator

import boto3
import httpx
import pytest
from moto import mock_aws

from app.config import Configuracion
from app.contenedor import Contenedor
from app.integraciones.almacenamiento import AlmacenamientoS3, ErrorAlmacenamiento, crear_almacenamiento
from app.usuarios.modelos import Usuario
from app.videos.gestor_videos import GestorVideos
from tests.fabrica import ciclo, crear_ubicaciones, servicio_en_curso

BUCKET = "robots-drones-videos"


@pytest.fixture
def s3(monkeypatch: pytest.MonkeyPatch) -> Iterator[AlmacenamientoS3]:
    for variable, valor in {
        "AWS_ACCESS_KEY_ID": "pruebas",
        "AWS_SECRET_ACCESS_KEY": "pruebas",
        "AWS_DEFAULT_REGION": "us-east-1",
    }.items():
        monkeypatch.setenv(variable, valor)
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        yield AlmacenamientoS3(BUCKET, region="us-east-1")


async def test_restr04_s3_guarda_lee_por_rango_y_borra(s3: AlmacenamientoS3) -> None:
    await s3.revisar()
    url = await s3.subir(b"0123456789", "videos/2026/11/bitacora-1.mp4")
    assert url == f"s3://{BUCKET}/videos/2026/11/bitacora-1.mp4"
    assert await s3.tamano(url) == 10
    assert await s3.obtener_rango(url, 3, 6) == b"3456"
    assert await s3.obtener(url) == b"0123456789"
    await s3.eliminar(url)
    await s3.eliminar(url)  # borrar lo que ya no existe no es un error
    with pytest.raises(ErrorAlmacenamiento):
        await s3.tamano(url)
    with pytest.raises(ErrorAlmacenamiento, match="no es del bucket"):
        await s3.obtener("s3://otro-bucket/x.mp4")
    with pytest.raises(ErrorAlmacenamiento):
        await AlmacenamientoS3("no-existe", region="us-east-1").revisar()


async def test_restr04_el_cierre_del_servicio_sube_el_video_al_bucket(
    s3: AlmacenamientoS3,
    cliente: httpx.AsyncClient,
    contenedor: Contenedor,
    admin: Usuario,
    operador: Usuario,
    auth,
) -> None:
    contenedor.almacenamiento = s3
    contenedor.gestor_videos = GestorVideos(s3, contenedor.config.pendientes_dir)
    lugares = await crear_ubicaciones(contenedor)
    _, _, id_bitacora = await servicio_en_curso(contenedor, administrador=admin, operador=operador, lugares=lugares)
    await ciclo(contenedor, minutes=25)
    detalle = (await cliente.get(f"/api/bitacoras/{id_bitacora}", headers=auth(admin))).json()
    assert detalle["estado"] == "FINALIZADO" and detalle["video"] is not None
    objeto = boto3.client("s3", region_name="us-east-1").get_object(
        Bucket=BUCKET, Key=f"videos/2026/11/bitacora-{id_bitacora}.mp4"
    )
    assert objeto["ContentType"] == "video/mp4" and objeto["Body"].read()[4:8] == b"ftyp"
    salud = (await cliente.get("/health")).json()
    assert salud["almacenamiento"] == "ok"


def test_restr04_configuracion_de_s3(config: Configuracion) -> None:
    with pytest.raises(ValueError, match="S3_BUCKET"):
        crear_almacenamiento(config.model_copy(update={"almacenamiento": "s3", "s3_bucket": None}))
    adaptador = crear_almacenamiento(config.model_copy(update={"almacenamiento": "s3", "s3_bucket": BUCKET}))
    assert isinstance(adaptador, AlmacenamientoS3) and adaptador.bucket == BUCKET
