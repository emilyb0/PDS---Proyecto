# Sistema centralizado de robots y drones — prototipo (entrega 1)

Proyecto final de *Procesos y Diseño de Software*. Una universidad tiene 6 dispositivos (robots que transportan documentos y pedidos de cafetería; drones que graban eventos) y necesita un sistema web que los reserve, los monitoree en tiempo real, registre la bitácora de cada servicio y guarde los videos en la nube. El demo es solo software: los dispositivos se simulan (RESTR01).

**Este repositorio es la entrega 1:** el núcleo del backend con 12 de los 27 RF. Los otros 15 están pendientes y se agregan como módulos. Qué está hecho, qué falta y cómo seguir: `docs/como-continuar.md`.

## Documentos (leer antes de cambiar algo)

| Archivo | Qué es |
|---|---|
| `docs/requisitos.md` | RF01–RF27, RNF01–RNF10, RESTR01–RESTR04 (SRS del equipo). **Manda sobre todo lo demás** |
| `docs/modelo/esquema_bd.sql` | Esquema PostgreSQL 16 probado: tablas, CHECK, EXCLUDE, triggers, función de reporte. **Fuente de verdad de la BD** |
| `docs/especificacion-backend.md` | Reglas exactas de los 27 RF, estados, API, SSE, simulador, tareas, semilla y pruebas |
| `docs/modelo/diagrama_clases.puml` | Diagrama de clases (PlantUML). Nombres de clases e interfaces a respetar |
| `docs/modelo/diagrama_secuencia.mmd` | Flujo de reserva y servicio, 69 pasos (Mermaid) |
| `docs/modelo/diagrama_bd.mmd` | Vista ER derivada del SQL (solo referencia) |
| `docs/como-continuar.md` | Para el equipo: qué está hecho, qué falta (con la sección de la especificación de cada RF), cómo levantar el proyecto y cómo implementar un RF pendiente, con un prompt de ejemplo |
| `docs/decisiones.md` | Decisiones tomadas durante la construcción, con el porqué (mantenerlo) |
| `docs/trazabilidad.md` | RF → endpoints → clases → pruebas; los pendientes con su sección de la especificación (mantenerlo) |
| `docs/plan.md` | Plan aprobado en la Fase 0 del proyecto completo (estructura, simulador, monitor, tareas, librerías) |
| `docs/guia-frontend.md` | Contrato de la API para el frontend: formatos, errores, roles, endpoints, SSE. **Mantenerlo igual al código** |
| `docs/arquitectura.md` | Núcleo y módulos, puntos de extensión, `MODULOS_ACTIVOS`, cómo agregar o quitar un módulo. **Mantenerla al día** |
| `docs/demo.md` | Guion de la demo paso a paso (con `README.md`, `backend/tests/http/api.http` y `backend/scripts/demo_e2e.py`) |

Si dos documentos se contradicen, manda el que está más arriba en la tabla. Si la contradicción cambia el comportamiento y no se resuelve así, pregunta.

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2 async + psycopg 3 · Alembic · PostgreSQL 16 · Pydantic v2 · JWT · SSE · pytest · ruff · Docker Compose. El equipo trabaja en **Windows con PowerShell y Docker Desktop**.

## Reglas de oro

- **Esquema:** la migración 0001 ejecuta `esquema_bd.sql` tal cual. No se edita; los cambios van en migraciones nuevas. Nunca `create_all`.
- **Nada de SQLite**, ni en pruebas: el esquema usa EXCLUDE, TSRANGE, ENUM y triggers de PostgreSQL.
- **Hora:** todo en America/Bogota (TIMESTAMP sin zona), con la sesión de PostgreSQL en esa zona. Nadie llama a `datetime.now()`: se usa el `Reloj` inyectable.
- **Un proceso:** Uvicorn con 1 worker (simulador, monitor y SSE viven en memoria).
- **Nombres:** clases como en el diagrama (`GestorReservas`, `MonitorServicios`, `GestorVideos`, `IApiDispositivo`, `ApiDispositivoSimulada`, `IServicioClima`, `IAlmacenamientoCloud`); métodos en snake_case. Dominio, mensajes y comentarios en español.
- **Reglas de negocio:** se validan en el servicio con mensajes claros, y la BD es la última barrera. Los errores de PostgreSQL se traducen como indica la especificación (sección 4).
- **Auditoría (RNF09):** cada creación, edición o baja hecha por un usuario va en la misma transacción.
- **Pruebas:** cada RF tiene al menos una prueba `test_rfXX_...`. Ninguna prueba sale a internet (clima, almacenamiento y dispositivo usan adaptadores falsos).
- **Secretos:** nunca en el repositorio; solo `.env.example`.
- **Al terminar un RF o un cambio:** pruebas en verde (también `pytest --solo-entrega-1`), ruff limpio, actualizar este archivo (comandos y estado), `docs/trazabilidad.md`, `docs/decisiones.md`, `docs/guia-frontend.md` y `docs/arquitectura.md`, y hacer un commit.

## Entregas: núcleo y módulos por RF

El sistema tiene 27 RF y se entrega en dos partes:

- **Entrega 1, el núcleo (12 RF, hecha):** RF01, RF04, RF05, RF06, RF07, RF08, RF09, RF10, RF11, RF12, RF18 y RF20,
  más la infraestructura, los RNF y las restricciones.
- **Entrega 2, los módulos (15 RF, pendientes):** RF02, RF03, RF13, RF14, RF15, RF16, RF17, RF19, RF21, RF22,
  RF23, RF24, RF25, RF26 y RF27. La tabla de `docs/como-continuar.md` dice, para cada uno, dónde empieza en la
  especificación, en qué carpeta va, en qué puntos de extensión se engancha y qué decisiones ya lo afectan.

Reglas:

1. **Una carpeta por RF removible:** `backend/app/modulos/rfXX_nombre/`. Ahí van sus routers, servicios, tareas,
   verificaciones del monitor, controles de demo, chequeos de salud y funciones de menú. El paquete expone
   `MODULO = ModuloRF(...)` y se descubre solo (`app/modulos/__init__.py`): no hay que registrarlo en ningún otro
   archivo.
2. **El núcleo nunca importa `app.modulos.rfXX…`.** Los módulos se enganchan a los puntos de extensión del núcleo
   (`app/nucleo/extensiones.py`): validadores de reserva, verificaciones del monitor, manejadores de eventos del
   dispositivo, ajustes de la orden de inicio, acciones al cerrar un servicio, tareas programadas, tareas y eventos
   de demo, chequeos de `/health`, funciones de menú y evaluador de clima. Un módulo puede importar el núcleo.
   Entre módulos, la dependencia es opcional y pasa por las extensiones; un módulo no importa otro.
3. **Pruebas separadas:** las del núcleo están en `backend/tests/` (fuera de `tests/modulos/`) y corren con
   **todos los módulos apagados**. Las de cada módulo van en `backend/tests/modulos/rfXX_nombre/` y corren con
   todos los módulos encendidos (`tests/modulos/conftest.py`). `pytest --solo-entrega-1` corre solo el núcleo:
   esa es la prueba de que los 12 no dependen de los 15. Los chequeos de permisos (RNF01) y auditoría (RNF09) de
   cada módulo van en sus propias pruebas, no en las del núcleo. `tests/unitarias/test_modulos.py` vigila estas
   reglas.
4. **Quitar un módulo** = borrar `app/modulos/rfXX_nombre/` y `tests/modulos/rfXX_nombre/`, y sus filas en
   `docs/trazabilidad.md` y `docs/guia-frontend.md`. Para apagarlo sin borrar código: `MODULOS_ACTIVOS` en el
   `.env` (`todos` por defecto, `ninguno` para solo el núcleo, o una lista como `rf02,rf03`).
5. **Excepciones que impone el esquema:**
   - Los modelos de las 18 tablas siguen en el núcleo, porque el esquema es literal.
   - El código de entrega de 4 dígitos se genera en el núcleo al crear la reserva de un robot, porque el
     trigger `fn_validar_reserva` lo exige. RF24 aportará la espera del robot y la confirmación del código.
6. **El frontend** sabe qué hay con `requisitos_activos` y `funciones`, que devuelven `POST /api/auth/login` y
   `GET /api/auth/yo`.

## Comandos

PowerShell, desde la raíz del proyecto (salvo donde dice `backend/`).

Puertos de la máquina (todos en `.env`): base en `localhost:5433` (`PUERTO_BD`), API en `http://localhost:8010`
(`PUERTO_API`), publicados solo en `127.0.0.1` (`IP_PUBLICACION`). El proyecto Compose se llama `robots-drones`
(o el valor de `COMPOSE_PROJECT_NAME` en el `.env`) y no fija `container_name`, así que convive con otros
proyectos Docker. Dentro de Docker la API usa `db:5432`; lo que corre en la máquina (uvicorn, pytest, alembic)
arma solo `127.0.0.1:PUERTO_BD`.

```powershell
# Primera vez: configuración local (no se sube al repositorio). No hace falta cambiar nada.
Copy-Item .env.example .env

# Levantar base y API (la API aplica las migraciones al arrancar). Docs en http://localhost:8010/docs
docker compose up --build -d
docker compose logs -f api

# Migrar a mano / ver la versión
docker compose exec api alembic upgrade head
docker compose exec api alembic current

# Sembrar datos de demo (usuarios en el README)
docker compose exec api python -m app.semilla              # idempotente
docker compose exec api python -m app.semilla --reiniciar  # borra datos y videos y vuelve a sembrar
docker compose restart api                                 # después de --reiniciar (el simulador vuelve a leer)

# Recorrer el flujo de los 12 RF contra la API levantada (necesita la semilla y MODO_DEMO=true)
docker compose exec api python scripts/demo_e2e.py --url http://localhost:8000

# Pruebas y lint dentro del contenedor (usan la base robots_test, que se recrea en cada corrida)
docker compose exec api pytest                             # núcleo (módulos apagados) + cada módulo (encendidos)
docker compose exec api pytest --solo-entrega-1            # solo el núcleo: prueba que los 12 RF no dependen de los módulos
docker compose exec api pytest --lentas                    # incluye la prueba lenta de RNF02 (~20 s)
docker compose exec api ruff check .
docker compose exec api ruff format --check .

# Sin Docker para la API (Windows, Python 3.12 con uv), desde backend/; la base sigue en Compose
uv sync
uv run pytest
uv run pytest --solo-entrega-1
uv run ruff check .
uv run python -m app                                       # API en http://127.0.0.1:8010 (antes: docker compose stop api)

# Regenerar el video de muestra del simulador (solo si cambia el script), desde backend/
uv sync --group video
uv run python scripts/generar_video_muestra.py

# Apagar los módulos (cuando existan): en .env, MODULOS_ACTIVOS=ninguno, y recrear la API
docker compose up -d api

# Detener
docker compose down        # conserva los datos
docker compose down -v     # borra la base y los videos
```

## Estado

> Actualizar al terminar cada RF: qué está hecho, qué falta y cualquier problema abierto.

- **Entrega 1 (2026-11-08):** hecha. El backend se construyó completo en las fases 0 a 5 (historial en
  `docs/decisiones.md`); este repositorio tiene solo el núcleo.
  - Base: Docker Compose, Alembic 0001 (copia literal de `esquema_bd.sql`), modelos de las 18 tablas, `Reloj`,
    errores, JWT, Argon2id, auditoría (RNF09) y `/health`.
  - RF18 y RF20 (usuarios y sesión), RF01 y RF04 (inventario), RF05–RF07 (`GestorReservas`: cruce de horarios con
    la reserva en conflicto, batería y sensores consultados en ese momento y código de entrega para robots).
  - RF08–RF12 (`MonitorServicios`): inicio automático, monitoreo en paralelo cada 5 s, SSE, alertas de batería,
    sensor y retraso sin duplicados, bitácora con ruta e incidencias, cierre con video (local o S3, con carpeta de
    pendientes y reintento) y reanudación tras un reinicio.
  - Simulador completo (también las órdenes, la espera del código y la salida de zona que usarán los módulos),
    semilla solo con datos de la entrega 1, controles de demo del núcleo, `scripts/demo_e2e.py`,
    `tests/http/api.http` y `docs/demo.md`.
  - 187 pruebas en verde con `--lentas` en el contenedor (más 1 omitida: la guarda de `.env.example`, que no se
    monta); ruff limpio. `--solo-entrega-1` da lo mismo porque aún no hay módulos.
- **Pendiente:** los 15 RF de la entrega 2 (tabla en `docs/como-continuar.md` y `docs/trazabilidad.md`).
- **Para validar con el cliente o el equipo:** RESTR04 con un bucket real de AWS (hoy los videos van a disco
  local por defecto), HTTPS en local (RNF05, hoy solo documentado), `MODO_DEMO=false` en producción y las
  coordenadas reales del campus (`backend/app/semilla.py`). Ver `docs/decisiones.md`, "Entrega 1".
