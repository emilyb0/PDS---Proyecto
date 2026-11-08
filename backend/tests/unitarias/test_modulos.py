"""Regla de entregas (CLAUDE.md): el núcleo no depende de los módulos removibles.

Si esta prueba falla, algún archivo del núcleo importa un módulo de ``app/modulos/rfXX…``: hay que mover ese
código al módulo o pasarlo por un punto de extensión (``app/nucleo/extensiones.py``).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.modulos import modulos_disponibles, seleccionar_modulos
from app.nucleo.enums import RolUsuario
from app.nucleo.extensiones import REQUISITOS_NUCLEO, Extensiones
from app.usuarios.permisos import funciones_de

RAIZ_APP = Path(__file__).resolve().parents[2] / "app"
RAIZ_PRUEBAS = Path(__file__).resolve().parents[1]

# Los 15 RF de la entrega 2 (CLAUDE.md).
REQUISITOS_ENTREGA_2 = {
    "RF02",
    "RF03",
    "RF13",
    "RF14",
    "RF15",
    "RF16",
    "RF17",
    "RF19",
    "RF21",
    "RF22",
    "RF23",
    "RF24",
    "RF25",
    "RF26",
    "RF27",
}


def _importa_un_modulo(archivo: Path) -> list[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    encontrados = []
    for nodo in ast.walk(arbol):
        nombres = []
        if isinstance(nodo, ast.Import):
            nombres = [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nombres = [nodo.module]
        encontrados += [n for n in nombres if n.startswith("app.modulos.rf")]
    return encontrados


def test_el_nucleo_no_importa_modulos_removibles() -> None:
    infractores = {}
    for archivo in RAIZ_APP.rglob("*.py"):
        if "modulos" in archivo.relative_to(RAIZ_APP).parts:
            continue
        if importados := _importa_un_modulo(archivo):
            infractores[str(archivo.relative_to(RAIZ_APP))] = importados
    assert infractores == {}


def test_las_pruebas_del_nucleo_no_importan_modulos_removibles() -> None:
    infractores = {}
    for archivo in RAIZ_PRUEBAS.rglob("*.py"):
        if "modulos" in archivo.relative_to(RAIZ_PRUEBAS).parts:
            continue
        if importados := _importa_un_modulo(archivo):
            infractores[str(archivo.relative_to(RAIZ_PRUEBAS))] = importados
    assert infractores == {}


def test_las_pruebas_de_un_modulo_solo_importan_su_modulo() -> None:
    """Si un módulo se borra, las pruebas de los demás deben seguir corriendo."""
    for carpeta in sorted(RAIZ_PRUEBAS.joinpath("modulos").glob("rf*")):
        for archivo in carpeta.rglob("*.py"):
            ajenos = [i for i in _importa_un_modulo(archivo) if not i.startswith(f"app.modulos.{carpeta.name}")]
            assert ajenos == [], f"{archivo.relative_to(RAIZ_PRUEBAS)} importa {ajenos}"


def test_un_modulo_no_importa_otro_modulo() -> None:
    for clave, modulo in modulos_disponibles().items():
        carpeta = next(RAIZ_APP.joinpath("modulos").glob(f"{clave}_*"))
        for archivo in carpeta.rglob("*.py"):
            ajenos = [i for i in _importa_un_modulo(archivo) if not i.startswith(f"app.modulos.{carpeta.name}")]
            assert ajenos == [], f"{archivo.name} de {modulo.clave} importa {ajenos}"


def test_los_modulos_son_solo_de_la_entrega_2_y_tienen_sus_pruebas() -> None:
    for clave, modulo in modulos_disponibles().items():
        assert set(modulo.requisitos) <= REQUISITOS_ENTREGA_2, clave
        assert not set(modulo.requisitos) & set(REQUISITOS_NUCLEO), clave
        carpeta_app = next(RAIZ_APP.joinpath("modulos").glob(f"{clave}_*"))
        assert RAIZ_PRUEBAS.joinpath("modulos", carpeta_app.name).is_dir(), f"faltan las pruebas de {clave}"


def test_seleccionar_modulos() -> None:
    todos = seleccionar_modulos("todos")
    assert [m.clave for m in todos] == sorted(modulos_disponibles())
    assert seleccionar_modulos("ninguno") == []
    assert seleccionar_modulos("entrega1") == []
    claves = list(modulos_disponibles())[:2]
    if len(claves) == 2:  # no nombra módulos concretos: la prueba sigue valiendo si se borra alguno
        texto = f" {claves[1].upper()} , {claves[0]}"
        assert [m.clave for m in seleccionar_modulos(texto)] == [claves[1], claves[0]]
    with pytest.raises(ValueError, match="no existen: rf99"):
        seleccionar_modulos("rf99")


def test_funciones_del_menu_suman_las_de_los_modulos() -> None:
    extensiones = Extensiones()
    extensiones.agregar_funciones("mantenimiento.gestionar")
    extensiones.agregar_funciones("reportes.ver", solo_administrador=True)
    operador = funciones_de(RolUsuario.OPERADOR, extensiones=extensiones)
    administrador = funciones_de(RolUsuario.ADMINISTRADOR, extensiones=extensiones)
    assert "mantenimiento.gestionar" in operador and "reportes.ver" not in operador
    assert {"mantenimiento.gestionar", "reportes.ver"} <= set(administrador)
