# Plan del backend — Fase 0

> Plan para construir el backend del prototipo. Se basa en `requisitos.md`, `esquema_bd.sql`,
> `especificacion-backend.md` y los diagramas. Las decisiones que tome durante la construcción
> se anotarán en `decisiones.md`. Este archivo no se actualiza fase a fase: es el plan aprobado.
>
> **Nota de la entrega 1:** es el plan del proyecto completo (27 RF), que se construyó entero. Este repositorio
> tiene solo el núcleo (12 RF); lo que el plan dice de los módulos de la entrega 2 sigue pendiente. Estado
> actual: `docs/como-continuar.md` y `CLAUDE.md`.

## 1. Estructura de carpetas y correspondencia con el diagrama de clases

```text
proyecto-robots-drones/
├─ docker-compose.yml            db (postgres:16) + api; restart: unless-stopped
├─ .env.example                  todas las variables con valores de desarrollo (sin secretos reales)
├─ README.md                     en español, con comandos de PowerShell
├─ docs/                         requisitos, modelo, especificación, plan, decisiones, trazabilidad, demo
└─ backend/
   ├─ Dockerfile                 python:3.12-slim; etapa "dev" con herramientas de prueba
   ├─ pyproject.toml / uv.lock   dependencias fijadas, configuración de ruff y pytest
   ├─ alembic.ini
   ├─ migraciones/
   │  ├─ env.py                  Alembic en modo async, sesión en America/Bogota
   │  ├─ sql/0001_esquema_bd.sql copia literal de docs/modelo/esquema_bd.sql
   │  └─ versions/0001_esquema_inicial.py   ejecuta ese archivo tal cual
   ├─ app/
   │  ├─ main.py                 crear_app(contenedor) + lifespan (simulador, monitor, tareas)
   │  ├─ config.py               Configuracion (pydantic-settings): parámetros de la sección 6
   │  ├─ contenedor.py           arma e inyecta reloj, adaptadores, bus de eventos y gestores
   │  ├─ semilla.py              python -m app.semilla [--reiniciar]
   │  ├─ nucleo/                 bd, errores (+ traducción SQLSTATE), seguridad (Argon2, JWT, HMAC),
   │  │                          dependencias (usuario actual, roles), paginacion, eventos (BusEventos SSE),
   │  │                          reloj (Reloj, RelojSistema, RelojSimulado), registro (logs sin token)
   │  ├─ dominio/                reglas puras sin BD: umbrales, punto en polígono, distancias,
   │  │                          tipo requerido por servicio, suma de meses de calendario
   │  ├─ usuarios/               Usuario (rol ADMINISTRADOR/OPERADOR) · login, /yo, CRUD de usuarios
   │  ├─ auditoria/              RegistroAuditoria · registrar_auditoria() y consulta
   │  ├─ dispositivos/           Dispositivo, Robot, Drone, Sensor · RF01–RF04
   │  ├─ mantenimiento/          Mantenimiento · RF15 y alerta preventiva RF16
   │  ├─ ubicaciones/            Ubicacion, ZonaOperacion (+ VerticeZona) · catálogo y polígono
   │  ├─ reservas/               Reserva, GestorReservas · RF05–RF07, RF21–RF24
   │  ├─ servicios/              BitacoraServicio, RegistroTelemetria, LecturaSensor, Incidencia,
   │  │                          MonitorServicios · RF08–RF11, RF14, RF24, RF25, monitoreo y SSE
   │  ├─ alertas/                Alerta, AlertaServicio, AlertaMantenimiento, AtencionAlerta · RF11, RF16, RF27
   │  ├─ videos/                 Video, GestorVideos, enlaces firmados y Range · RF12, RF13, RF26
   │  ├─ reportes/               ReporteDispositivo (usa reporte_dispositivo()) · RF17
   │  ├─ integraciones/
   │  │  ├─ dispositivo/         IApiDispositivo, ApiDispositivoSimulada, escenario.json, muestra.mp4
   │  │  ├─ clima/               IServicioClima, Pronostico, ServicioClimaOpenMeteo, ServicioClimaFalso
   │  │  └─ almacenamiento/      IAlmacenamientoCloud, AlmacenamientoS3, AlmacenamientoLocal
   │  ├─ tareas/                 planificador (APScheduler) y las 5 tareas de la sección 12
   │  └─ demo/                   controles de demo (solo con MODO_DEMO=true)
   ├─ scripts/
   │  ├─ demo_e2e.py             recorre el diagrama de secuencia contra la API levantada
   │  └─ generar_video_muestra.py genera muestra.mp4 (H.264, ≤ 1 MB) con PyAV; no descarga nada
   └─ tests/
      ├─ conftest.py             BD de prueba real (robots_test), migrada con Alembic y limpiada entre pruebas
      ├─ falsos.py / fabrica.py  adaptadores falsos y datos de prueba
      ├─ unitarias/              reglas puras
      ├─ integracion/            test_rfXX_*.py, test_rnfXX_*.py
      └─ http/api.http           colección de peticiones para VS Code / JetBrains
```

Cada módulo de dominio tiene `modelos.py` (SQLAlchemy), `esquemas.py` (Pydantic), `servicio.py` o el
gestor del diagrama, y `router.py`. Capas: router → servicio/gestor → modelos.

**Correspondencia con el diagrama de clases**

| Diagrama | Código | Nota |
|---|---|---|
| Usuario, Administrador, Operador | `usuarios.modelos.Usuario` con `rol` | Una clase con `es_administrador`; ver decisión D10 |
| Dispositivo, Robot, Drone | `Dispositivo` + subclases `Robot`, `Drone` | Herencia de tabla única de SQLAlchemy con `polymorphic_on=tipo` |
| Alerta, AlertaServicio, AlertaMantenimiento | Herencia *joined* de SQLAlchemy | Calza con "tabla por subclase (PK = FK)"; `AlertaServicio.atendida` es propiedad |
| Métodos de entidad (`estaApto`, `seCruzaCon`, `cerrar`, `estaVencido`…) | Métodos en snake_case en el modelo | `esta_apto`, `se_cruza_con`, `cerrar`, `esta_vencido`… |
| GestorReservas, MonitorServicios, GestorVideos | Clases con esos nombres y métodos en snake_case | Reciben sesión, reloj y adaptadores por inyección |
| IApiDispositivo, IServicioClima, IAlmacenamientoCloud | `abc.ABC` (la herencia deja explícito el `<|..` del diagrama) | Métodos `async` |
| ReporteDispositivo, Pronostico | `dataclass` | No se guardan |

## 2. API REST y eventos SSE

Prefijo `/api`, JSON en español, paginación `limite`/`desplazamiento` (50), respuesta paginada
`{items, total, limite, desplazamiento}`, errores `{"error": {codigo, mensaje, detalles}}`,
OpenAPI en `/docs` con etiquetas por módulo, el RF en cada descripción y seguridad *Bearer*.

| Método | Ruta | Rol | RF |
|---|---|---|---|
| POST | `/api/auth/login` | público | RF20 |
| GET | `/api/auth/yo` | ambos | RF20 |
| POST · GET | `/api/usuarios` | admin | RF18 |
| PATCH | `/api/usuarios/{id}` | admin | RNF01 |
| POST | `/api/usuarios/{id}/desactivar` | admin | RF19 |
| GET | `/api/dispositivos` · `/api/dispositivos/{id}` | ambos | RF04 |
| POST | `/api/dispositivos` | admin | RF01 |
| PATCH | `/api/dispositivos/{id}` | admin | RF02 |
| POST | `/api/dispositivos/{id}/baja` | admin | RF03 |
| GET | `/api/dispositivos/{id}/reporte` | admin | RF17 |
| GET · POST | `/api/dispositivos/{id}/mantenimientos` | ambos | RF15 |
| POST | `/api/mantenimientos/{id}/cerrar` | ambos | RF15 |
| GET | `/api/ubicaciones` | ambos | RF05 |
| GET | `/api/zona-operacion` | ambos | RF25 |
| GET | `/api/reservas/sugerencia` | admin | RF22, RF23 |
| POST | `/api/reservas` | admin | RF05–RF07, RF23, RF24 |
| GET | `/api/reservas` · `/api/reservas/{id}` | ambos | RF05 |
| POST | `/api/reservas/{id}/cancelar` · `/reprogramar` | admin | RF21 |
| GET | `/api/bitacoras` · `/api/bitacoras/{id}` · `/api/bitacoras/{id}/ruta` | ambos | RF08 |
| POST | `/api/bitacoras/{id}/ordenes` | admin | RF14 |
| GET | `/api/monitoreo` | ambos | RF09 |
| GET | `/api/monitoreo/stream?token=` | ambos | RF10, RNF02 |
| GET | `/api/alertas` · `/api/alertas/{id}` | ambos | RF11, RF16, RF25 |
| POST | `/api/alertas/{id}/atencion` | ambos | RF27 |
| GET | `/api/videos` | ambos | RF12, RF13 |
| GET | `/api/videos/{id}/reproducir` | ambos | RF13 |
| GET | `/api/videos/{id}/contenido?usuario=&expira=&firma=` | enlace firmado | RF13 |
| GET | `/api/auditoria` | admin | RNF09 |
| GET | `/health` | público | RNF06 |
| POST | `/api/demo/reservas/{id}/iniciar` | admin (demo) | — |
| POST | `/api/demo/dispositivos/{id}/eventos` | admin (demo) | — |
| POST | `/api/demo/dispositivos/{id}/codigo-entrega` | admin (demo) | — |
| PUT | `/api/demo/clima` | admin (demo) | — |
| POST | `/api/demo/tareas/{nombre}/ejecutar` | admin (demo) | — |

Son exactamente los de la sección 9 de la especificación; no agrego rutas. Detalles que fijo:

- `GET /api/reservas/sugerencia` devuelve además la lista de **operadores activos**, para que el
  formulario no necesite otra llamada (RNF07: "sugerir y confirmar").
- Fechas: se aceptan con o sin zona; sin zona se asume America/Bogota. Las respuestas salen con
  `-05:00` (Colombia no tiene horario de verano), así el navegador las interpreta bien en cualquier equipo.
- El SSE vuelve a revisar cada 30 s que el usuario siga activo y que el token no haya vencido; si no,
  cierra el flujo (RF19 "queda fuera de inmediato").
- Los parámetros `token` y `firma` se ocultan en el log de accesos.

**Eventos SSE** (`event:`, `id:` incremental, `data:` JSON, `: ping` cada 15 s), tal cual la sección 10:
`telemetria`, `alerta`, `alerta_atendida`, `entrega`, `orden`, `servicio`, `servicio_en_espera`,
`servicio_no_iniciado`. Agrego `id_operador` a `alerta` para que el frontend pueda resaltarla al
operador responsable. El bus guarda los últimos 200 eventos para reenviarlos si el navegador se
reconecta con `Last-Event-ID`.

## 3. Simulador, monitor y tareas

### 3.1 `IApiDispositivo` y `ApiDispositivoSimulada`

```python
class IApiDispositivo(ABC):
    async def obtener_telemetria(self, numero_serie) -> TelemetriaDispositivo
    async def enviar_orden_inicio(self, numero_serie, orden: OrdenInicio) -> None
    async def enviar_orden(self, numero_serie, tipo: TipoOrden) -> None
    async def leer_codigo_entrega(self, numero_serie) -> str | None
    async def descargar_video(self, numero_serie) -> bytes
    async def confirmar_entrega(self, numero_serie, resultado: ResultadoEntrega) -> None   # agregado (7.5)
    async def esperar_evento(self) -> EventoDispositivo                                    # canal Dispositivo → Servidor
```

- **Un simulador para todos los dispositivos:** por eso cada método recibe `numero_serie` (el diagrama
  modela una API por dispositivo). `OrdenInicio` lleva lo que el dispositivo necesita de la reserva:
  id, tipo de servicio, origen y destino con coordenadas, base, inicio y duración estimada.
- **Estado en memoria por dispositivo:** posición, batería, sensores, misión (tramos y velocidad), fase,
  pausa, parada, desvío fuera de zona, video listo.
- **Tiempo:** el simulador no tiene un hilo propio. Cada vez que se le consulta, avanza su estado desde la
  última consulta hasta `reloj.ahora()`, integrando el movimiento por tramos, los cambios de fase, la
  descarga y la recarga de batería. Así es determinista con el `RelojSimulado` de las pruebas
  (avanzar 10 min = una consulta) y exacto con el reloj real.
- **Datos precargados (`escenario.json`):** consumo de batería por minuto y por tipo, recarga por minuto,
  sensores por tipo, *waypoints* opcionales entre ubicaciones (si no hay, línea recta), desvío para
  `SALIR_DE_ZONA` y probabilidad de fallas aleatorias (0 por defecto). Semilla fija para el azar.
- **Alta automática (RNF10):** si se consulta un número de serie desconocido, el simulador lo carga desde
  la BD (tipo, batería y sensores) con una función de lectura que se le inyecta. Por eso el robot sembrado
  con un sensor en `FALLA` aparece así en el simulador.
- **Misión:** tramos base → origen → destino → base, sin repetir puntos. Presupuesto de tiempo =
  `FRACCION_RECORRIDO` × duración.
  - Robot: la velocidad cubre todos los tramos en el presupuesto; en el destino queda en `ESPERANDO_CODIGO`.
  - Drone: la mitad del presupuesto es vuelo y la otra mitad grabación en el destino (`EN_DESTINO`).
- **Órdenes:** `RETORNO_BASE` traza un tramo directo a la base (fase `RETORNANDO`); `PARADA_EMERGENCIA`
  deja la fase `DETENIDO` hasta que llegue un `RETORNO_BASE`.
- **Eventos al servidor:** `CODIGO_INGRESADO` y `LLEGADA_BASE` van a una **cola en memoria**
  (`asyncio.Queue`). El monitor tiene una tarea que los consume y entonces llama a
  `leer_codigo_entrega()` o `descargar_video()`, como en el diagrama de secuencia.
- **Video:** al llegar a la base queda disponible `muestra.mp4` (H.264, generado por script y guardado
  en el repositorio).
- **Recarga:** en la base y sin misión, la batería sube a la tasa del escenario.
- **Controles de demo:** métodos propios del simulador (no de la interfaz): fijar batería, fallar o reparar
  un sensor, salir o volver a la zona, pausar o reanudar, e ingresar un código.

### 3.2 `MonitorServicios`

- **`actualizar_monitoreo()`** (cada `INTERVALO_MONITOREO_SEG`): una consulta trae los dispositivos no
  dados de baja con su servicio abierto. Luego `asyncio.gather` consulta todos en paralelo, cada uno con
  un tiempo máximo menor que el intervalo. Por dispositivo, en una transacción corta:
  1. Actualiza `nivel_bateria` y `sensor.estado`. Si está `EN_CARGA` y llegó al 100 %, pasa a `DISPONIBLE`.
  2. Si tiene servicio en curso, también:
     - guarda `registro_telemetria` y `lectura_sensor`;
     - pasa la bitácora a `RETORNANDO` cuando el dispositivo reporta esa fase;
     - corre `evaluar_umbrales` y `verificar_zona`;
     - revisa la espera del código (RF24).

  Después del *commit* publica `telemetria` y las alertas nuevas. Guarda en memoria la última lectura
  de cada dispositivo para `GET /api/monitoreo`. Si un dispositivo falla, lo registra en el log y sigue.
- **Alertas sin duplicados:** guarda en memoria qué condiciones están activas por bitácora. Una causa
  vuelve a alertar solo si la condición se normalizó y luego volvió a ocurrir. `RETRASO` se consulta en la
  BD, así sale una sola vez por servicio. Al reiniciar, las condiciones activas se reconstruyen con el
  último punto de cada bitácora abierta.
- **Entrega (RF24):** compara el código con `reserva.codigo_entrega`.
  - Los intentos fallidos se cuentan con las incidencias `ENTREGA_NO_CONFIRMADA` de la bitácora.
  - El inicio de la espera es el primer punto `ESPERANDO_CODIGO` guardado.
  - Las dos cosas viven en la BD, así que sobreviven a un reinicio.
  - Al tercer error o a los 5 min, envía `confirmar_entrega(AGOTADA)` y el robot regresa.
- **Exclusión por dispositivo:** un `asyncio.Lock` por dispositivo serializa el ciclo de monitoreo, los
  eventos, las órdenes (RF14) y el inicio, para que no choquen sobre la misma bitácora.
- **Cierre:** al recibir `LLEGADA_BASE`, sube el video fuera de la transacción. Luego cierra todo en una
  transacción, como dice 7.5. Si la subida falla, deja el MP4 en la carpeta de pendientes.
- **Reinicio:** en el arranque, las bitácoras abiertas se reanudan en el simulador desde su último punto
  (o desde la base si no hay puntos), con la fase que corresponde al estado de la bitácora.

### 3.3 Tareas (APScheduler 3.x, `AsyncIOScheduler`, zona America/Bogota)

| Tarea | Disparador | Detalle |
|---|---|---|
| Iniciar reservas | cada 10 s | `max_instances=1`, `coalesce` |
| Monitoreo | cada `INTERVALO_MONITOREO_SEG` | igual; nunca se solapa consigo misma |
| Mantenimiento preventivo | cron 06:00 | además, al cerrar cada servicio |
| Retención de videos | cron 02:00 | |
| Reintento de subidas | cada 5 min | |
| Consumidor de eventos del dispositivo | tarea `asyncio` permanente | |

Con `TAREAS_ACTIVAS=false` (pruebas) no se arranca nada. Las pruebas llaman a las funciones de cada tarea
directamente con el `RelojSimulado`. Los controles de demo usan esas mismas funciones.

## 4. Librerías (instaladas y probadas en Python 3.12.14 el 2026-11-07)

| Paquete | Versión | Uso |
|---|---|---|
| fastapi | 0.162.2 | API (trae starlette 1.10.0) |
| uvicorn[standard] | 0.54.0 | servidor, 1 worker |
| sqlalchemy[asyncio] | 2.1.8 | ORM async |
| psycopg[binary] | 3.3.8 | controlador PostgreSQL |
| alembic | 1.20.1 | migraciones |
| pydantic | 2.14.3 | validación |
| pydantic-settings | 2.16.2 | configuración por `.env` |
| email-validator | 2.3.0 | correo institucional |
| pyjwt | 2.15.1 | JWT HS256 |
| argon2-cffi | 25.1.0 | contraseñas Argon2id (RNF05) |
| sse-starlette | 3.7.0 | SSE con ping |
| apscheduler | 3.11.3 (fijado < 4) | tareas |
| httpx | 0.28.1 | Open-Meteo y cliente de pruebas |
| boto3 | 1.43.126 | S3 |
| tzdata | 2026.6 | zona America/Bogota en Windows y en la imagen *slim* |
| **Desarrollo:** pytest | 9.2.0 | |
| pytest-asyncio | 1.4.1.post1 | |
| moto[s3] | 5.2.5 | S3 simulado en pruebas |
| ruff | 0.17.4 | lint y formato |
| **Solo para el script del video:** av (PyAV) | 19.0.2 | trae `libx264`; probado: genera H.264 en MP4 |
| numpy | 2.5.4 | cuadros del video |

Gestor de dependencias: **uv** (`pyproject.toml` + `uv.lock`). La imagen Docker lo usa, y en Windows se
puede usar `uv sync` para correr las pruebas fuera del contenedor. Open-Meteo confirmado en su
documentación: `https://api.open-meteo.com/v1/forecast` con `hourly=wind_speed_10m,precipitation_probability`,
`wind_speed_unit=kmh` (por defecto), `timezone=America/Bogota`, `start_hour`/`end_hour` y 16 días como máximo.

**Riesgos de Windows ya identificados:**

- psycopg async no funciona con el `ProactorEventLoop`: el `conftest` y el arranque local fijan el
  *selector loop*.
- `zoneinfo` necesita `tzdata`.
- Los archivos `.sh` y `.sql` van con LF (`.gitattributes`).

## 5. Contradicciones y huecos encontrados

### Necesitan tu decisión (dejo mi recomendación)

- **P1. Reinicio sin poder reanudar (7.5).** La especificación dice que, si un servicio no se puede
  reanudar, se cierre "con una incidencia que explique por qué", pero ningún valor de `tipo_incidencia`
  sirve. **Recomiendo:** reanudar siempre (desde el último punto, o desde la base si no hay puntos), así
  ese caso no se da y no hay que tocar el esquema. Alternativa: migración 0002 con
  `ALTER TYPE tipo_incidencia ADD VALUE 'INTERRUPCION'`.
- **P2. Operador desactivado con reservas programadas.** RF21 solo permite cancelar o reprogramar; no hay
  cómo cambiar el operador, y el trigger exige un operador activo al cambiar `id_operador`.
  **Recomiendo:** desactivar devuelve una advertencia con esas reservas, y el servicio se inicia igual
  (el operador queda como dato histórico). Alternativa: aceptar `id_operador` opcional en
  `reprogramar`, que es una extensión pequeña de RF21.
- **P3. RESTR04 (S3 real).** Desarrollo y pruebas con almacenamiento local y `moto`; el adaptador S3
  queda listo. Para la demo hace falta que el equipo cree un bucket en AWS (capa gratuita) y ponga las
  credenciales en `.env`. ¿Lo tendrán? Si no, la demo corre con `ALMACENAMIENTO=local` y RESTR04 queda
  documentado como configuración.

### Las resuelvo así (quedarán en `decisiones.md`; dime si alguna no te gusta)

- **D1.** RF01 se contradice (pide "estado inicial" y luego dice "guarda con estado Disponible"). Sigo
  7.2: estado opcional, `DISPONIBLE` por defecto, nunca `EN_SERVICIO` ni `EN_MANTENIMIENTO`.
- **D2.** Cambios permitidos a la interfaz del diagrama (el equipo debe actualizar el diagrama de clases):
  - `IApiDispositivo`: `numero_serie` en cada método, `confirmar_entrega` y `esperar_evento`; recibe
    `OrdenInicio` en lugar de la entidad `Reserva`.
  - `IAlmacenamientoCloud`: `obtener_rango` y `tamano`, para transmitir con `Range` sin cargar el
    objeto completo.
  - `IServicioClima`: se conserva `consultar_pronostico(lugar, fecha_hora)` y el adaptador guarda en
    caché el pronóstico horario del día, así las horas del rango cuestan una sola llamada HTTP.
- **D3.** RF23: se revisan las horas cuyo intervalo se cruza con la reserva (10:15–11:15 revisa 10:00 y
  11:00). Se toma el peor viento y la peor lluvia.
- **D4.** La espera del código de entrega y los intentos (RF24) los controla el servidor, no el robot:
  son parámetros configurables y se prueban con el reloj simulado.
- **D5.** `EN_CARGA` → `DISPONIBLE` automático cuando la batería llega al 100 % (8 solo dice cuándo entra).
- **D6.** Un dispositivo `EN_MANTENIMIENTO` se puede editar (modelo, capacidad), pero no cambiar su estado
  mientras el mantenimiento esté abierto (409: "cierre el mantenimiento").
- **D7.** RF15:
  - Si un administrador registra el mantenimiento, debe indicar el operador responsable (422 si no).
  - Si hay reservas programadas, se registra igual con una advertencia, como en RF02. Esas reservas no
    se inician mientras dure (7.5).
- **D8.** RF16: no se alerta a dispositivos dados de baja ni con un mantenimiento abierto.
- **D9.** Las horas se fijan siempre con el `Reloj` (creación, auditoría, incidencias, fecha de registro),
  no con los `DEFAULT now()` de la BD, para que las pruebas con reloj simulado sean coherentes.
- **D10.** Usuario es una sola clase con `rol`: si `Administrador` y `Operador` fueran subclases, cambiar
  el rol (RNF01) cambiaría la clase del objeto, y SQLAlchemy no lo maneja bien. Robot/Drone y las alertas
  sí usan herencia.
- **D11.** Un token de un usuario desactivado responde 401 `NO_AUTENTICADO` ("Usuario inactivo"), para que
  el frontend cierre la sesión. El login de un inactivo responde 403, como dice 7.1. El rol se lee de la BD
  en cada petición, no del token.
- **D12.** Validación de "no en el pasado": se acepta el minuto en curso, para que una reserva para "ya"
  no falle por segundos. La hora se guarda sin segundos.
- **D13.** Auditoría (RNF09):
  - Se auditan `usuario` (CREAR/EDITAR/BAJA), `dispositivo` (CREAR/EDITAR/BAJA), `mantenimiento`
    (CREAR, y EDITAR al cerrar), `reserva` (CREAR, EDITAR al reprogramar, BAJA al cancelar),
    `atencion_alerta` (CREAR) y la `incidencia` que crea una orden RF14 (CREAR).
  - Los sensores creados con el dispositivo van dentro del CREAR del dispositivo.
  - No se auditan el login, las acciones automáticas ni los controles de demo (simulan al dispositivo
    o al reloj).
- **D14.** "Alertas abiertas" en `/api/monitoreo`: alertas de servicio sin atención, más alertas de
  mantenimiento sin un mantenimiento registrado después de ellas. En `GET /api/alertas`, el filtro
  `atendida` solo aplica a las de servicio.
- **D15.** `POST /api/demo/reservas/{id}/iniciar` aplica las mismas validaciones del inicio automático
  (dispositivo apto y libre); solo se salta la hora. El retraso se sigue midiendo contra el horario
  reservado, como dice la especificación. Para mostrar `RETRASO` en la presentación sin esperar 10 min,
  `docs/demo.md` indicará bajar `RETRASO_ALERTA_MIN` en el `.env` de la demo.
- **D16.** RF26 sigue la especificación: se borra cuando `fecha_grabacion::date + 3 meses ≤ hoy` (meses de
  calendario; el 31 de agosto + 3 meses = 30 de noviembre). Así el video "cumple" 3 meses en esa fecha,
  como dice RF26.
- **D17.** RF17 usa `reporte_dispositivo()` tal cual: cuenta todos los servicios que salieron en el rango
  (también los que siguen en curso) y suma horas solo de los cerrados. La lista que acompaña al reporte
  muestra el estado de cada servicio.
- **D18.** Si llega una telemetría repetida para el mismo instante (`uq_telemetria_punto`), el punto se
  omite sin error.
- **D19.** La zona de operación es la de nombre `ZONA_OPERACION` (por defecto, la única cargada). Si no hay
  zona, RF25 no se evalúa y se avisa en el log y en `/health`.
- **D20.** RF13: un video ya eliminado por retención responde 404 al pedir su enlace o su contenido.

### Para validar con el cliente (no cambian el plan)

- No hay forma de reactivar un usuario ni de cambiar contraseñas (no están en el SRS).
- La duración de una grabación no se compara con la autonomía de vuelo del drone, ni hay peso del pedido
  frente a la capacidad del robot. Serían reglas naturales, pero no están pedidas.
- Las coordenadas del campus son de ejemplo.

## 6. Pruebas

- PostgreSQL 16 real: BD `robots_test` en el mismo contenedor `db`. Se crea sola, se migra con Alembic una
  vez por sesión y se limpia con `TRUNCATE … RESTART IDENTITY CASCADE` después de cada prueba.
- Todo corre en un solo *event loop* de sesión (pytest-asyncio), para que el motor async no cambie de loop.
- La app de prueba se arma con `crear_app(contenedor)` usando `RelojSimulado`, `ServicioClimaFalso`,
  `AlmacenamientoLocal` en `tmp_path` y el simulador determinista. Las pruebas del adaptador S3 usan `moto`.
  Ninguna prueba sale a internet.
- HTTP con `httpx.AsyncClient` + `ASGITransport`. El SSE y la prueba lenta de RNF02 levantan un
  `uvicorn.Server` real dentro del mismo loop, en un puerto libre, porque `ASGITransport` espera a que la
  respuesta termine y un flujo SSE no termina.
- Concurrencia de RF06, dos pruebas:
  1. Dos `POST` simultáneos con `asyncio.gather` dan un 201 y un 409.
  2. Otra fuerza a que ambas peticiones pasen la validación del servicio, para comprobar que el 409 lo da
     la restricción `EXCLUDE` (23P01), con la reserva en conflicto.
- Nombres `test_rfXX_…` y `test_rnfXX_…`. La prueba de RNF02 se marca `lenta` (con la opción para
  incluirla en la suite completa).
- Comandos:
  - `docker compose exec api pytest` (principal)
  - `uv run pytest` en Windows contra `localhost`

## 7. Fases

Las del encargo original (no incluido en este repositorio), sin cambios: 1 Base · 2 Inventario y mantenimiento · 3 Reservas ·
4 Servicio en curso · 5 Videos, reportes y cierre. Cada fase termina con:

- pruebas en verde y ruff limpio;
- `CLAUDE.md`, `decisiones.md` y `trazabilidad.md` al día;
- un commit `fase N: …`.

El repositorio git se inicializa al empezar la Fase 1.
