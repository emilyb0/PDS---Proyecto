# Sistema centralizado de robots y drones — backend (entrega 1)

Prototipo del proyecto final de *Procesos y Diseño de Software*. Una universidad tiene robots que transportan
documentos y pedidos de cafetería, y drones que graban eventos. Este backend los **reserva**, los **monitorea en
tiempo real**, registra la **bitácora** de cada servicio y guarda sus **videos**. Los dispositivos se simulan
(RESTR01), así que todo corre en un computador con Docker.

**Esta es la entrega 1: 12 de los 27 requisitos funcionales.** Los otros 15 se agregarán como módulos.
👉 **Si va a continuar el proyecto, empiece por [`docs/como-continuar.md`](docs/como-continuar.md).**

- API REST con FastAPI y documentación interactiva en `http://localhost:8010/docs`.
- Monitoreo en tiempo real por SSE cada ≤ 5 s, alertas de servicio, bitácora y videos MP4.
- PostgreSQL 16, simulador de dispositivos, datos semilla y controles para la demo.
- El frontend no está en este repositorio; la API está lista para él (ver `docs/guia-frontend.md`).

## 1. Qué incluye esta entrega

| Implementados (12) | Pendientes (15) |
|---|---|
| RF01 registrar dispositivo · RF04 consultar inventario · RF05 crear reserva · RF06 validar cruce de horarios · RF07 validar batería y sensores · RF08 bitácora del servicio · RF09 monitorear dispositivos · RF10 actualizar monitoreo · RF11 alertas de servicio · RF12 almacenar video · RF18 registrar usuario · RF20 iniciar sesión | RF02 editar dispositivo · RF03 dar de baja · RF13 consultar videos · RF14 ordenar retorno o parada · RF15 registrar mantenimiento · RF16 mantenimiento preventivo · RF17 reportes · RF19 desactivar usuario · RF21 cancelar o reprogramar · RF22 sugerir dispositivo · RF23 validar clima · RF24 entrega con código · RF25 salida de zona · RF26 eliminar videos vencidos · RF27 atender alerta |

Además: los requisitos no funcionales y las restricciones que dependen del núcleo (permisos por rol, tiempo real,
contraseñas con Argon2id, auditoría, `/health`, almacenamiento en S3). Dónde empieza cada RF en la especificación:
`docs/como-continuar.md`. Cada requisito con sus pruebas: `docs/trazabilidad.md`.

## 2. Requisitos

- Windows 10/11 con **Docker Desktop** encendido y **PowerShell**.
- Opcional, para correr las pruebas sin Docker: [uv](https://docs.astral.sh/uv/) (instala Python 3.12 solo).

## 3. Puesta en marcha (5 minutos)

En PowerShell, desde la carpeta del proyecto:

```powershell
# 1. Configuración local (solo la primera vez). No hace falta cambiar nada para desarrollar.
Copy-Item .env.example .env

# 2. Levantar la base de datos y la API (la API aplica las migraciones al arrancar)
docker compose up --build -d

# 3. Cargar los datos de la demo (usuarios, dispositivos, campus de ejemplo, historial y reservas)
docker compose exec api python -m app.semilla

# 4. Comprobar que todo está bien
Invoke-RestMethod http://localhost:8010/health
```

Abra **http://localhost:8010/docs**, use `POST /api/auth/login` con un usuario de prueba, copie el `token` y péguelo
en el botón **Authorize**.

Para ver el flujo completo funcionando (reserva → servicio → alerta → cierre con video), con la API arriba:

```powershell
docker compose exec api python scripts/demo_e2e.py --url http://localhost:8000
```

### Usuarios de prueba

| Correo | Contraseña | Rol |
|---|---|---|
| `admin@campus.edu.co` | `Admin123*` | Administrador |
| `operador1@campus.edu.co`, `operador2@…`, `operador3@…` | `Operador123*` | Operador |

Son contraseñas solo para desarrollo. El dominio `campus.edu.co` es de ejemplo.

### Qué trae la semilla

- 4 robots (`R-001`…`R-004`) y 2 drones (`D-001`, `D-002`). `R-003` tiene la batería baja y `R-004` el LIDAR en
  falla (sirven para mostrar RF07).
- Un **campus de ejemplo** con 8 ubicaciones. **Las coordenadas son inventadas**: hay que reemplazarlas por las del
  campus real (están en `backend/app/semilla.py`).
- 25 servicios terminados en los últimos 4 meses, con ruta, incidencias, 3 alertas de servicio y sus videos, y
  reservas programadas para hoy y mañana.

`python -m app.semilla` no hace nada si ya hay datos. Para empezar de cero:

```powershell
docker compose exec api python -m app.semilla --reiniciar
docker compose restart api      # el simulador vuelve a leer los dispositivos
```

## 4. Comandos frecuentes

```powershell
docker compose logs -f api                      # ver el log de la API
docker compose exec api alembic current         # versión de la base
docker compose restart api                      # reiniciar la API (los servicios abiertos se reanudan)
docker compose down                             # detener (conserva los datos)
docker compose down -v                          # detener y BORRAR la base y los videos de este proyecto
```

### Pruebas

Las pruebas usan PostgreSQL real (una base `robots_test` que se crea y se borra en cada corrida) y nunca salen a
internet: el almacenamiento (S3 con `moto`) y los dispositivos son simulados.

```powershell
docker compose exec api pytest                   # todo (~2 min)
docker compose exec api pytest --solo-entrega-1  # solo el núcleo (hoy es lo mismo: aún no hay módulos)
docker compose exec api pytest --lentas          # incluye la prueba de tiempo real de RNF02 (~20 s más)
docker compose exec api ruff check .             # estilo
docker compose exec api ruff format --check .
```

Sin Docker para la API (la base sigue en Docker), desde `backend/`:

```powershell
uv sync
uv run pytest
uv run python -m app          # API en http://127.0.0.1:8010 (antes: docker compose stop api)
```

### Probar la API a mano

- `http://localhost:8010/docs` (Swagger).
- `backend/tests/http/api.http`: las peticiones listas para la extensión **REST Client** de VS Code.
- `docs/demo.md`: guion de la demo paso a paso.

## 5. Núcleo y módulos

El código está organizado para crecer sin tocar lo que ya funciona. Lo de esta entrega es el **núcleo**
(`backend/app/`). Cada RF pendiente se agrega como un **módulo** en `backend/app/modulos/rfXX_nombre/`, que se
descubre solo y se engancha al núcleo por puntos de extensión; el núcleo nunca importa un módulo. Una vez existan,
los módulos se apagan sin borrar código con `MODULOS_ACTIVOS` en el `.env`:

```ini
MODULOS_ACTIVOS=todos            # por defecto
MODULOS_ACTIVOS=ninguno          # solo el núcleo
MODULOS_ACTIVOS=rf15,rf16        # núcleo + esos módulos
```

Cómo crear un módulo: `docs/como-continuar.md` (paso a paso, con un prompt de ejemplo para Claude Code) y
`docs/arquitectura.md` (detalle técnico).

## 6. Configuración (`.env`)

Todas las variables están explicadas en `.env.example`. Las más usadas:

| Variable | Por defecto | Para qué |
|---|---|---|
| `PUERTO_BD` / `PUERTO_API` | `5433` / `8010` | Puertos en la máquina (dentro de Docker la API usa `db:5432`) |
| `COMPOSE_PROJECT_NAME` | sin definir (`robots-drones`) | Nombre del proyecto Docker. Defínalo, junto con otros puertos, si corre dos copias del sistema en la misma máquina |
| `JWT_SECRETO` | valor de ejemplo | Firma de los tokens. **Cámbielo** fuera de desarrollo |
| `MODO_DEMO` | `true` | Habilita `/api/demo/...` (solo administrador). En producción, `false` |
| `TAREAS_ACTIVAS` | `true` | Inicio automático de reservas, monitoreo y reintento de subidas |
| `ALMACENAMIENTO` | `local` | `s3` para guardar los videos en AWS S3 (RESTR04) |
| `RETRASO_ALERTA_MIN` | `10` | Bájelo a `1` para mostrar la alerta de retraso en la demo |
| Parámetros de negocio | sección 6 de la especificación | Batería mínima y umbrales de alerta; también los de los RF pendientes (clima, mantenimiento, retención, código) |

### Videos en AWS S3 (RESTR04)

En desarrollo los videos van a un volumen de Docker. Para la demo con AWS (capa gratuita):

1. En la consola de AWS, cree un bucket **privado** (deje activado "Bloquear todo el acceso público").
2. Cree un usuario IAM solo para este sistema, con una política limitada a ese bucket:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       { "Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": "arn:aws:s3:::NOMBRE-DEL-BUCKET" },
       { "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
         "Resource": "arn:aws:s3:::NOMBRE-DEL-BUCKET/*" }
     ]
   }
   ```

3. Cree una clave de acceso para ese usuario y póngala en el `.env` (nunca en el repositorio):

   ```ini
   ALMACENAMIENTO=s3
   S3_BUCKET=NOMBRE-DEL-BUCKET
   S3_REGION=us-east-1
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   ```

4. `docker compose up -d api` y revise que `/health` diga `"almacenamiento": "ok"`. Vuelva a sembrar con
   `--reiniciar` para que los videos del historial suban al bucket.

El navegador nunca habla con S3. En esta entrega el video de cada servicio se ve como dato en la bitácora
(`GET /api/bitacoras/{id}`); reproducirlo con un enlace firmado es del RF13, pendiente.
`S3_ENDPOINT_URL` permite usar otro servicio compatible con S3.

## 7. Notas de operación

- **Un solo proceso.** El simulador, el monitor y el tiempo real (SSE) viven en memoria, así que Uvicorn corre con
  **un worker** (`--workers 1`). No lo aumente: cada worker tendría su propio simulador.
- **HTTPS (RNF05).** En local la API usa HTTP. Al desplegarla, póngala detrás de un proxy inverso con HTTPS y no
  publique el puerto de la base de datos. Ejemplo con Caddy, que obtiene el certificado solo:

  ```text
  api.su-dominio.edu.co {
      reverse_proxy 127.0.0.1:8010
  }
  ```

  Ajuste `CORS_ORIGENES` al dominio del frontend y use un `JWT_SECRETO` largo y aleatorio. Las contraseñas se
  guardan con Argon2id.
- **Disponibilidad (RNF06).** Compose reinicia los contenedores si fallan (`restart: unless-stopped`) y
  `GET /health` informa la base de datos, el almacenamiento y el simulador (503 si falla algo crítico). La meta de
  95 % de disponibilidad se cumple con un monitor externo que consulte `/health` y con el reinicio automático; en
  este prototipo local no se mide.
- **Reinicios.** Si la API se reinicia con servicios en curso, los dispositivos siguen desde su último punto.
- **Convive con otros proyectos Docker.** El proyecto Compose se llama `robots-drones` (o el de
  `COMPOSE_PROJECT_NAME`), no fija nombres de contenedores y publica los puertos solo en `127.0.0.1`. Si un puerto
  está ocupado, cámbielo en el `.env`.

## 8. Estructura

```text
docker-compose.yml        base de datos (PostgreSQL 16) + API
.env.example              configuración de ejemplo
docs/                     requisitos, modelo (SQL y diagramas), especificación, decisiones, guías
backend/
  app/                    el núcleo (entrega 1); app/modulos/ recibirá un paquete por RF pendiente
  migraciones/            Alembic; la 0001 es docs/modelo/esquema_bd.sql tal cual
  scripts/                demo_e2e.py y generar_video_muestra.py
  tests/                  pruebas del núcleo, tests/modulos/ (para las de cada módulo) y tests/http/api.http
```

## 9. Documentación

| Archivo | Para qué |
|---|---|
| `docs/como-continuar.md` | **Empiece aquí:** qué está hecho, qué falta y cómo agregar un RF pendiente |
| `docs/requisitos.md` | Requisitos (manda sobre todo lo demás) |
| `docs/especificacion-backend.md` | Reglas, estados, API, simulador y pruebas de los 27 RF |
| `docs/arquitectura.md` | Núcleo, módulos y puntos de extensión |
| `docs/guia-frontend.md` | Contrato de la API para el frontend |
| `docs/demo.md` | Guion de la demo paso a paso |
| `docs/decisiones.md` | Decisiones tomadas y por qué |
| `docs/trazabilidad.md` | Cada requisito con sus endpoints, clases y pruebas |

## 10. Problemas comunes

| Síntoma | Qué hacer |
|---|---|
| `docker compose up` dice que el puerto está ocupado | Cambie `PUERTO_BD` o `PUERTO_API` en el `.env` |
| `error during connect` al usar `docker` | Encienda Docker Desktop |
| `/health` dice `"simulador": "sin_base"` | Falta la ubicación base: cargue la semilla |
| Después de `--reiniciar` los dispositivos muestran datos viejos | `docker compose restart api` |
| El frontend (Vite) no conecta con un proxy a `localhost` | Apunte el proxy a `http://127.0.0.1:8010` |

## Frontend

Aplicación web (React + Vite + TypeScript) en `frontend/`. Con el backend arriba y la semilla cargada, en PowerShell:

```powershell
cd frontend
npm install        # solo la primera vez
npm run dev        # abre http://localhost:5173
```

Entre con `admin@campus.edu.co` / `Admin123*`. El proxy de Vite reenvía `/api` y `/health` a `http://127.0.0.1:8010`
(otra dirección: `$env:API_URL = 'http://127.0.0.1:XXXX'; npm run dev`). `npm run build` verifica los tipos y genera
`frontend/dist`. Pantallas, requisitos que cubre cada una y guion de la demo: [`docs/frontend.md`](docs/frontend.md).
Observaciones para el backend: [`docs/pendientes-backend.md`](docs/pendientes-backend.md).
