"""Geometría del campus sin PostGIS (especificación 7.5): punto en polígono y distancias.

Las coordenadas son (latitud, longitud) en grados. El campus es pequeño, así que el polígono se trata
como plano; para distancias se usa la fórmula del haversine.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

Punto = tuple[float, float]

_TOLERANCIA = 1e-9  # grados (~0,1 mm): margen para decidir que un punto está sobre el borde
RADIO_TIERRA_M = 6_371_000.0


def _sobre_segmento(p: Punto, a: Punto, b: Punto) -> bool:
    (py, px), (ay, ax), (by, bx) = p, a, b
    cruz = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if abs(cruz) > _TOLERANCIA:
        return False
    return (
        min(ax, bx) - _TOLERANCIA <= px <= max(ax, bx) + _TOLERANCIA
        and min(ay, by) - _TOLERANCIA <= py <= max(ay, by) + _TOLERANCIA
    )


def punto_en_poligono(punto: Punto, poligono: Sequence[Punto]) -> bool:
    """RF25: ``True`` si el punto está dentro del polígono. **El borde cuenta como dentro.**

    *Ray casting*: se cuenta cuántas veces un rayo horizontal desde el punto cruza los lados.
    """
    if len(poligono) < 3:
        return False
    vertices = list(poligono)
    for i, a in enumerate(vertices):
        if _sobre_segmento(punto, a, vertices[(i + 1) % len(vertices)]):
            return True

    lat, lon = punto
    dentro = False
    j = len(vertices) - 1
    for i in range(len(vertices)):
        lat_i, lon_i = vertices[i]
        lat_j, lon_j = vertices[j]
        if (lat_i > lat) != (lat_j > lat):
            lon_cruce = lon_i + (lat - lat_i) * (lon_j - lon_i) / (lat_j - lat_i)
            if lon < lon_cruce:
                dentro = not dentro
        j = i
    return dentro


def distancia_m(a: Punto, b: Punto) -> float:
    """Distancia en metros entre dos puntos (haversine)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * RADIO_TIERRA_M * math.asin(math.sqrt(h))
