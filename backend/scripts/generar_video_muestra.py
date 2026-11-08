"""Genera el MP4 de muestra que entrega el simulador al cerrar cada servicio (RF12, RESTR01).

El video se crea por código (no se descarga nada): H.264 en MP4, 320×240, 12 s, menos de 1 MB. Muestra un
"dron" que recorre una pista sobre un fondo degradado, con una barra de avance.

Uso, desde ``backend/`` (PowerShell)::

    uv sync --group video
    uv run python scripts/generar_video_muestra.py

Escribe ``app/integraciones/dispositivo/muestra.mp4``. El archivo generado se guarda en el repositorio.
"""

from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

DESTINO = Path(__file__).resolve().parents[1] / "app" / "integraciones" / "dispositivo" / "muestra.mp4"
ANCHO, ALTO, FPS, SEGUNDOS = 320, 240, 12, 12
LIMITE_BYTES = 1_000_000


def _cuadro(indice: int, total: int) -> np.ndarray:
    t = indice / total
    y, x = np.mgrid[0:ALTO, 0:ANCHO]
    imagen = np.zeros((ALTO, ANCHO, 3), dtype=np.uint8)
    imagen[..., 0] = (30 + 40 * x / ANCHO).astype(np.uint8)
    imagen[..., 1] = (90 + 80 * y / ALTO).astype(np.uint8)
    imagen[..., 2] = (60 + 30 * np.sin(2 * math.pi * (x / ANCHO + t))).astype(np.uint8)
    # Pista elíptica y el "dron" que la recorre.
    cx, cy, rx, ry = ANCHO / 2, ALTO / 2 - 10, 110, 70
    angulo = 2 * math.pi * t
    px, py = cx + rx * math.cos(angulo), cy + ry * math.sin(angulo)
    pista = np.abs(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 - 1) < 0.03
    imagen[pista] = (220, 220, 220)
    dron = (x - px) ** 2 + (y - py) ** 2 < 9**2
    imagen[dron] = (240, 80, 40)
    # Barra de avance.
    imagen[ALTO - 14 : ALTO - 6, 10 : 10 + int((ANCHO - 20) * t)] = (250, 250, 250)
    return imagen


def generar(destino: Path = DESTINO) -> int:
    total = FPS * SEGUNDOS
    # faststart: el índice (moov) va al principio, así el navegador empieza a reproducir sin bajar todo.
    with av.open(str(destino), mode="w", options={"movflags": "+faststart"}) as contenedor:
        flujo = contenedor.add_stream("libx264", rate=FPS)
        flujo.width, flujo.height, flujo.pix_fmt = ANCHO, ALTO, "yuv420p"
        flujo.time_base = Fraction(1, FPS)
        flujo.options = {"crf": "30", "preset": "veryslow"}
        for i in range(total):
            cuadro = av.VideoFrame.from_ndarray(_cuadro(i, total), format="rgb24")
            cuadro.pts = i
            for paquete in flujo.encode(cuadro):
                contenedor.mux(paquete)
        for paquete in flujo.encode():
            contenedor.mux(paquete)
    tamano = destino.stat().st_size
    if tamano > LIMITE_BYTES:
        raise SystemExit(f"El video pesa {tamano} bytes; el límite es {LIMITE_BYTES}.")
    return tamano


if __name__ == "__main__":
    print(f"{DESTINO} ({generar()} bytes)")
