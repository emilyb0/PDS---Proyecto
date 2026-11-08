"""Recorre de punta a punta el diagrama de secuencia contra la API en ejecución, con los 12 RF de la entrega 1.

Inventario → crear reserva (con los rechazos de RF06 y RF07) → iniciar → telemetría → alerta → cierre con video →
bitácora y ruta → consulta de alertas.

Necesita la API levantada, los datos semilla y ``MODO_DEMO=true``. Usa los controles de demo para no esperar.
RF01 y RF18 (registrar dispositivo y usuario) no se recorren aquí para no dejar datos de más: los cubren las pruebas
y ``docs/demo.md``.

Uso (PowerShell, desde ``backend/``)::

    uv run python scripts/demo_e2e.py                          # contra http://127.0.0.1:8010
    docker compose exec api python scripts/demo_e2e.py --url http://localhost:8000

Termina con código 0 si todo salió bien y 1 si algún paso falló. Deja el dispositivo como estaba (repara el sensor).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx

ADMIN = ("admin@campus.edu.co", "Admin123*")
OPERADOR = ("operador1@campus.edu.co", "Operador123*")
DURACION_MIN = 2  # el robot recorre todo en 2 × 0,8 = 96 s
ROBOT_EN_FALLA = "R-004"  # la semilla le deja el LIDAR en falla (RF07)


class FalloDemo(Exception):
    pass


class Demo:
    def __init__(self, url: str) -> None:
        self.api = httpx.AsyncClient(base_url=url, timeout=20)
        self.inicio = time.monotonic()
        self.eventos: list[tuple[str, dict[str, Any]]] = []
        self.pasos: list[str] = []

    # ------------------------------------------------------------------ utilidades

    def tiempo(self) -> str:
        return f"{time.monotonic() - self.inicio:6.1f} s"

    def ok(self, paso: str, detalle: str = "") -> None:
        self.pasos.append(paso)
        print(f"[{self.tiempo()}] ✔ {paso}" + (f" — {detalle}" if detalle else ""))

    async def pedir(self, metodo: str, ruta: str, esperado: int, **opciones: Any) -> httpx.Response:
        respuesta = await self.api.request(metodo, ruta, **opciones)
        if respuesta.status_code != esperado:
            raise FalloDemo(f"{metodo} {ruta} respondió {respuesta.status_code}: {respuesta.text[:300]}")
        return respuesta

    def de_tipo(self, tipo: str) -> list[dict[str, Any]]:
        return [datos for t, datos in self.eventos if t == tipo]

    async def esperar(self, condicion: Callable[[], Any], segundos: float, que: str) -> Any:
        fin = time.monotonic() + segundos
        while time.monotonic() < fin:
            resultado = condicion()
            if resultado:
                return resultado
            await asyncio.sleep(0.3)
        raise FalloDemo(f"no llegó a tiempo: {que} ({segundos:.0f} s)")

    async def escuchar(self, token: str) -> None:
        tipo, datos = "message", []
        async with self.api.stream("GET", "/api/monitoreo/stream", params={"token": token}, timeout=None) as r:
            async for linea in r.aiter_lines():
                if linea == "":
                    if datos:
                        self.eventos.append((tipo, json.loads("\n".join(datos))))
                    tipo, datos = "message", []
                elif linea.startswith("event:"):
                    tipo = linea[6:].strip()
                elif linea.startswith("data:"):
                    datos.append(linea[5:].strip())

    async def entrar(self, correo: str, contrasena: str) -> tuple[dict[str, str], dict[str, Any]]:
        cuerpo = (
            await self.pedir("POST", "/api/auth/login", 200, json={"correo": correo, "contrasena": contrasena})
        ).json()
        return {"Authorization": f"Bearer {cuerpo['token']}"}, cuerpo

    # ------------------------------------------------------------------ recorrido

    async def recorrer(self) -> None:
        salud = (await self.api.get("/health")).json()
        if salud.get("base_datos") != "ok" or salud.get("almacenamiento") != "ok":
            raise FalloDemo(f"la API no está sana: {salud}")
        self.ok("API sana (/health)", ", ".join(f"{k}={v}" for k, v in salud.items() if k != "version"))

        admin, sesion = await self.entrar(*ADMIN)
        operador, sesion_op = await self.entrar(*OPERADOR)
        activos = sesion["requisitos_activos"]
        self.ok("Sesión de administrador y operador (RF20)", f"{len(activos)} requisitos activos: {', '.join(activos)}")
        if "demo.usar" not in sesion["funciones"]:
            raise FalloDemo("la API no tiene MODO_DEMO=true (los controles de demo están apagados)")

        lugares = {
            u["nombre"]: u["id_ubicacion"]
            for u in (await self.pedir("GET", "/api/ubicaciones", 200, headers=admin)).json()
        }
        if not {"Cafetería", "Rectoría"} <= set(lugares):
            raise FalloDemo("faltan los datos semilla (python -m app.semilla)")
        # La hora sale del reloj del servidor (hora de Colombia), no del equipo que corre el script.
        ahora = datetime.fromisoformat(
            (await self.pedir("GET", "/api/monitoreo", 200, headers=admin)).json()["generado"]
        )
        solicitud = {
            "tipo_servicio": "PEDIDO_CAFETERIA",
            "fecha": ahora.date().isoformat(),
            "hora_inicio": ahora.strftime("%H:%M"),
            "duracion_estimada_min": DURACION_MIN,
            "id_origen": lugares["Cafetería"],
            "id_destino": lugares["Rectoría"],
        }

        # Inventario (RF04): el robot disponible y apto con más batería.
        robots = (
            await self.pedir("GET", "/api/dispositivos", 200, params={"tipo": "ROBOT", "limite": 200}, headers=admin)
        ).json()["items"]
        aptos = [
            d for d in robots if d["estado"] == "DISPONIBLE" and not d["sensores_en_falla"] and d["nivel_bateria"] >= 30
        ]
        if not aptos:
            raise FalloDemo("no hay robots disponibles")
        robot = max(aptos, key=lambda d: d["nivel_bateria"])
        self.ok(
            "Inventario (RF04)",
            f"{len(robots)} robots; se elige {robot['numero_serie']} con {robot['nivel_bateria']} %",
        )

        id_operador = sesion_op["usuario"]["id_usuario"]
        reserva = (
            await self.pedir(
                "POST",
                "/api/reservas",
                201,
                headers=admin,
                json={**solicitud, "id_dispositivo": robot["id_dispositivo"], "id_operador": id_operador},
            )
        ).json()
        self.ok(
            "Reserva creada (RF05)",
            f"#{reserva['id_reserva']} a las {reserva['hora_inicio']}, código {reserva['codigo_entrega']}",
        )

        # RF06: el mismo robot a la misma hora se rechaza con la reserva en conflicto.
        cruce = (
            await self.pedir(
                "POST",
                "/api/reservas",
                409,
                headers=admin,
                json={**solicitud, "id_dispositivo": robot["id_dispositivo"], "id_operador": id_operador},
            )
        ).json()["error"]
        if cruce["codigo"] != "CRUCE_HORARIO":
            raise FalloDemo(f"se esperaba CRUCE_HORARIO: {cruce}")
        self.ok("Cruce de horario rechazado (RF06)", cruce["mensaje"])

        # RF07: el robot con un sensor en falla no se puede reservar.
        en_falla = next((d for d in robots if d["numero_serie"] == ROBOT_EN_FALLA), None)
        if en_falla is not None and en_falla["sensores_en_falla"]:
            rechazo = (
                await self.pedir(
                    "POST",
                    "/api/reservas",
                    409,
                    headers=admin,
                    json={**solicitud, "id_dispositivo": en_falla["id_dispositivo"], "id_operador": id_operador},
                )
            ).json()["error"]
            if rechazo["codigo"] != "DISPOSITIVO_NO_APTO":
                raise FalloDemo(f"se esperaba DISPOSITIVO_NO_APTO: {rechazo}")
            self.ok("Dispositivo no apto rechazado (RF07)", "; ".join(rechazo["detalles"]["motivos"]))

        oyente = asyncio.create_task(self.escuchar(sesion_op["token"]))
        await asyncio.sleep(1)
        try:
            await self._servicio(admin, operador, reserva, robot)
        finally:
            oyente.cancel()

    async def _servicio(self, admin: dict, operador: dict, reserva: dict, robot: dict) -> None:
        id_robot, serie = robot["id_dispositivo"], robot["numero_serie"]
        inicio = (
            await self.pedir("POST", f"/api/demo/reservas/{reserva['id_reserva']}/iniciar", 200, headers=admin)
        ).json()
        id_bitacora = inicio["id_bitacora"]
        await self.esperar(lambda: self.de_tipo("servicio"), 10, "evento servicio INICIADO")
        self.ok("Servicio iniciado y bitácora abierta (RF08)", f"bitácora #{id_bitacora}; evento SSE servicio INICIADO")

        def telemetria_del_robot() -> list[dict]:
            return [
                e
                for e in self.de_tipo("telemetria")
                if e["id_dispositivo"] == id_robot and e["id_bitacora"] == id_bitacora
            ]

        primera = (await self.esperar(telemetria_del_robot, 12, "telemetría del robot"))[-1]
        self.ok(
            "Telemetría en tiempo real (RF09, RF10)",
            f"{primera['estado_servicio']}, batería {primera['nivel_bateria']} %, "
            f"({primera['latitud']}, {primera['longitud']})",
        )

        await self.pedir(
            "POST",
            f"/api/demo/dispositivos/{id_robot}/eventos",
            200,
            headers=admin,
            json={"tipo": "FALLA_SENSOR", "sensor": "Ultrasonido"},
        )
        alerta = await self.esperar(
            lambda: next((a for a in self.de_tipo("alerta") if a["id_dispositivo"] == id_robot), None),
            12,
            "alerta de sensor",
        )
        self.ok("Alerta de servicio (RF11)", alerta["descripcion"])
        await self.pedir(
            "POST",
            f"/api/demo/dispositivos/{id_robot}/eventos",
            200,
            headers=admin,
            json={"tipo": "REPARAR_SENSOR", "sensor": "Ultrasonido"},
        )

        # Sin RF24 (pendiente) el robot deja el pedido en el destino y vuelve a la base.
        await self.esperar(lambda: len(self.de_tipo("servicio")) >= 2, 120, "evento servicio FINALIZADO")
        bitacora = (await self.pedir("GET", f"/api/bitacoras/{id_bitacora}", 200, headers=operador)).json()
        if bitacora["estado"] != "FINALIZADO" or bitacora["video"] is None:
            raise FalloDemo(f"la bitácora no quedó cerrada con video: {bitacora['estado']}, video={bitacora['video']}")
        self.ok(
            "Cierre con video (RF08, RF12)",
            f"salida {bitacora['hora_salida'][11:19]}, regreso {bitacora['hora_regreso'][11:19]}, "
            f"{len(bitacora['incidencias'])} incidencia(s), video de {bitacora['video']['duracion_seg']} s",
        )
        ruta = (await self.pedir("GET", f"/api/bitacoras/{id_bitacora}/ruta", 200, headers=operador)).json()
        self.ok("Ruta recorrida (RF08)", f"{len(ruta['puntos'])} puntos")

        alertas = (
            await self.pedir("GET", "/api/alertas", 200, params={"id_dispositivo": id_robot}, headers=operador)
        ).json()["items"]
        if not any(a["id_alerta"] == alerta["id_alerta"] for a in alertas):
            raise FalloDemo("la alerta del servicio no aparece en GET /api/alertas")
        self.ok("Consulta de alertas (RF11)", f"{len(alertas)} alerta(s) de {serie}")

    async def cerrar(self) -> None:
        await self.api.aclose()


async def principal(url: str) -> int:
    demo = Demo(url)
    print(f"Demo de punta a punta (entrega 1) contra {url}\n")
    try:
        await demo.recorrer()
    except (FalloDemo, httpx.HTTPError) as error:
        print(f"[{demo.tiempo()}] ✘ {error}")
        return 1
    finally:
        await demo.cerrar()
    tipos: dict[str, int] = {}
    for tipo, _ in demo.eventos:
        tipos[tipo] = tipos.get(tipo, 0) + 1
    print(f"\nEventos SSE recibidos: {tipos}")
    print(f"Listo: {len(demo.pasos)} pasos en {demo.tiempo().strip()}.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8010", help="URL base de la API (por defecto %(default)s)")
    argumentos = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(principal(argumentos.url)))


if __name__ == "__main__":
    main()
