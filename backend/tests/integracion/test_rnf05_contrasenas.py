"""RNF05 — Las contraseñas se almacenan cifradas (Argon2id), nunca en texto plano."""

from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.usuarios.modelos import Usuario


async def test_rnf05_contrasena_queda_con_hash_argon2(
    cliente: httpx.AsyncClient, sesion: AsyncSession, admin: Usuario, auth
) -> None:
    datos = {
        "nombre": "Pedro",
        "correo_institucional": "pedro@campus.edu.co",
        "contrasena": "MiClave2026*",
        "rol": "OPERADOR",
    }
    assert (await cliente.post("/api/usuarios", json=datos, headers=auth(admin))).status_code == 201

    guardado = await sesion.scalar(
        select(Usuario.contrasena_hash).where(Usuario.correo_institucional == "pedro@campus.edu.co")
    )
    assert guardado is not None
    assert guardado.startswith("$argon2id$")
    assert "MiClave2026*" not in guardado
