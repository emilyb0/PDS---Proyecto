"""La migración 0001 ejecuta esquema_bd.sql tal cual y la sesión trabaja en hora de Colombia."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

RAIZ_BACKEND = Path(__file__).resolve().parents[2]
COPIA_MIGRACION = RAIZ_BACKEND / "migraciones" / "sql" / "0001_esquema_bd.sql"
CANDIDATOS_ORIGINAL = [
    RAIZ_BACKEND.parent / "docs" / "modelo" / "esquema_bd.sql",  # repositorio
    Path("/docs/modelo/esquema_bd.sql"),  # contenedor (docs montado en /docs)
]

TABLAS_ESPERADAS = {
    "usuario",
    "registro_auditoria",
    "dispositivo",
    "sensor",
    "mantenimiento",
    "ubicacion",
    "zona_operacion",
    "vertice_zona",
    "reserva",
    "bitacora_servicio",
    "registro_telemetria",
    "lectura_sensor",
    "incidencia",
    "alerta",
    "alerta_servicio",
    "alerta_mantenimiento",
    "atencion_alerta",
    "video",
}


def test_migracion_0001_es_copia_literal_del_esquema() -> None:
    original = next((ruta for ruta in CANDIDATOS_ORIGINAL if ruta.exists()), None)
    if original is None:
        pytest.skip("docs/modelo/esquema_bd.sql no está disponible en este entorno")
    assert COPIA_MIGRACION.read_bytes() == original.read_bytes(), (
        "migraciones/sql/0001_esquema_bd.sql debe ser idéntico a docs/modelo/esquema_bd.sql"
    )


async def test_migracion_crea_todas_las_tablas_y_reglas(motor: AsyncEngine) -> None:
    async with motor.connect() as conexion:
        tablas = set(
            (await conexion.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))).scalars()
        )
        version = (await conexion.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        disparadores = set(
            (await conexion.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"))).scalars()
        )
        funciones = set(
            (
                await conexion.execute(text("SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace"))
            ).scalars()
        )
        exclusion = (
            await conexion.execute(
                text("SELECT count(*) FROM pg_constraint WHERE conname = 'ex_reserva_cruce' AND contype = 'x'")
            )
        ).scalar_one()

    assert tablas >= TABLAS_ESPERADAS
    assert version == "0001"
    assert {"trg_reserva_validar", "trg_dispositivo_baja"} <= disparadores
    assert {"fn_validar_reserva", "fn_validar_baja", "reporte_dispositivo"} <= funciones
    assert exclusion == 1


async def test_sesion_de_base_en_hora_de_colombia(motor: AsyncEngine) -> None:
    async with motor.connect() as conexion:
        zona = (await conexion.execute(text("SHOW timezone"))).scalar_one()
    assert zona == "America/Bogota"
