"""Contraseñas con Argon2id (RNF05) y tokens JWT (RF20).

La vigencia del token se revisa contra el ``Reloj`` inyectado, no contra la hora del sistema,
para que las pruebas puedan simular su vencimiento.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.nucleo.errores import ErrorNoAutenticado
from app.nucleo.reloj import ZONA_HORARIA, Reloj


class CifradorContrasenas:
    """Cifra y verifica contraseñas con Argon2id. Nunca guarda ni devuelve el texto plano."""

    def __init__(self, iteraciones: int = 3, memoria_kib: int = 65536) -> None:
        self._hasher = PasswordHasher(time_cost=iteraciones, memory_cost=memoria_kib)
        # Hash de referencia para gastar el mismo tiempo cuando el correo no existe.
        self._hash_ficticio = self._hasher.hash("contrasena-ficticia-para-igualar-tiempos")

    def cifrar(self, contrasena: str) -> str:
        return self._hasher.hash(contrasena)

    def verificar(self, hash_guardado: str, contrasena: str) -> bool:
        try:
            return self._hasher.verify(hash_guardado, contrasena)
        except (VerifyMismatchError, VerificationError, InvalidHashError, UnicodeEncodeError):
            return False

    def verificar_ficticio(self, contrasena: str) -> bool:
        """Verificación de relleno cuando el usuario no existe (siempre devuelve ``False``)."""
        self.verificar(self._hash_ficticio, contrasena)
        return False


@dataclass(frozen=True)
class TokenEmitido:
    token: str
    expira: datetime  # hora local sin zona


class EmisorTokens:
    """Crea y valida los JWT de sesión."""

    def __init__(self, secreto: str, reloj: Reloj, expira_horas: int = 8, algoritmo: str = "HS256") -> None:
        self._secreto = secreto
        self._reloj = reloj
        self._expira = timedelta(hours=expira_horas)
        self._algoritmo = algoritmo

    def emitir(self, id_usuario: int, rol: str) -> TokenEmitido:
        ahora = self._reloj.ahora()
        expira = ahora + self._expira
        carga = {
            "sub": str(id_usuario),
            "rol": rol,
            "iat": int(ahora.replace(tzinfo=ZONA_HORARIA).timestamp()),
            "exp": int(expira.replace(tzinfo=ZONA_HORARIA).timestamp()),
        }
        return TokenEmitido(jwt.encode(carga, self._secreto, algorithm=self._algoritmo), expira)

    def validar(self, token: str) -> int:
        """Devuelve el id del usuario del token. Lanza ``ErrorNoAutenticado`` si es inválido o venció."""
        try:
            carga = jwt.decode(
                token,
                self._secreto,
                algorithms=[self._algoritmo],
                # Las fechas se validan con el Reloj, no con la hora del sistema que usaría PyJWT.
                options={
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                    "require": ["sub", "exp", "iat"],
                },
            )
        except jwt.PyJWTError as error:
            raise ErrorNoAutenticado("El token de acceso no es válido.") from error
        ahora = self._reloj.marca_unix()
        if int(carga["iat"]) > ahora + 60:
            raise ErrorNoAutenticado("El token de acceso no es válido.")
        if int(carga["exp"]) <= ahora:
            raise ErrorNoAutenticado("La sesión venció; inicie sesión de nuevo.")
        try:
            return int(carga["sub"])
        except (TypeError, ValueError) as error:
            raise ErrorNoAutenticado("El token de acceso no es válido.") from error
