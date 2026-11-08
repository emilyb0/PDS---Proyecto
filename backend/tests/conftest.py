"""Infraestructura de pruebas.

- PostgreSQL 16 REAL (nunca SQLite): la base de pruebas se borra, se recrea y se migra con Alembic una vez
  por corrida, y se vacía con TRUNCATE antes de cada prueba que la usa.
- Todo corre en un solo event loop de sesión, para que el motor async no cambie de loop.
- Reloj simulado y adaptadores falsos: ninguna prueba sale a internet.
- Entregas (CLAUDE.md): las pruebas del núcleo corren con TODOS los módulos removibles apagados; las de
  ``tests/modulos/`` los encienden (su conftest redefine ``modulos_activos``). ``--solo-entrega-1`` no recoge
  ``tests/modulos/``: así se comprueba que los 12 RF del núcleo no dependen de los 15 removibles.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":  # psycopg async no funciona con el ProactorEventLoop (decisión T10)
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault("JWT_SECRETO", "secreto-solo-para-pruebas-0123456789-abcdefghij")

import httpx
import psycopg
import pytest
from alembic import command
from alembic.config import Config as ConfigAlembic
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.config import Configuracion
from app.contenedor import Contenedor
from app.main import crear_app
from app.nucleo.bd import crear_motor
from app.nucleo.enums import RolUsuario
from app.nucleo.extensiones import ModuloRF
from app.nucleo.reloj import RelojSimulado
from app.usuarios.modelos import Usuario
from tests.fabrica import crear_usuario, encabezados

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
CARPETA_MODULOS = Path(__file__).resolve().parent / "modulos"
INICIO_PRUEBAS = datetime(2026, 11, 9, 8, 0)  # lunes 9 de noviembre de 2026, 08:00 (hora de Colombia)


# ============================================================================ opciones


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--lentas",
        action="store_true",
        default=False,
        help="Incluye las pruebas marcadas como lentas (RNF02).",
    )
    parser.addoption(
        "--solo-entrega-1",
        action="store_true",
        default=False,
        help="Corre solo las pruebas del núcleo (entrega 1), sin tests/modulos/.",
    )


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    if config.getoption("--solo-entrega-1") and collection_path.is_relative_to(CARPETA_MODULOS):
        return True
    return None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--lentas"):
        return
    omitir = pytest.mark.skip(reason="prueba lenta: use --lentas para incluirla")
    for item in items:
        if "lenta" in item.keywords:
            item.add_marker(omitir)


# ============================================================================ base de datos


@pytest.fixture(scope="session")
def config_pruebas() -> Configuracion:
    base = Configuracion()
    url = base.url_bd_pruebas
    nombre_bd = make_url(url).database or ""
    if "test" not in nombre_bd:
        raise RuntimeError(
            f"La base de pruebas debe llevar 'test' en el nombre (se borra en cada corrida): {nombre_bd}"
        )
    return base.model_copy(
        update={
            "bd_url": url,
            "argon2_iteraciones": 1,
            "argon2_memoria_kib": 64,
            "tareas_activas": False,
            "modo_demo": True,
            "dominio_correo_institucional": "campus.edu.co",
            "clima_proveedor": "falso",
            "almacenamiento": "local",
            "cors_origenes": "http://localhost:5173",
        }
    )


async def _recrear_bd(url: str) -> None:
    datos = make_url(url)
    conexion_admin = datos.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
    async with await psycopg.AsyncConnection.connect(conexion_admin, autocommit=True) as conexion:
        await conexion.execute(f'DROP DATABASE IF EXISTS "{datos.database}" WITH (FORCE)')
        await conexion.execute(f'CREATE DATABASE "{datos.database}"')


def _migrar(url: str) -> None:
    configuracion = ConfigAlembic(str(RAIZ_BACKEND / "alembic.ini"))
    configuracion.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(configuracion, "head")


@pytest.fixture(scope="session")
async def motor(config_pruebas: Configuracion) -> AsyncIterator[AsyncEngine]:
    await _recrear_bd(config_pruebas.url_bd)
    await asyncio.to_thread(_migrar, config_pruebas.url_bd)
    motor = crear_motor(config_pruebas.url_bd, pool_size=10, max_overflow=10)
    yield motor
    await motor.dispose()


@pytest.fixture(scope="session")
async def tablas(motor: AsyncEngine) -> list[str]:
    async with motor.connect() as conexion:
        filas = await conexion.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'")
        )
        return [fila[0] for fila in filas]


@pytest.fixture
async def bd_limpia(motor: AsyncEngine, tablas: list[str]) -> None:
    async with motor.begin() as conexion:
        await conexion.execute(text(f"TRUNCATE {', '.join(tablas)} RESTART IDENTITY CASCADE"))


# ============================================================================ aplicación


@pytest.fixture
def reloj() -> RelojSimulado:
    return RelojSimulado(INICIO_PRUEBAS)


@pytest.fixture
def modulos_activos() -> list[ModuloRF]:
    """El núcleo se prueba sin módulos removibles; ``tests/modulos/conftest.py`` los enciende todos."""
    return []


@pytest.fixture
def config(config_pruebas: Configuracion, tmp_path: Path) -> Configuracion:
    """Configuración de cada prueba: los videos y los pendientes van a una carpeta temporal propia."""
    return config_pruebas.model_copy(
        update={"almacenamiento_local_dir": tmp_path / "videos", "pendientes_dir": tmp_path / "pendientes"}
    )


@pytest.fixture
async def contenedor(
    config: Configuracion,
    motor: AsyncEngine,
    reloj: RelojSimulado,
    bd_limpia: None,
    modulos_activos: list[ModuloRF],
) -> Contenedor:
    return Contenedor.crear(config, reloj=reloj, motor=motor, modulos=modulos_activos)


@pytest.fixture
async def sesion(contenedor: Contenedor) -> AsyncIterator[AsyncSession]:
    async with contenedor.sesiones() as sesion:
        yield sesion


@pytest.fixture
def app(contenedor: Contenedor):
    return crear_app(contenedor)


@pytest.fixture
async def cliente(app) -> AsyncIterator[httpx.AsyncClient]:
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        yield cliente


# ============================================================================ usuarios de prueba


@pytest.fixture
async def admin(contenedor: Contenedor) -> Usuario:
    return await crear_usuario(
        contenedor,
        rol=RolUsuario.ADMINISTRADOR,
        nombre="Ana Admin",
        correo="admin@campus.edu.co",
        contrasena="Admin123*",
    )


@pytest.fixture
async def operador(contenedor: Contenedor) -> Usuario:
    return await crear_usuario(
        contenedor,
        rol=RolUsuario.OPERADOR,
        nombre="Óscar Operador",
        correo="operador1@campus.edu.co",
        contrasena="Operador123*",
    )


@pytest.fixture
def auth(contenedor: Contenedor) -> Callable[[Usuario], dict[str, str]]:
    """``auth(usuario)`` devuelve la cabecera Authorization con un token válido para ese usuario."""
    return lambda usuario: encabezados(contenedor, usuario)
