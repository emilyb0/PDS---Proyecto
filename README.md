# Sistema centralizado de robots y drones

Proyecto final de *Procesos y Diseño de Software*. Una universidad tiene robots que transportan documentos y pedidos
de cafetería, y drones que graban eventos. Esta plataforma web los **reserva**, los **monitorea en tiempo real** en
un mapa, genera **alertas**, registra la **bitácora** de cada servicio y guarda su **video**. Los dispositivos se
simulan (RESTR01), así que todo corre en un computador con Docker.

**Estado: versión final.** Están implementados los **12 requisitos funcionales** que pidió el profesor, con su
backend, su interfaz web y sus pruebas. Los otros 15 RF del documento de requisitos quedaron fuera del alcance.

## 1. Qué se implementó

| RF | Requisito | Dónde se ve en la interfaz |
|---|---|---|
| RF01 | Registrar dispositivo | Inventario → Registrar |
| RF04 | Consultar inventario | Inventario (filtros por tipo y estado, detalle) |
| RF05 | Crear reserva | Reservas → Nueva reserva (código de entrega de 4 dígitos para robots) |
| RF06 | Validar cruce de horarios | Nueva reserva: error `CRUCE_HORARIO` con la reserva en conflicto |
| RF07 | Validar batería y sensores | Nueva reserva: error `DISPOSITIVO_NO_APTO` con el motivo |
| RF08 | Registrar bitácora del servicio | Bitácoras: ruta en el mapa, reproducción, incidencias |
| RF09 | Monitorear dispositivos | Monitoreo: mapa del campus con la flota |
| RF10 | Actualizar el monitoreo en tiempo real | Monitoreo: una lectura cada 5 s por SSE |
| RF11 | Generar alertas de servicio | Alertas y avisos en cualquier pantalla (batería, sensor, retraso) |
| RF12 | Almacenar el video del servicio | Detalle de la bitácora (disco local o AWS S3) |
| RF18 | Registrar usuario | Usuarios |
| RF20 | Iniciar sesión | Login (token de 8 h, roles administrador y operador) |

También se cumplen los requisitos no funcionales y las restricciones que dependen de esto: permisos por rol (RNF01),
tiempo real en ≤ 5 s (RNF02), listados en < 3 s (RNF03), contraseñas con Argon2id (RNF05), `/health` y reinicio
automático (RNF06), **auditoría** de cada creación (RNF09), dispositivos sin límite fijo (RNF10), simulador
(RESTR01), API REST con SSE (RESTR02 y RESTR03) y almacenamiento en S3 (RESTR04). El detalle de cada requisito con
sus endpoints, clases y pruebas está en [`docs/trazabilidad.md`](docs/trazabilidad.md).

## 2. Cómo está armado

```text
Navegador ──► Frontend (React + Vite, puerto 5173)
                 │  /api y /health por el proxy de Vite
                 ▼
              API (FastAPI, puerto 8010) ──► PostgreSQL 16 (puerto 5433)
                 │  simulador de dispositivos, monitor cada 5 s, SSE
                 ▼
              Videos MP4 en un volumen de Docker o en AWS S3
```

- **Backend** (`backend/`): Python 3.12, FastAPI, SQLAlchemy 2 (async) y Alembic. El esquema de la base es
  `docs/modelo/esquema_bd.sql`, con triggers y una restricción `EXCLUDE` que impide cruces de horario. Un monitor
  revisa todos los dispositivos en paralelo cada 5 s, genera las alertas y publica los eventos por **SSE**.
- **Frontend** (`frontend/`): React 18, TypeScript, React Router y Leaflet. Tiene estética de "torre de control",
  modo claro y oscuro, y un mapa con íconos propios de robot y drone. Muestra cada pantalla según el rol y los
  requisitos activos que devuelve el login. Detalle: [`docs/frontend.md`](docs/frontend.md).
- **Docker Compose** levanta la base de datos y la API. El proyecto se llama `robots-drones` y publica los puertos
  solo en `127.0.0.1`.

## 3. Puesta en marcha (local, Windows + PowerShell)

Necesita **Docker Desktop** encendido y **Node.js 18 o superior**. Desde la carpeta del proyecto:

```powershell
# 1. Configuración (solo la primera vez; no hace falta cambiar nada)
Copy-Item .env.example .env

# 2. Base de datos y API (la API aplica las migraciones al arrancar)
docker compose up --build -d

# 3. Datos de la demo
docker compose exec api python -m app.semilla

# 4. Interfaz web
cd frontend
npm install          # solo la primera vez
npm run dev          # http://localhost:5173
```

- Interfaz web: **http://localhost:5173**.
- Documentación interactiva de la API (Swagger): **http://localhost:8010/docs**.
- Estado del sistema: `Invoke-RestMethod http://localhost:8010/health`.

### Usuarios

| Nombre | Correo | Contraseña | Rol |
|---|---|---|---|
| Emily Bonilla | `emily.bonilla@campus.edu.co` | `Admin123*` | Administradora |
| Santiago Figueroa | `santiago.figueroa@campus.edu.co` | `Operador123*` | Operador |

Son contraseñas de desarrollo. Los nuevos usuarios se registran desde la pantalla **Usuarios** con un correo
`@campus.edu.co`.

### Qué trae la semilla

La semilla es mínima a propósito, para que en la demostración se creen los datos en vivo:

- Los 2 usuarios de la tabla anterior. Se necesita al menos un operador porque toda reserva tiene un operador
  responsable.
- 6 dispositivos: 4 robots (`R-001` a `R-004`) y 2 drones (`D-001` y `D-002`). `R-003` tiene la batería en 28 % y
  `R-004` tiene el LIDAR en falla: sirven para mostrar los rechazos de RF07.
- Un campus de ejemplo con 8 ubicaciones (coordenadas inventadas cerca de Bogotá).
- 5 reservas: 3 servicios ya terminados con ruta, video y 2 alertas (una de sensor y otra de batería), y 2
  reservas programadas para mañana.
- La **auditoría empieza vacía**.

Para volver a ese estado antes de una presentación:

```powershell
docker compose exec api python -m app.semilla --reiniciar   # borra todos los datos y los videos
docker compose restart api                                  # el simulador vuelve a leer los dispositivos
```

## 4. Demostración

- **Con la interfaz web (≈ 10 min):** el guion está en [`docs/frontend.md`](docs/frontend.md). Recorre login por
  rol, inventario, una reserva con sus rechazos, el servicio moviéndose en el mapa, alertas provocadas desde el
  **Panel de demo**, el cierre con bitácora y video, y la auditoría.
- **Solo con la API:** [`docs/demo.md`](docs/demo.md) (Swagger o `backend/tests/http/api.http` con la extensión
  REST Client de VS Code).
- **Flujo automático de los 12 RF**, para comprobar que todo funciona (≈ 2 min):

  ```powershell
  docker compose exec api python scripts/demo_e2e.py --url http://localhost:8000
  ```

  El script deja una reserva más y su servicio. Después vuelva a sembrar con `--reiniciar`.

Para la demo conviene poner `RETRASO_ALERTA_MIN=1` en el `.env` (la alerta de retraso aparece al minuto) y
recrear la API con `docker compose up -d api`. Los controles de demo (`/api/demo/...` y el Panel de demo) existen
solo con `MODO_DEMO=true`, que viene por defecto.

## 5. Pruebas

Las pruebas usan PostgreSQL real (una base `robots_test` que se recrea en cada corrida) y nunca salen a internet.

```powershell
docker compose exec api pytest                  # 186 pruebas (~1 min)
docker compose exec api pytest --lentas         # incluye la prueba de tiempo real de RNF02
docker compose exec api ruff check .            # estilo
cd frontend; npm run build                      # verificación de tipos y build del frontend
```

## 6. Despliegue

### Backend en un servidor

1. Copie el proyecto a un servidor con Docker y cree el `.env` a partir de `.env.example`, con estos cambios:

   ```ini
   JWT_SECRETO=una-cadena-larga-y-aleatoria
   MODO_DEMO=false                         # oculta los controles de demo
   CORS_ORIGENES=https://su-frontend.edu.co
   ```

2. `docker compose up --build -d` y `docker compose exec api python -m app.semilla`.
3. Ponga la API detrás de HTTPS (RNF05) con un proxy inverso y no publique el puerto de la base. Con Caddy, que
   obtiene el certificado solo:

   ```text
   api.su-dominio.edu.co {
       reverse_proxy 127.0.0.1:8010
   }
   ```

La API corre con **un solo worker** a propósito: el simulador, el monitor y el SSE viven en memoria. No lo aumente.

### Frontend

El frontend es un sitio estático. Se compila indicando dónde está la API:

```powershell
cd frontend
$env:VITE_API_URL = 'https://api.su-dominio.edu.co'
npm run build        # genera frontend/dist
```

`frontend/dist` se puede publicar en cualquier hosting estático (Vercel, Netlify, GitHub Pages o el mismo Caddy).
En Vercel o Netlify configure la redirección de todas las rutas a `index.html`, porque la aplicación usa rutas del
navegador. El backend debe estar publicado con HTTPS y con el dominio del frontend en `CORS_ORIGENES`.

### Videos en AWS S3 (RESTR04)

Por defecto los videos se guardan en un volumen de Docker. Para usar S3:

1. Cree un bucket **privado** y un usuario IAM con permisos solo sobre ese bucket (`s3:ListBucket` en el bucket;
   `s3:GetObject`, `s3:PutObject` y `s3:DeleteObject` en `NOMBRE-DEL-BUCKET/*`).
2. En el `.env` (nunca en el repositorio):

   ```ini
   ALMACENAMIENTO=s3
   S3_BUCKET=NOMBRE-DEL-BUCKET
   S3_REGION=us-east-1
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   ```

3. `docker compose up -d api` y revise que `/health` diga `"almacenamiento": "ok"`.

## 7. Configuración (`.env`)

Todas las variables están explicadas en `.env.example`. Las más usadas:

| Variable | Por defecto | Para qué |
|---|---|---|
| `PUERTO_BD` / `PUERTO_API` | `5433` / `8010` | Puertos en la máquina |
| `JWT_SECRETO` | valor de ejemplo | Firma de los tokens. **Cámbielo** fuera de desarrollo |
| `MODO_DEMO` | `true` | Controles de demo (solo el administrador). En producción, `false` |
| `ALMACENAMIENTO` | `local` | `s3` para guardar los videos en AWS |
| `RETRASO_ALERTA_MIN` | `10` | Minutos de retraso para la alerta; `1` para la demo |
| `CORS_ORIGENES` | `http://localhost:5173` | Dominios desde los que se puede llamar a la API |

## 8. Comandos frecuentes

```powershell
docker compose logs -f api        # log de la API
docker compose restart api        # reiniciar la API (los servicios en curso continúan)
docker compose down               # detener (conserva los datos)
docker compose down -v            # detener y BORRAR la base y los videos
```

## 9. Estructura

```text
docker-compose.yml     base de datos y API
.env.example           configuración de ejemplo
backend/
  app/                 código de la API (usuarios, dispositivos, reservas, servicios, alertas, videos, auditoría)
  migraciones/         Alembic; la 0001 es docs/modelo/esquema_bd.sql tal cual
  scripts/             demo_e2e.py (flujo automático) y generar_video_muestra.py
  tests/               pruebas y tests/http/api.http
frontend/
  src/                 páginas, mapa, sesión y permisos, tiempo real y cliente de la API
docs/                  requisitos, modelo (SQL y diagramas), especificación y guías
```

## 10. Documentación

| Archivo | Para qué |
|---|---|
| [`docs/requisitos.md`](docs/requisitos.md) | Requisitos del sistema (RF, RNF y restricciones) |
| [`docs/trazabilidad.md`](docs/trazabilidad.md) | Cada requisito con sus endpoints, clases y pruebas |
| [`docs/frontend.md`](docs/frontend.md) | Frontend: diseño, pantallas por requisito y guion de la demo |
| [`docs/guia-frontend.md`](docs/guia-frontend.md) | Contrato de la API: formatos, errores, roles, endpoints y SSE |
| [`docs/demo.md`](docs/demo.md) | Guion de la demo solo con la API |
| [`docs/especificacion-backend.md`](docs/especificacion-backend.md) | Reglas de negocio, estados, simulador y tareas |
| [`docs/arquitectura.md`](docs/arquitectura.md) | Organización del backend (núcleo y módulos) |
| [`docs/decisiones.md`](docs/decisiones.md) | Decisiones tomadas y por qué |
| `docs/modelo/` | Esquema SQL y diagramas de clases, secuencia y base de datos |

## 11. Problemas comunes

| Síntoma | Qué hacer |
|---|---|
| `error during connect` al usar `docker` | Encienda Docker Desktop |
| El puerto está ocupado | Cambie `PUERTO_BD` o `PUERTO_API` en el `.env` |
| La interfaz dice "No hay conexión con el servidor" | Revise que la API esté arriba: `docker compose ps` |
| `/health` dice `"simulador": "sin_base"` | Falta cargar la semilla |
| Después de `--reiniciar` el mapa muestra datos viejos | `docker compose restart api` |
| El mapa sale sin calles | Las teselas de OpenStreetMap necesitan internet; los dispositivos se ven igual |
| `npm run dev` dice que el puerto 5173 está ocupado | Cierre la otra ventana de `npm run dev` |
