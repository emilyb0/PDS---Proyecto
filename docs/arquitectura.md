# Arquitectura del backend: núcleo y módulos

> Guía corta para el equipo. Explica cómo está organizado el código para entregar el sistema en dos partes y cómo
> agregar los RF que faltan. Se actualiza con cada módulo. Detalle técnico: `docs/decisiones.md` (M-1 a M-12) y la
> sección "Entregas" de `CLAUDE.md`. Paso a paso para el equipo: `docs/como-continuar.md`.

## 1. La idea

El sistema tiene 27 requisitos funcionales, pero se entrega en dos partes:

- **Entrega 1, el núcleo (este repositorio):** RF01, RF04, RF05, RF06, RF07, RF08, RF09, RF10, RF11, RF12, RF18 y
  RF20. Siempre está.
- **Entrega 2, los módulos (pendientes):** los otros 15 (RF02, RF03, RF13, RF14, RF15, RF16, RF17, RF19, RF21,
  RF22, RF23, RF24, RF25, RF26 y RF27). Cada uno será una pieza aparte que se puede encender, apagar o borrar.

La regla de oro: **el núcleo no conoce a los módulos**. Funciona solo. Los módulos se "enchufan" al núcleo; el
núcleo nunca los llama por su nombre.

```text
            ┌────────────────────────── núcleo (entrega 1) ──────────────────────────┐
            │ usuarios · dispositivos · reservas · monitoreo · bitácora · alertas    │
            │                                                                        │
            │   puntos de extensión  ◄── aquí se enchufan los módulos                │
            └────────▲──────────────▲───────────────▲────────────────────────────────┘
                     │              │               │
               ┌─────┴────┐   ┌─────┴─────┐   ┌─────┴─────┐
               │ RF23     │   │ RF16      │   │ RF25      │   … un paquete por RF (pendientes)
               │ clima    │   │ preventivo│   │ zona      │
               └──────────┘   └───────────┘   └───────────┘
```

## 2. Dónde está cada cosa

| Carpeta | Qué hay |
|---|---|
| `backend/app/` (salvo `modulos/`) | El núcleo: un paquete por tema (`usuarios`, `dispositivos`, `reservas`, `servicios`, `alertas`, `videos`, …) más `nucleo/` (base de datos, errores, seguridad, reloj, extensiones) |
| `backend/app/modulos/` | Hoy solo tiene `__init__.py`, que descubre los módulos. Cada RF pendiente agrega aquí su carpeta `rfXX_nombre/` |
| `backend/tests/` (salvo `modulos/`) | Pruebas del núcleo |
| `backend/tests/modulos/` | Hoy solo tiene `conftest.py`, que enciende los módulos en sus pruebas. Cada RF pendiente agrega aquí su carpeta `rfXX_nombre/` |

Nombres de carpeta sugeridos para los 15 pendientes (tabla completa en `docs/como-continuar.md`):
`rf02_editar_dispositivo`, `rf03_dar_de_baja`, `rf13_consultar_videos`, `rf14_ordenar_retorno`,
`rf15_mantenimiento`, `rf16_mantenimiento_preventivo`, `rf17_reportes`, `rf19_desactivar_usuario`,
`rf21_cancelar_reprogramar`, `rf22_sugerir_dispositivo`, `rf23_validar_clima`, `rf24_entrega_con_codigo`,
`rf25_salida_de_zona`, `rf26_eliminar_videos_vencidos` y `rf27_atender_alerta`.

Los modelos de las 18 tablas están siempre en el núcleo, porque la base de datos es una sola. Un módulo nuevo no
toca la base; si de verdad necesita un cambio de esquema, va en una migración nueva (nunca se edita la 0001).

El servicio en curso es del núcleo y funciona completo sin módulos: el inicio automático, el monitoreo cada 5 s, las
alertas de batería, sensor y retraso, el tiempo real (SSE) y el cierre con video. Lo hace `MonitorServicios`
(`app/servicios/monitor.py`), y el simulador de dispositivos está en `app/integraciones/dispositivo/`. Los módulos
solo agregan cosas en los puntos de extensión. Por ejemplo, RF24 se engancharía en tres:

1. `ajustes_orden_inicio`: pedirle al robot que espere el código en el destino (el simulador ya sabe esperar);
2. `manejadores_evento`: cuando alguien digita un código, compararlo con el de la reserva (el núcleo ya lo genera);
3. `verificaciones_monitor`: si pasan 5 minutos sin un código correcto, hacer que el robot regrese.

Mientras RF24 no exista, el robot deja el pedido y vuelve, y todo lo demás funciona igual.

## 3. Puntos de extensión

Están en `backend/app/nucleo/extensiones.py`. Un módulo los usa en su función `configurar`.

| Punto | Para qué sirve | Quién lo usaría |
|---|---|---|
| `routers` (en `ModuloRF`) | Agregar rutas a la API (también controles de demo propios, como el código de entrega de RF24) | casi todos |
| `validadores_reserva` | Agregar una validación al crear o reprogramar una reserva (después del cruce, la batería y los sensores) | RF23 (clima) |
| `evaluador_clima` | Dejar que otro módulo consulte el clima sin importar RF23 | RF23 lo registra; RF22 lo usa si existe |
| `al_finalizar_servicio` | Hacer algo cuando un servicio termina, en la misma transacción del cierre | RF16 (revisión preventiva) |
| `verificaciones_monitor` | Revisar cada lectura del monitoreo. Recibe un `ContextoMonitor` y puede agregar causas de alerta (el núcleo las guarda sin duplicados), campos al evento `telemetria` o acciones para después del *commit* | RF25 (salida de zona), RF24 (tiempo de espera del código) |
| `manejadores_evento` | Atender avisos del dispositivo distintos de la llegada a la base (esa la atiende el núcleo) | RF24 (código ingresado) |
| `ajustes_orden_inicio` | Cambiar la orden de salida del dispositivo | RF24 (el robot espera el código) |
| `tareas` | Tareas programadas; también se pueden lanzar desde la demo. El núcleo tiene las suyas: `iniciar-reservas` (10 s), `monitoreo` (5 s) y `reintento-subidas` (5 min) | RF16 (06:00), RF26 (02:00) |
| `eventos_demo` | Controles de demo propios del módulo (se suman a los del núcleo: batería, sensores, pausa) | RF25 (salir y volver a la zona) |
| `chequeos_salud` | Agregar una línea a `/health` | RF25 (`zona_operacion`) |
| `funciones` | Agregar opciones al menú del frontend | RF13, RF14, RF15, RF17, RF27 |
| `servicios` | Guardar objetos propios del módulo | RF23 (el servicio de clima) |

## 4. Encender o apagar módulos sin borrar código

En el archivo `.env`, la variable `MODULOS_ACTIVOS`:

```ini
MODULOS_ACTIVOS=todos            # por defecto: núcleo + todos los módulos que existan
MODULOS_ACTIVOS=ninguno          # solo el núcleo
MODULOS_ACTIVOS=rf15,rf16        # núcleo + solo esos módulos
```

Después de cambiarla hay que recrear la API: `docker compose up -d api`. Los módulos apagados desaparecen por
completo: sus rutas responden 404 (o 405 si comparten la dirección de una ruta del núcleo, como
`PATCH /api/dispositivos/{id}`) y no aparecen en `/docs`. El frontend sabe qué hay gracias a la lista
`requisitos_activos` que devuelven el login y `GET /api/auth/yo` (hoy, los 12 del núcleo).

## 5. Quitar un módulo para siempre

1. Borrar la carpeta `backend/app/modulos/rfXX_nombre/`.
2. Borrar la carpeta `backend/tests/modulos/rfXX_nombre/`.
3. En `docs/trazabilidad.md` y `docs/guia-frontend.md`, devolver el RF a la lista de pendientes (quitar sus
   endpoints de la guía y dejarlo en su sección 11).
4. Correr las pruebas (sección 7).

No hay que tocar ningún otro archivo: los módulos se descubren solos.

## 6. Agregar un módulo nuevo

1. Crear la carpeta `backend/app/modulos/rfXX_nombre/`. El nombre empieza por la clave del módulo (la carpeta
   `rf17_reportes` es del módulo con clave `rf17`), y los `requisitos` que declara deben ser de los 15
   pendientes: `test_modulos.py` revisa las dos cosas.
2. Escribir ahí la lógica y las rutas. Se puede importar todo el núcleo, pero **nunca otro módulo**.
3. En su `__init__.py`, declarar el módulo. Un ejemplo pequeño, con una ruta solo para el administrador, una opción
   de menú y una tarea diaria (cambie `rf17_reportes`, `RF17` y los nombres por los de su RF):

   ```python
   # backend/app/modulos/rf17_reportes/router.py
   from fastapi import APIRouter

   from app.nucleo.dependencias import Administrador, Sesion

   router = APIRouter(prefix="/api", tags=["Reportes"])


   @router.get("/reportes/ejemplo", summary="Ejemplo (RF17)", description="RF17. Qué hace, en una línea.")
   async def ejemplo(sesion: Sesion, _: Administrador) -> list[dict]:
       return []
   ```

   ```python
   # backend/app/modulos/rf17_reportes/__init__.py
   """RF17 — Generar reportes (entrega 2). Especificación, sección 7.7."""

   from typing import Any

   from app.config import Configuracion
   from app.modulos.rf17_reportes.router import router
   from app.nucleo.extensiones import Extensiones, ModuloRF, TareaProgramada


   async def _revisar(contenedor: Any) -> dict:  # tarea diaria; recibe el Contenedor
       return {"revisados": 0}


   def _configurar(extensiones: Extensiones, config: Configuracion) -> None:
       extensiones.agregar_funciones("reportes.ver", solo_administrador=True)  # opción de menú
       extensiones.tareas.append(TareaProgramada(nombre="revision-ejemplo", funcion=_revisar, tipo="diaria", hora=6))


   MODULO = ModuloRF(
       clave="rf17",
       requisitos=("RF17",),
       nombre="Generar reportes",
       routers=(router,),
       configurar=_configurar,
   )
   ```

   Las dependencias de FastAPI (`Sesion`, `ContenedorDep`, `UsuarioActual`, `Administrador`, `Paginacion`,
   `ModoDemo`) están en `app/nucleo/dependencias.py`. Copie el estilo de un router del núcleo, por ejemplo
   `app/dispositivos/router.py`.
4. Crear sus pruebas en `backend/tests/modulos/rfXX_nombre/` (obligatorio: una prueba lo verifica). Ahí los módulos
   están encendidos y sirven las mismas fixtures del núcleo (`cliente`, `contenedor`, `admin`, `operador`, `auth`,
   `reloj`). Por ejemplo:

   ```python
   # backend/tests/modulos/rf17_reportes/test_rf17_reportes.py  (y un __init__.py vacío en la carpeta)
   async def test_rf17_solo_el_administrador(cliente, admin, operador, auth) -> None:
       assert (await cliente.get("/api/reportes/ejemplo", headers=auth(admin))).status_code == 200
       assert (await cliente.get("/api/reportes/ejemplo", headers=auth(operador))).status_code == 403  # RNF01
   ```

   Incluya los casos del RF, los permisos (RNF01) y la auditoría (RNF09) si el módulo crea, edita o da de baja algo.
5. Pasar su fila de `docs/trazabilidad.md` a ✅, agregar sus endpoints a `docs/guia-frontend.md` (y sacarlo de
   su sección 11) y actualizar la columna "Quién lo usaría" de la sección 3 de este archivo.

## 7. Correr las pruebas

Dentro de Docker (desde la raíz del proyecto):

```powershell
docker compose exec api pytest                    # todo: núcleo (con módulos apagados) + cada módulo
docker compose exec api pytest --solo-entrega-1   # solo el núcleo
```

Sin Docker, desde `backend/`: `uv run pytest` y `uv run pytest --solo-entrega-1`.

- **`--solo-entrega-1`** corre solo las pruebas del núcleo, con todos los módulos apagados. Si pasa, el núcleo
  funciona sin los módulos. Hoy da lo mismo que `pytest`, porque aún no hay módulos.
- **`tests/unitarias/test_modulos.py`** vigila la regla de oro. Falla si:
  - el núcleo importa un módulo;
  - un módulo importa otro;
  - las pruebas de un módulo importan otro módulo;
  - un módulo no tiene carpeta de pruebas;
  - un módulo declara un RF que no es de la entrega 2.

## 8. En pocas palabras

- ¿Es de la entrega 1? Ya está en el núcleo.
- ¿Es uno de los 15 pendientes? Va en `app/modulos/rfXX_nombre/`.
- ¿El núcleo necesita "avisarle" algo a un módulo? Se agrega un punto de extensión en `nucleo/extensiones.py`;
  nunca un import del módulo.
