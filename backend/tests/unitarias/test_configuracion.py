"""La URL de la base sale de PUERTO_BD en la máquina y de BD_URL dentro de Docker (decisiones I-1 e I-2)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.config import ConfiguracionBD


def _config(**valores: object) -> ConfiguracionBD:
    base = {
        "postgres_db": "robots",
        "postgres_user": "robots",
        "postgres_password": "clave",
        "bd_url": None,
        "bd_url_pruebas": None,
    }
    return ConfiguracionBD(_env_file=None, **{**base, **valores})


def test_en_la_maquina_la_url_usa_127_0_0_1_y_puerto_bd() -> None:
    config = _config(puerto_bd=5433)
    assert config.url_bd == "postgresql+psycopg://robots:clave@127.0.0.1:5433/robots"
    assert config.url_bd_pruebas == "postgresql+psycopg://robots:clave@127.0.0.1:5433/robots_test"


def test_puerto_por_defecto_es_5433() -> None:
    assert ConfiguracionBD.model_fields["puerto_bd"].default == 5433


def test_dentro_de_docker_manda_bd_url() -> None:
    config = _config(puerto_bd=5433, bd_url="postgresql+psycopg://robots:clave@db:5432/robots")
    assert config.url_bd == "postgresql+psycopg://robots:clave@db:5432/robots"
    assert config.url_bd_pruebas.endswith("@db:5432/robots_test")


def test_bd_url_vacia_cuenta_como_no_definida() -> None:
    assert _config(puerto_bd=6000, bd_url="  ").url_bd.endswith("@127.0.0.1:6000/robots")


def test_env_example_sin_comentarios_en_la_misma_linea() -> None:
    """Docker Compose toma "VAR=   # texto" como valor "# texto": los comentarios van en su propia línea."""
    ejemplo = Path(__file__).resolve().parents[3] / ".env.example"
    if not ejemplo.exists():
        pytest.skip(".env.example no está disponible en este entorno")
    lineas = ejemplo.read_text(encoding="utf-8").splitlines()
    con_comentario = [linea for linea in lineas if not linea.lstrip().startswith("#") and re.search(r"\s#", linea)]
    assert con_comentario == []
