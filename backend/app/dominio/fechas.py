"""Cálculos de fechas sin dependencias externas."""

from __future__ import annotations

import calendar
from datetime import date


def sumar_meses(fecha: date, meses: int) -> date:
    """Suma meses de calendario. Si el día no existe en el mes destino, usa el último (31-ago + 3 = 30-nov)."""
    indice = fecha.month - 1 + meses
    anio = fecha.year + indice // 12
    mes = indice % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)
