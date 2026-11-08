"""Punto en polígono (ray casting propio, el borde cuenta como dentro) y distancias."""

from __future__ import annotations

import pytest

from app.dominio.geometria import distancia_m, punto_en_poligono
from app.ubicaciones.modelos import VerticeZona, ZonaOperacion

CUADRADO = [(4.63, -74.09), (4.65, -74.09), (4.65, -74.07), (4.63, -74.07)]
# Polígono cóncavo en forma de "L".
ELE = [(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 1.0), (1.0, 2.0), (0.0, 2.0)]


@pytest.mark.parametrize(
    ("punto", "dentro"),
    [
        ((4.64, -74.08), True),  # centro
        ((4.66, -74.08), False),  # al norte
        ((4.64, -74.10), False),  # al occidente
        ((4.63, -74.08), True),  # sobre el borde sur
        ((4.64, -74.07), True),  # sobre el borde oriental
        ((4.65, -74.09), True),  # en un vértice
        ((4.6300001, -74.08), True),
        ((4.6299999, -74.08), False),
    ],
)
def test_punto_en_poligono_y_el_borde_cuenta_como_dentro(punto: tuple[float, float], dentro: bool) -> None:
    assert punto_en_poligono(punto, CUADRADO) is dentro


@pytest.mark.parametrize(
    ("punto", "dentro"),
    [((0.5, 0.5), True), ((1.5, 0.5), True), ((0.5, 1.5), True), ((1.5, 1.5), False), ((1.0, 1.5), True)],
)
def test_punto_en_poligono_concavo(punto: tuple[float, float], dentro: bool) -> None:
    assert punto_en_poligono(punto, ELE) is dentro


def test_poligono_invalido_no_contiene_nada() -> None:
    assert not punto_en_poligono((0, 0), [(0, 0), (1, 1)])


def test_zona_operacion_contiene() -> None:
    zona = ZonaOperacion(
        nombre="Campus",
        vertices=[VerticeZona(orden=i, latitud=lat, longitud=lon) for i, (lat, lon) in enumerate(CUADRADO, 1)],
    )
    assert zona.contiene(4.64, -74.08)
    assert not zona.contiene(4.70, -74.08)


def test_distancia_haversine() -> None:
    # Un grado de latitud son unos 111 km.
    assert distancia_m((4.0, -74.0), (5.0, -74.0)) == pytest.approx(111_195, rel=1e-3)
    assert distancia_m((4.638, -74.084), (4.638, -74.084)) == 0
