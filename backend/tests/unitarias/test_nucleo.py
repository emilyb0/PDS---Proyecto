"""Reglas puras del núcleo: reloj, meses de calendario, tokens, logs sin secretos y funciones por rol."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

import pytest

from app.dominio.fechas import sumar_meses
from app.nucleo.enums import RolUsuario
from app.nucleo.errores import ErrorNoAutenticado
from app.nucleo.registro import FiltroSecretos, ocultar_secretos
from app.nucleo.reloj import ZONA_HORARIA, RelojSimulado, RelojSistema, a_hora_local, con_zona
from app.nucleo.seguridad import CifradorContrasenas, EmisorTokens
from app.usuarios.permisos import FUNCIONES_SOLO_ADMINISTRADOR, funciones_de


def test_reloj_simulado_avanza_solo_cuando_se_le_pide() -> None:
    reloj = RelojSimulado(datetime(2026, 11, 9, 8, 0))
    assert reloj.ahora() == datetime(2026, 11, 9, 8, 0)
    reloj.avanzar(minutes=11)
    assert reloj.ahora() == datetime(2026, 11, 9, 8, 11)
    assert reloj.hoy() == date(2026, 11, 9)


def test_reloj_sistema_da_hora_de_colombia_sin_zona() -> None:
    ahora = RelojSistema().ahora()
    assert ahora.tzinfo is None
    esperado = datetime.now(ZONA_HORARIA).replace(tzinfo=None)
    assert abs(ahora - esperado) < timedelta(seconds=5)


def test_conversion_de_zonas() -> None:
    utc = datetime(2026, 11, 9, 15, 0, tzinfo=UTC)
    assert a_hora_local(utc) == datetime(2026, 11, 9, 10, 0)
    assert con_zona(datetime(2026, 11, 9, 10, 0)).isoformat() == "2026-11-09T10:00:00-05:00"


@pytest.mark.parametrize(
    ("fecha", "meses", "esperado"),
    [
        (date(2026, 8, 7), 3, date(2026, 11, 7)),
        (date(2026, 8, 31), 3, date(2026, 11, 30)),  # el 31 de noviembre no existe
        (date(2026, 11, 30), 3, date(2027, 2, 28)),
        (date(2027, 11, 29), 3, date(2028, 2, 29)),  # año bisiesto
    ],
)
def test_sumar_meses_de_calendario(fecha: date, meses: int, esperado: date) -> None:
    assert sumar_meses(fecha, meses) == esperado


def test_token_vence_segun_el_reloj_inyectado() -> None:
    reloj = RelojSimulado(datetime(2026, 11, 9, 8, 0))
    emisor = EmisorTokens("x" * 40, reloj, expira_horas=8)
    emitido = emisor.emitir(7, "OPERADOR")
    assert emitido.expira == datetime(2026, 11, 9, 16, 0)
    assert emisor.validar(emitido.token) == 7
    reloj.avanzar(hours=7, minutes=59)
    assert emisor.validar(emitido.token) == 7
    reloj.avanzar(minutes=1)
    with pytest.raises(ErrorNoAutenticado, match="venció"):
        emisor.validar(emitido.token)


def test_token_alterado_o_de_otro_secreto_no_sirve() -> None:
    reloj = RelojSimulado(datetime(2026, 11, 9, 8, 0))
    token = EmisorTokens("x" * 40, reloj).emitir(1, "ADMINISTRADOR").token
    with pytest.raises(ErrorNoAutenticado):
        EmisorTokens("y" * 40, reloj).validar(token)
    with pytest.raises(ErrorNoAutenticado):
        EmisorTokens("x" * 40, reloj).validar(token[:-2] + "aa")
    with pytest.raises(ErrorNoAutenticado):
        EmisorTokens("x" * 40, reloj).validar("no-es-un-jwt")


def test_rnf05_cifrado_argon2_verifica_sin_guardar_texto_plano() -> None:
    cifrador = CifradorContrasenas(iteraciones=1, memoria_kib=64)
    guardado = cifrador.cifrar("Secreta123*")
    assert guardado.startswith("$argon2id$")
    assert "Secreta123*" not in guardado
    assert cifrador.verificar(guardado, "Secreta123*")
    assert not cifrador.verificar(guardado, "otra")
    assert not cifrador.verificar("hash-dañado", "Secreta123*")


def test_logs_ocultan_token_y_firma() -> None:
    linea = '127.0.0.1 - "GET /api/monitoreo/stream?token=abc.def.ghi&x=1 HTTP/1.1" 200'
    assert "abc.def.ghi" not in ocultar_secretos(linea)
    assert "token=***&x=1" in ocultar_secretos(linea)
    assert ocultar_secretos("/api/videos/3/contenido?usuario=1&expira=9&firma=f00").endswith("firma=***")

    registro = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s"',
        ("127.0.0.1", "GET", "/api/monitoreo/stream?token=secreto"),
        None,
    )
    FiltroSecretos().filter(registro)
    assert "secreto" not in registro.getMessage()


def test_funciones_por_rol() -> None:
    operador = funciones_de(RolUsuario.OPERADOR)
    administrador = funciones_de(RolUsuario.ADMINISTRADOR, modo_demo=True)
    assert not set(FUNCIONES_SOLO_ADMINISTRADOR) & set(operador)
    assert set(operador) < set(administrador)
    assert "demo.usar" in administrador
    assert "demo.usar" not in funciones_de(RolUsuario.ADMINISTRADOR, modo_demo=False)
