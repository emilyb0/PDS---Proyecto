# Especificación del backend — prototipo

> Este documento dice **cómo** construir el backend: reglas exactas, estados, API, simulador y pruebas.
> `requisitos.md` dice **qué** debe hacer el sistema.
>
> **Si dos documentos se contradicen, manda el primero de esta lista:**
> 1. `docs/requisitos.md`
> 2. `docs/modelo/esquema_bd.sql` (probado en PostgreSQL 16)
> 3. este documento
> 4. `docs/modelo/diagrama_clases.puml`
> 5. `docs/modelo/diagrama_secuencia.mmd`
> 6. `docs/modelo/diagrama_bd.mmd` (vista derivada del SQL, solo de referencia)

---

## 1. Alcance

**Incluye:** API REST y eventos en tiempo real para RF01–RF27, los RNF que aplican al backend, RESTR01 (simulador y datos precargados), RESTR02 (API lista para una app web) y RESTR04 (videos en un servicio tipo S3). También incluye datos semilla para la demo y un guion de demo.

**No incluye:** el frontend (la API debe quedar lista para él: OpenAPI, CORS y SSE), el despliegue en la nube, hardware real ni alta disponibilidad. RNF06 (disponibilidad) y la parte HTTPS de RNF05 se documentan en el README; no se implementan en local.

### Cómo cumple el backend cada RNF y restricción

| ID | En el backend |
|---|---|
| RNF01 | Matriz de permisos (sección 5); el operador recibe 403 en lo que es del administrador |
| RNF02 | Monitor cada ≤ 5 s con consultas en paralelo + SSE; prueba lenta con 6 dispositivos en servicio |
| RNF03 | Listados de inventario, reservas y bitácora paginados y con índices; prueba de que responden en < 3 s con los datos semilla |
| RNF04 | Retención de videos de 3 meses (tarea diaria, RF26) |
| RNF05 | Contraseñas con Argon2 o bcrypt; el README explica cómo poner HTTPS con un proxy inverso al desplegar |
| RNF06 | `/health` con sus dependencias y `restart: unless-stopped` en Compose; la meta del 95 % se documenta |
| RNF07 | La sugerencia (RF22) devuelve en una sola llamada todo lo que el formulario necesita, así crear una reserva toma 2 pasos: sugerir y confirmar |
| RNF08 | Bucket privado, enlaces firmados de corta duración, solo usuarios autenticados y registro de cada acceso a un video |
| RNF09 | Auditoría en la misma transacción (sección 4) |
| RNF10 | Ningún límite fijo de dispositivos; prueba con 20 |
| RESTR01 | Simulador y datos semilla (secciones 11 y 13) |
| RESTR02 | API REST + SSE con CORS configurable para la app web |
| RESTR03 | Solo estándares web: SSE (`EventSource`) y video MP4 con `Range`, compatibles con Chrome, Firefox y Edge |
| RESTR04 | Videos en AWS S3 (adaptador S3); almacenamiento local solo para desarrollo |

## 2. Stack (decidido)

| Pieza | Elección | Motivo |
|---|---|---|
| Lenguaje y framework | Python 3.12 + FastAPI, servido con Uvicorn | El equipo ya lo usó en otro proyecto |
| Base de datos | PostgreSQL 16 | El esquema usa `EXCLUDE`, `TSRANGE`, ENUM y triggers |
| Acceso a datos | SQLAlchemy 2 en modo async + psycopg 3 | Monitoreo cada 5 s, SSE y llamadas HTTP externas conviven mejor en async |
| Migraciones | Alembic | La migración 0001 ejecuta `esquema_bd.sql` |
| Validación y configuración | Pydantic v2 + pydantic-settings (`.env`) | — |
| Autenticación | JWT (PyJWT) y contraseñas con Argon2 o bcrypt | RF20, RNF05 |
| Tiempo real | Server-Sent Events (sse-starlette) | El flujo es solo servidor → navegador |
| Tareas periódicas | APScheduler 3.x (AsyncIOScheduler) o bucles asyncio en el `lifespan` | Inicio de reservas, monitoreo y tareas diarias |
| Clima (RF23) | Open-Meteo con httpx (gratis, sin API key) + adaptador falso | Confirmar en https://open-meteo.com/en/docs los nombres `wind_speed_10m` y `precipitation_probability` |
| Videos (RF12, RESTR04) | AWS S3 con boto3 (o cualquier servicio compatible con S3 vía `S3_ENDPOINT_URL`) + adaptador local en disco para desarrollo | **No usar MinIO**: dejó de publicar imágenes Docker en oct-2025 y su repositorio está archivado |
| Pruebas | pytest + pytest-asyncio + httpx; `moto` para simular S3 | PostgreSQL **real** en Docker, **nunca SQLite** (el esquema depende de PostgreSQL) |
| Calidad | ruff (lint y formato) | — |
| Entorno | Docker Compose (`db`, `api`). El equipo trabaja en **Windows + PowerShell + Docker Desktop** | README con comandos de PowerShell |

**Un solo proceso:** el simulador, el monitor y el bus de eventos SSE viven en memoria, así que Uvicorn corre con **1 worker**. Hay que dejarlo dicho en el README.

## 3. Arquitectura

Capas: **routers** (HTTP, validación de entrada) → **servicios** (reglas de negocio, transacciones) → **repositorios/modelos** (SQLAlchemy). Las integraciones externas van detrás de interfaces (`typing.Protocol` o ABC) y se inyectan, para poder reemplazarlas en pruebas.

### Correspondencia con el diagrama de clases

| Módulo | Clases del diagrama | Tablas |
|---|---|---|
| `usuarios` (incluye login) | Usuario, Administrador, Operador | `usuario` |
| `auditoria` | RegistroAuditoria | `registro_auditoria` |
| `dispositivos` | Dispositivo, Robot, Drone, Sensor | `dispositivo`, `sensor` |
| `mantenimiento` | Mantenimiento | `mantenimiento` |
| `ubicaciones` | Ubicacion, ZonaOperacion | `ubicacion`, `zona_operacion`, `vertice_zona` |
| `reservas` | Reserva, **GestorReservas** | `reserva` |
| `servicios` (bitácora y monitoreo) | BitacoraServicio, RegistroTelemetria, Incidencia, **MonitorServicios** | `bitacora_servicio`, `registro_telemetria`, `lectura_sensor`, `incidencia` |
| `alertas` | Alerta, AlertaServicio, AlertaMantenimiento, AtencionAlerta | `alerta`, `alerta_servicio`, `alerta_mantenimiento`, `atencion_alerta` |
| `videos` | Video, **GestorVideos** | `video` |
| `reportes` | ReporteDispositivo | función SQL `reporte_dispositivo()` |
| `integraciones` | **IApiDispositivo**, **ApiDispositivoSimulada**, **IServicioClima**, Pronostico, **IAlmacenamientoCloud** | — |

**Nombres:** las clases conservan el nombre del diagrama (`GestorReservas`, `MonitorServicios`, `GestorVideos`, `IApiDispositivo`, `ApiDispositivoSimulada`, `IServicioClima`, `IAlmacenamientoCloud`, `Pronostico`). Métodos y atributos van en snake_case: `obtenerTelemetria` → `obtener_telemetria`, `estaApto` → `esta_apto`. El código de dominio, los comentarios y los mensajes al usuario van en español.

**Reloj inyectable:** ningún servicio llama directamente a `datetime.now()`; todos usan un `Reloj` inyectado. Así las pruebas pueden simular 10 minutos de retraso o 3 meses de antigüedad sin esperar.

**Diferencias intencionales entre clases y tablas** (ya explicadas en la cabecera de `esquema_bd.sql`; no hay que "corregirlas"):

- Usuario/Administrador/Operador → una tabla con `rol`. Dispositivo/Robot/Drone → una tabla con `tipo` y columnas de subtipo.
- Alerta/AlertaServicio/AlertaMantenimiento → una tabla por subclase (PK = FK).
- `AlertaServicio.atendida` no es columna: es *atendida* si existe su `atencion_alerta`.
- AlertaServicio llega a su bitácora a través de `incidencia` (cada alerta de servicio nace de una incidencia).
- `Ubicacion` es un catálogo (`ubicacion`) para origen y destino; telemetría e incidencias guardan `latitud`/`longitud`.
- `RegistroTelemetria.estadoSensores` (Map) → tabla `lectura_sensor`.
- `ReporteDispositivo` no se guarda: lo calcula `reporte_dispositivo(id, desde, hasta)`.
- `Pronostico` no se guarda.

## 4. Base de datos

- `docs/modelo/esquema_bd.sql` es la fuente de verdad. La migración Alembic **0001** ejecuta una copia literal de ese archivo, guardada junto a las migraciones. Cualquier cambio posterior va en una migración nueva; la 0001 no se edita.
- **Nunca** usar `Base.metadata.create_all`. Los modelos SQLAlchemy se mapean a las tablas que ya existen: ENUM de PostgreSQL con `create_type=False`, `reserva.horario` como columna calculada de solo lectura (`TSRANGE`, nunca se escribe) y la PK `GENERATED BY DEFAULT AS IDENTITY`.
- **Zona horaria:** las columnas `TIMESTAMP` (sin zona) guardan la hora local de Colombia, **America/Bogota**. Hay que configurar la sesión de PostgreSQL en esa zona (en la cadena de conexión o en el contenedor) para que `now()` y la aplicación coincidan, y el `Reloj` también trabaja en esa zona.
- **Defensa en profundidad:** los servicios validan primero, para dar mensajes claros. La base es la última barrera, sobre todo ante concurrencia.
- **Traducción de errores de PostgreSQL a HTTP:**

| SQLSTATE | Caso | HTTP y código de error |
|---|---|---|
| `23P01` (exclusion) | `ex_reserva_cruce` | 409 `CRUCE_HORARIO`, con la reserva en conflicto (hay que buscarla y devolverla, RF06) |
| `23505` (unique) | correo o número de serie repetido, segunda bitácora, segunda atención… | 409 `DUPLICADO` |
| `23514` (check) | `ck_…` | 409 `REGLA_NEGOCIO`, con un mensaje en español según la restricción |
| `P0001` (RAISE de trigger) | `fn_validar_reserva`, `fn_validar_baja` | 409 `REGLA_NEGOCIO`, con el mensaje del trigger |
| `23503` (foreign key) | id inexistente | 404 `NO_ENCONTRADO` |

- **Auditoría (RNF09):** cada creación, edición o baja que hace un usuario escribe en `registro_auditoria`, **en la misma transacción** (acción `CREAR`, `EDITAR` o `BAJA`; `entidad` = nombre de la tabla). Las acciones automáticas del sistema no se auditan ahí; quedan en la bitácora.

## 5. Roles y permisos (RF20, RNF01)

| Acción | Administrador | Operador |
|---|:---:|:---:|
| Consultar inventario, reservas, bitácoras, monitoreo, alertas, videos, ubicaciones | ✔ | ✔ |
| Registrar mantenimiento y cerrarlo (RF15) | ✔ | ✔ |
| Atender alertas de servicio (RF27) | ✔ | ✔ |
| Registrar, editar y dar de baja dispositivos (RF01–RF03) | ✔ | ✘ |
| Sugerir, crear, cancelar y reprogramar reservas (RF05, RF21, RF22) | ✔ | ✘ |
| Ordenar retorno o parada (RF14) | ✔ | ✘ |
| Reportes (RF17) y auditoría (RNF09) | ✔ | ✘ |
| Registrar usuarios, cambiar rol, desactivar (RF18, RF19, RNF01) | ✔ | ✘ |
| Controles de demo (`/api/demo/...`) | ✔ | ✘ |

- Sin token, con token inválido o vencido: **401**. Sin permiso: **403**.
- **RF19:** el estado del usuario se revisa en **cada** petición. Un usuario desactivado queda fuera de inmediato, aunque su token no haya vencido.
- `GET /api/auth/yo` devuelve el usuario y la lista de **funciones** de su rol, para que el frontend muestre solo esas (RF20).

## 6. Parámetros de negocio

Todos se configuran por variables de entorno. Estos son sus valores por defecto. Las comparaciones son **exactas** y las pruebas deben cubrir el límite.

| Parámetro | Defecto | Regla | Comparación | RF |
|---|---|---|---|---|
| `BATERIA_MINIMA_ASIGNACION` | 30 | Rechazar asignación | `bateria < 30` rechaza; 30 pasa | RF07, RF22 |
| `BATERIA_ALERTA` | 20 | Alerta en servicio | `bateria < 20` | RF11 |
| `RETRASO_ALERTA_MIN` | 10 | Alerta de retraso | `ahora > inicio + duración + 10 min` sin haber cerrado el servicio | RF11 |
| `VIENTO_MAX_KMH` | 30 | Rechazar drone | `viento > 30` rechaza | RF23 |
| `LLUVIA_MAX_PCT` | 60 | Rechazar drone | `probabilidad > 60` rechaza | RF23 |
| `MANTENIMIENTO_DIAS` | 30 | Alerta preventiva | `días ≥ 30` | RF16 |
| `MANTENIMIENTO_HORAS` | 50 | Alerta preventiva | `horas_uso_desde_mant ≥ 50` | RF16 |
| `RETENCION_VIDEO_MESES` | 3 | Borrar video | `fecha_grabacion + 3 meses ≤ hoy` (meses de calendario) | RF26, RNF04 |
| `INTERVALO_MONITOREO_SEG` | 5 | Ciclo de monitoreo | ≤ 5 | RF10, RNF02 |
| `ESPERA_ENTREGA_MIN` | 5 | Espera del robot en el destino | Si se agota, regresa | RF24 (decisión) |
| `MAX_INTENTOS_CODIGO` | 3 | Intentos de código de entrega | Al tercer error, regresa | RF24 (decisión) |
| `FRACCION_RECORRIDO` | 0.8 | El simulador completa el recorrido en este % de la duración estimada | — | RESTR01 |
| `VIDEO_URL_EXPIRA_MIN` | 10 | Vigencia del enlace firmado de video | — | RF13, RNF08 |
| `JWT_EXPIRA_HORAS` | 8 | Vigencia del token | — | RF20 |

## 7. Reglas por módulo

### 7.1 Usuarios (RF18–RF20, RNF01, RNF05)

- **Registrar:** nombre, correo institucional, contraseña (mínimo 8 caracteres) y rol. El correo es único sin importar mayúsculas (la base ya lo exige). Si `DOMINIO_CORREO_INSTITUCIONAL` está definido, el correo debe ser de ese dominio. El usuario se guarda `ACTIVO` y con la contraseña cifrada; **nunca** se devuelve el hash.
- **Cambiar rol o nombre** (RNF01, "cambiar permisos"): solo el administrador.
- **Desactivar:** el usuario pasa a `INACTIVO`. No se permite desactivar al último administrador activo ni a uno mismo (409).
- **Login:** con datos incorrectos responde 401 "Correo o contraseña incorrectos" (el mismo mensaje para correo inexistente y contraseña errada). Si la contraseña es correcta pero el usuario está inactivo, responde 403 "Usuario inactivo".

### 7.2 Dispositivos (RF01–RF04, RNF10)

- **Tipo requerido por servicio** (del enunciado: los robots transportan y los drones graban): `ENTREGA_DOCUMENTOS` y `PEDIDO_CAFETERIA` → **ROBOT**; `GRABACION_EVENTO` → **DRONE**.
- **Registrar (RF01):** tipo, número de serie (único), modelo, `capacidad_carga_kg` si es robot o `autonomia_vuelo_min` si es drone, y estado inicial. El estado es opcional, por defecto `DISPONIBLE`, y no puede ser `EN_SERVICIO` ni `EN_MANTENIMIENTO`. Los **sensores** son opcionales (lista de nombres); si no se envían, se crean los del tipo: robot = GPS, Cámara, LIDAR, Ultrasonido; drone = GPS, Cámara, IMU, Barómetro.
- **Editar (RF02):** modelo, capacidad o autonomía (según el tipo) y estado manual. Los estados manuales permitidos son `DISPONIBLE`, `EN_CARGA` y `FUERA_DE_SERVICIO`. `EN_SERVICIO` y `EN_MANTENIMIENTO` los maneja el sistema. No se edita un dispositivo en servicio ni uno dado de baja (409). Si queda `FUERA_DE_SERVICIO` con reservas programadas, se devuelve una advertencia. La "fecha de modificación" de RF02 es el registro `EDITAR` en `registro_auditoria`.
- **Dar de baja (RF03):** con motivo y fecha (hoy por defecto). Solo si no tiene reservas `PROGRAMADA` o `EN_CURSO` (el trigger también lo valida). Pasa a `FUERA_DE_SERVICIO` y queda excluido de nuevas asignaciones.
- **Inventario (RF04):** lista con tipo, modelo, estado, número de serie y último nivel de batería, filtrable por tipo y por estado, paginada. Por defecto incluye los dados de baja, que se ven como `FUERA_DE_SERVICIO`.
- **RNF10:** nada está fijado a 6 dispositivos. Un dispositivo nuevo aparece solo en el simulador y en el monitoreo, sin tocar código.

### 7.3 Mantenimiento (RF15, RF16)

- **Registrar (RF15):** tipo, descripción, fecha de inicio (hoy por defecto, no futura) y responsable (un operador activo; por defecto, el usuario actual si es operador). Se rechaza (409) si el dispositivo está en servicio, dado de baja o ya tiene un mantenimiento abierto. El dispositivo pasa a `EN_MANTENIMIENTO`.
- **Cerrar (RF15):** con fecha de fin (hoy por defecto). El dispositivo vuelve a `DISPONIBLE` y `horas_uso_desde_mant` vuelve a 0.
- **Alerta preventiva (RF16):** el último mantenimiento es el `fecha_fin` más reciente; si no hay ninguno, cuenta `fecha_registro`. Si han pasado `≥ 30` días o `horas_uso_desde_mant ≥ 50`, se crea una `alerta` de tipo `MANTENIMIENTO` con su `alerta_mantenimiento` y se publica por SSE para el operador. Se revisa **al cerrar cada servicio** y en una **tarea diaria**. No se repite: si ya hay una alerta de mantenimiento del dispositivo posterior al último mantenimiento, no se crea otra.

### 7.4 Reservas (RF05–RF07, RF21–RF24)

**Validaciones de entrada (422):** la fecha y hora no pueden estar en el pasado; la duración va de 1 a 480 min; el origen y el destino existen y son distintos.

**Sugerencia (RF22, pasos 2–10 del diagrama de secuencia):** recibe tipo de servicio, fecha, hora de inicio, duración, origen y destino.

1. Candidatos: dispositivos del tipo requerido que no estén dados de baja ni en `EN_MANTENIMIENTO` o `FUERA_DE_SERVICIO`.
2. Se descartan los que tienen cruce de horario (RF06).
3. Se consulta su batería y sus sensores **en ese momento** a través de `IApiDispositivo`, y se descartan los que no cumplen RF07.
4. Se ordenan por batería descendente y el primero es el `sugerido`.
5. La respuesta trae `sugerido`, `disponibles` y `descartados` (cada uno con sus `motivos`). Si el servicio es `GRABACION_EVENTO`, trae además la evaluación del clima, para que el administrador sepa antes de elegir. Si no queda ninguno, `sugerido` va en `null` con el mensaje "No hay dispositivos disponibles para ese horario; reprograme la solicitud" (pasos 5–6).

**Crear (RF05, pasos 12–28):** recibe los datos anteriores más `id_dispositivo` (el sugerido u otro) y `id_operador`. Las validaciones van **en el orden del diagrama** y se detienen en la primera que falla:

1. Tipo correcto para el servicio → si no, 409 `TIPO_DISPOSITIVO_INCORRECTO`.
2. Dispositivo no dado de baja ni en `EN_MANTENIMIENTO` o `FUERA_DE_SERVICIO` → si no, 409 `DISPOSITIVO_NO_APTO`.
3. **RF06**, cruce de horario con otra reserva `PROGRAMADA` o `EN_CURSO` → 409 `CRUCE_HORARIO`, devolviendo la reserva en conflicto (id, horario, servicio y operador).
4. **RF07**, batería y sensores consultados en ese momento → 409 `DISPOSITIVO_NO_APTO` con `motivos`, por ejemplo "Batería 25 % (mínimo 30 %)" o "Sensor LIDAR en falla". De paso se actualizan `dispositivo.nivel_bateria` y `sensor.estado`.
5. **RF23**, solo si es drone: se pide el pronóstico en el **destino** para **cada hora** del rango de la reserva y se toma el peor valor. Si el viento es mayor a 30 km/h o la lluvia mayor a 60 %, responde 409 `CLIMA_NO_APTO` con los valores y la hora. Si no hay pronóstico (más de ~16 días o la API falla), se **acepta con advertencia** `clima_no_verificado`.
6. Se guarda la reserva en estado `PROGRAMADA`. Si es robot, se genera un **código de 4 dígitos** con `secrets` (RF24), que se devuelve al administrador para entregarlo a quien recibe. Se audita `CREAR`.

La restricción `EXCLUDE` protege de dos creaciones simultáneas: si llega el error `23P01`, se responde como en el punto 3.

**Cancelar (RF21):** solo si está `PROGRAMADA`. Requiere motivo; pasa a `CANCELADA` con `motivo_cambio` y el horario queda libre. Se audita `BAJA`.

**Reprogramar (RF21):** solo si está `PROGRAMADA`. Recibe nueva fecha y hora de inicio, duración opcional y motivo. Revalida pasado, RF06, RF07 y RF23 (si es drone). Guarda el `motivo_cambio` y el horario anterior queda libre. Se audita `EDITAR`.

### 7.5 Servicio en curso (RF08–RF11, RF14, RF24, RF25)

**Inicio (pasos 29–31).** Una tarea revisa cada 10 s las reservas `PROGRAMADA` cuyo inicio ya llegó.

- Si el dispositivo sigue en otro servicio, la reserva espera y se avisa una vez por SSE (`servicio_en_espera`).
- Si el dispositivo no está apto (batería < 30, sensor en falla, en mantenimiento, fuera de servicio o dado de baja), no se inicia. Se avisa por SSE (`servicio_no_iniciado`, con el motivo) y el administrador decide.
- Si la ventana de la reserva terminó sin iniciarse, pasa a `CANCELADA` con motivo "No se inició: …".
- Si todo está bien: `enviar_orden_inicio` al dispositivo, se crea la bitácora (`hora_salida` = ahora, `EN_CURSO`), la reserva pasa a `EN_CURSO` y el dispositivo a `EN_SERVICIO`. Se publica por SSE `servicio` con `INICIADO`.

**Monitoreo (RF09, RF10, RNF02; pasos 33–36).** `MonitorServicios` corre cada `INTERVALO_MONITOREO_SEG` sobre **todos** los dispositivos no dados de baja. Así se cumple "antes, durante y al finalizar" del enunciado.

- Para cada uno: `obtener_telemetria`, actualizar `dispositivo.nivel_bateria` y `sensor.estado`, y publicar el evento SSE `telemetria`.
- Si tiene un servicio en curso, además: guardar `registro_telemetria` y `lectura_sensor`, evaluar alertas y zona, y actualizar el estado de la bitácora según la fase que reporta el dispositivo (`RETORNANDO` cuando inicia el regreso).
- Las consultas a los dispositivos van en paralelo (`asyncio.gather`), con una transacción corta por dispositivo. Si uno falla, se registra en el log y se sigue con los demás. Una vuelta nunca debe tardar más que el intervalo ni bloquear la API.

**Alertas de servicio (RF11, RF25; pasos 37–43).** Se evalúan solo con el servicio en curso:

| Causa | Condición |
|---|---|
| `BATERIA_BAJA` | `bateria < 20` |
| `SENSOR_EN_FALLA` | algún sensor en `FALLA` (la descripción nombra el sensor) |
| `RETRASO` | `ahora > inicio + duración + 10 min` y la bitácora no está `FINALIZADO` |
| `SALIDA_DE_ZONA` | el punto queda fuera del polígono de `vertice_zona`; se usa *ray casting* propio, sin PostGIS, y el borde cuenta como dentro |

- Cada alerta se guarda en **una transacción**: `incidencia` (el tipo con el mismo nombre; con latitud y longitud, obligatorias en `SALIDA_DE_ZONA`), `alerta` (tipo `SERVICIO`, `id_dispositivo`) y `alerta_servicio` (`causa`, `id_incidencia`). Después se publica por SSE `alerta`, con el dispositivo, la causa y la ubicación (RF11 y RF25 piden que la vean el administrador y el operador).
- **Sin duplicados:** una causa no se repite en el mismo servicio mientras la condición siga activa. Si se normaliza y vuelve a ocurrir, se genera otra alerta. `RETRASO` se genera una sola vez por servicio.

**Atención (RF27).** Solo para alertas de servicio, una por alerta. Guarda la causa revisada, las observaciones, el operador y la hora, y publica por SSE `alerta_atendida` para que la vea el administrador.

**Órdenes (RF14; pasos 44–48).** Solo el administrador, con la bitácora sin cerrar. `RETORNO_BASE` hace que el dispositivo vaya directo a la base. `PARADA_EMERGENCIA` lo detiene donde esté hasta que reciba un `RETORNO_BASE`. Cada orden se envía con `enviar_orden`, se registra como incidencia (`ORDEN_RETORNO` o `PARADA_EMERGENCIA`) y se publica por SSE `orden`.

**Entrega con código (RF24; pasos 49–54).** Solo robots. Al llegar al destino, el robot espera el código.

- Cuando el dispositivo avisa que alguien ingresó un código, el servidor lo lee (`leer_codigo_entrega`) y lo compara con `reserva.codigo_entrega`.
- **Si coincide:** la bitácora pasa a `ENTREGADO` con `hora_entrega`, se publica por SSE `entrega` con `CONFIRMADA`, y el robot recibe el resultado e inicia el regreso.
- **Si no coincide:** se registra una incidencia `ENTREGA_NO_CONFIRMADA` y se publica por SSE `entrega` con `NO_CONFIRMADA`. No se crea `alerta_servicio`, porque esa causa no existe en `causa_alerta`; es un aviso del panel.
- Tras `MAX_INTENTOS_CODIGO` errores o `ESPERA_ENTREGA_MIN` sin un código correcto, el robot regresa sin entregar y se registra una incidencia `ENTREGA_NO_CONFIRMADA` con el motivo.
- La interfaz del diagrama no tiene cómo avisarle el resultado al robot. Agregar `confirmar_entrega(resultado)` a `IApiDispositivo` está permitido; anótalo en `docs/decisiones.md` para que el equipo actualice el diagrama de clases.

**Cierre (RF08, RF12, RF16; pasos 55–63).** Cuando el dispositivo avisa que llegó a la base:

1. `descargar_video` y `GestorVideos.almacenar_video`: sube el MP4 con `IAlmacenamientoCloud.subir`, **fuera** de la transacción.
2. En **una transacción**: se crea `video` (`fecha_grabacion` = `hora_salida`, `duracion_seg` = la duración real); la bitácora queda con `hora_regreso` y `FINALIZADO`; la reserva pasa a `FINALIZADA`; el dispositivo vuelve a `DISPONIBLE` (o `EN_CARGA` si quedó con batería < 30, y el simulador lo recarga); y a `horas_uso_desde_mant` se le suman las horas del servicio.
3. Se revisa RF16 y se publica por SSE `servicio` con `FINALIZADO`.
4. Si la subida falla, la bitácora se cierra igual: el MP4 se guarda en una carpeta local de pendientes, una tarea lo reintenta cada 5 min y el registro `video` se crea cuando suba.

**Estados de la bitácora:** `EN_CURSO` → (`ENTREGADO`, solo robots) → `RETORNANDO` → `FINALIZADO`. Que el servicio fue entregado se sabe por `hora_entrega`, aunque el estado final sea `FINALIZADO`.

**Reinicio del backend:** los servicios abiertos se reanudan en el simulador desde su último punto. Si no se puede, se cierran con una incidencia que explique por qué.

### 7.6 Videos (RF12, RF13, RF26, RNF04, RNF08, RESTR04)

- La columna `video.url` guarda **la ubicación del objeto** (por ejemplo `s3://bucket/videos/2026/11/bitacora-123.mp4`), no una URL pública. El bucket es privado.
- **Buscar (RF13):** por día o rango de fechas de grabación, dispositivo y tipo de servicio. Por defecto excluye los eliminados (parámetro `incluir_eliminados`).
- **Reproducir (RF13, pasos 64–69):** `GET /api/videos/{id}/reproducir` devuelve un enlace firmado con HMAC (contiene usuario, video y expiración; vale `VIDEO_URL_EXPIRA_MIN`) hacia `GET /api/videos/{id}/contenido`. Ese endpoint trae el objeto del almacenamiento y lo **transmite con soporte de `Range`** (respuestas 206), para que el reproductor HTML5 pueda adelantar. Se usa enlace firmado porque la etiqueta `<video>` no puede enviar la cabecera `Authorization`. Cada acceso se registra en el log (RNF08).
- **Retención (RF26):** una tarea diaria busca los videos con `fecha_eliminacion` vacía y `fecha_grabacion + 3 meses ≤ hoy`, borra el objeto y llena `fecha_eliminacion`. Si un borrado falla, se reintenta al día siguiente, sin marcarlo.
- **Adaptadores:** `AlmacenamientoS3` (boto3; también sirve para servicios compatibles con S3 vía `S3_ENDPOINT_URL`) y `AlmacenamientoLocal` (carpeta en un volumen Docker). Se elige con `ALMACENAMIENTO=local|s3`. Para cumplir RESTR04 en la demo, se configura un bucket real de AWS S3 (capa gratuita o educativa).

### 7.7 Reportes (RF17) y auditoría (RNF09)

- **Reporte:** `GET /api/dispositivos/{id}/reporte?desde=&hasta=` usa `reporte_dispositivo()` y agrega la lista de servicios del periodo (fecha, tipo, duración, incidencias). Se exige `desde ≤ hasta`.
- **Auditoría:** `GET /api/auditoria`, solo para el administrador, con filtros por usuario, entidad, acción y fechas.

## 8. Estados

```text
dispositivo:  DISPONIBLE ⇄ EN_CARGA            (manual o por batería tras un servicio)
              DISPONIBLE → EN_SERVICIO → DISPONIBLE | EN_CARGA   (inicio y cierre del servicio)
              cualquiera excepto EN_SERVICIO → EN_MANTENIMIENTO → DISPONIBLE   (RF15)
              cualquiera excepto EN_SERVICIO → FUERA_DE_SERVICIO   (manual o baja RF03; con baja es definitivo)
reserva:      PROGRAMADA → EN_CURSO → FINALIZADA
              PROGRAMADA → CANCELADA          (RF21, o ventana vencida sin iniciar)
              PROGRAMADA → PROGRAMADA         (reprogramar, RF21)
bitácora:     EN_CURSO → [ENTREGADO] → RETORNANDO → FINALIZADO
```

## 9. API REST

**Convenciones:** prefijo `/api`; JSON en español; fechas ISO 8601 en hora de Colombia; paginación con `limite` y `desplazamiento` (por defecto 50); OpenAPI en `/docs` con etiquetas por módulo y el RF en la descripción de cada endpoint. CORS se configura con `CORS_ORIGENES` (por defecto `http://localhost:5173`).

**Formato de error** (también para los 422 de validación):

```json
{ "error": { "codigo": "CRUCE_HORARIO", "mensaje": "El dispositivo R-002 ya tiene la reserva #14 de 10:00 a 10:30.", "detalles": { "reserva_en_conflicto": { "id_reserva": 14 } } } }
```

Códigos: `VALIDACION` (422), `NO_AUTENTICADO` (401), `SIN_PERMISO` (403), `NO_ENCONTRADO` (404), `DUPLICADO`, `CRUCE_HORARIO`, `DISPOSITIVO_NO_APTO`, `CLIMA_NO_APTO`, `TIPO_DISPOSITIVO_INCORRECTO`, `RESERVAS_PENDIENTES`, `REGLA_NEGOCIO` (409), `ERROR_INTERNO` (500, sin detalles internos), `SERVICIO_NO_DISPONIBLE` (503).

| Método | Ruta | Rol | RF | Notas |
|---|---|---|---|---|
| POST | `/api/auth/login` | público | RF20 | Devuelve token, usuario y funciones |
| GET | `/api/auth/yo` | ambos | RF20 | Usuario actual y funciones de su rol |
| POST | `/api/usuarios` | admin | RF18 | |
| GET | `/api/usuarios` | admin | RF18 | Filtros `rol` y `estado` (para elegir operador en la reserva) |
| PATCH | `/api/usuarios/{id}` | admin | RNF01 | Nombre o rol |
| POST | `/api/usuarios/{id}/desactivar` | admin | RF19 | |
| GET | `/api/dispositivos` | ambos | RF04 | Filtros `tipo` y `estado` |
| POST | `/api/dispositivos` | admin | RF01 | |
| GET | `/api/dispositivos/{id}` | ambos | RF04 | Con sensores y último estado |
| PATCH | `/api/dispositivos/{id}` | admin | RF02 | |
| POST | `/api/dispositivos/{id}/baja` | admin | RF03 | |
| GET | `/api/dispositivos/{id}/reporte` | admin | RF17 | `desde`, `hasta` |
| GET | `/api/dispositivos/{id}/mantenimientos` | ambos | RF15 | |
| POST | `/api/dispositivos/{id}/mantenimientos` | ambos | RF15 | |
| POST | `/api/mantenimientos/{id}/cerrar` | ambos | RF15 | |
| GET | `/api/ubicaciones` | ambos | RF05 | Catálogo de origen y destino |
| GET | `/api/zona-operacion` | ambos | RF25 | Polígono |
| GET | `/api/reservas/sugerencia` | admin | RF22, RF23 | Ver 7.4 |
| POST | `/api/reservas` | admin | RF05–RF07, RF23, RF24 | Ver 7.4 |
| GET | `/api/reservas` | ambos | RF05 | Filtros `fecha`, `estado`, `id_dispositivo` |
| GET | `/api/reservas/{id}` | ambos | RF05 | El código de entrega solo lo ve el administrador |
| POST | `/api/reservas/{id}/cancelar` | admin | RF21 | `motivo` |
| POST | `/api/reservas/{id}/reprogramar` | admin | RF21 | `fecha`, `hora_inicio`, `duracion_estimada_min?`, `motivo` |
| GET | `/api/bitacoras` | ambos | RF08 | Filtros `desde`, `hasta`, `id_dispositivo`, `estado` |
| GET | `/api/bitacoras/{id}` | ambos | RF08 | Reserva, dispositivo, operador, incidencias y video |
| GET | `/api/bitacoras/{id}/ruta` | ambos | RF08 | Puntos y lecturas de sensores |
| POST | `/api/bitacoras/{id}/ordenes` | admin | RF14 | `tipo`: `RETORNO_BASE` o `PARADA_EMERGENCIA` |
| GET | `/api/monitoreo` | ambos | RF09 | Foto actual: dispositivos, última telemetría, servicio activo y alertas abiertas |
| GET | `/api/monitoreo/stream` | ambos | RF10, RNF02 | SSE; el token va en `?token=` porque `EventSource` no envía cabeceras. Ese parámetro no se escribe en los logs |
| GET | `/api/alertas` | ambos | RF11, RF16, RF25 | Filtros `tipo`, `atendida`, `id_dispositivo`, fechas |
| GET | `/api/alertas/{id}` | ambos | RF11 | |
| POST | `/api/alertas/{id}/atencion` | ambos | RF27 | `causa_revisada`, `observaciones` |
| GET | `/api/videos` | ambos | RF12, RF13 | Videos guardados al cerrar cada servicio (RF12). Filtros `fecha` o `desde`/`hasta`, `id_dispositivo`, `tipo_servicio`, `incluir_eliminados` |
| GET | `/api/videos/{id}/reproducir` | ambos | RF13 | Enlace firmado |
| GET | `/api/videos/{id}/contenido` | enlace firmado | RF13 | Transmisión con `Range` |
| GET | `/api/auditoria` | admin | RNF09 | |
| GET | `/health` | público | RNF06 | Base de datos, almacenamiento y simulador |

**Controles de demo** (solo con `MODO_DEMO=true`, solo administrador). Sirven para mostrar cada regla en la presentación sin esperar:

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/api/demo/reservas/{id}/iniciar` | Inicia ya el servicio de una reserva `PROGRAMADA` |
| POST | `/api/demo/dispositivos/{id}/eventos` | `tipo`: `BATERIA` (fija un nivel), `FALLA_SENSOR` o `REPARAR_SENSOR` (con el sensor), `SALIR_DE_ZONA`, `VOLVER_A_ZONA`, `PAUSAR`, `REANUDAR` |
| POST | `/api/demo/dispositivos/{id}/codigo-entrega` | Simula que quien recibe digita un código en el robot |
| PUT | `/api/demo/clima` | Fija viento y lluvia del clima falso (con `CLIMA_PROVEEDOR=falso`) |
| POST | `/api/demo/tareas/{nombre}/ejecutar` | Ejecuta ya `mantenimiento-preventivo` (RF16), `retencion-videos` (RF26) o `reintento-subidas` (RF12) |

## 10. Tiempo real (SSE)

`GET /api/monitoreo/stream`: cada mensaje lleva `event:`, `id:` incremental y `data:` en JSON. Cada 15 s se envía un comentario `: ping`. El token se valida al conectar, incluido que el usuario siga activo.

| Evento | Datos principales |
|---|---|
| `telemetria` | `id_dispositivo`, `numero_serie`, `id_bitacora?`, `fecha_hora`, `latitud`, `longitud`, `nivel_bateria`, `sensores[]`, `estado_servicio`, `estado_dispositivo`, `fuera_de_zona` |
| `alerta` | `id_alerta`, `tipo` (`SERVICIO` o `MANTENIMIENTO`), `causa?`, dispositivo, `descripcion`, `latitud?`, `longitud?`, `fecha_hora` |
| `alerta_atendida` | `id_alerta`, operador, `causa_revisada`, `observaciones` |
| `entrega` | `id_bitacora`, `resultado` (`CONFIRMADA` o `NO_CONFIRMADA`), `hora` |
| `orden` | `id_bitacora`, `tipo` |
| `servicio` | `id_bitacora`, `id_reserva`, `evento` (`INICIADO` o `FINALIZADO`) |
| `servicio_en_espera`, `servicio_no_iniciado` | `id_reserva`, `motivo` |

## 11. Simulador de dispositivos (RESTR01)

`ApiDispositivoSimulada` implementa `IApiDispositivo` y guarda en memoria el estado de cada dispositivo: posición, batería, sensores, misión, fase y si está cargando.

- **Datos precargados** (el atributo `datosPrecargados` del diagrama): un `escenario.json` con la posición de la base, los sensores por tipo, el consumo de batería por minuto según el tipo, las rutas precargadas entre ubicaciones (*waypoints* opcionales; si no hay, línea recta) y la probabilidad de fallas aleatorias. Esa probabilidad es **0 por defecto**, para que el simulador sea determinista.
- **Base:** la ubicación del catálogo configurada en `BASE_UBICACION` (por defecto "Base de operaciones"). Ahí empiezan, terminan y se recargan los dispositivos.
- **Misión** (al recibir `enviar_orden_inicio`): la ruta es base → origen → destino → base, omitiendo los tramos repetidos. La velocidad se calcula para completarla en `FRACCION_RECORRIDO` × la duración estimada; así una reserva corta de demo (2–5 min) termina rápido y sin retraso.
  - **Robot:** en el destino espera el código (fase `ESPERANDO_CODIGO`).
  - **Drone:** en el destino graba (`EN_DESTINO`) hasta completar el tiempo previsto y luego regresa.
- **Fases** (van en `estado_servicio` de la telemetría): `EN_BASE`, `EN_RUTA`, `EN_DESTINO`, `ESPERANDO_CODIGO`, `RETORNANDO`, `DETENIDO`.
- **Eventos que el dispositivo envía al servidor** (flechas Dispositivo → Servidor del diagrama de secuencia): `CODIGO_INGRESADO` y `LLEGADA_BASE`. Después el servidor llama a `leer_codigo_entrega()` o `descargar_video()`. La forma de entregarlos (callback o cola en memoria) la decide el plan.
- **Batería:** baja con el tiempo en misión y se recarga en la base.
- **Video:** al llegar a la base entrega un **MP4 de muestra incluido en el repositorio** (≤ 1 MB). Se genera por código, por ejemplo con `imageio-ffmpeg` o PyAV; nada se descarga de internet.
- Cualquier dispositivo nuevo en la base de datos obtiene estado en el simulador sin cambios de código (RNF10).
- Los controles de demo de la sección 9 alteran su estado: batería, sensores, desvío fuera de la zona, pausa (para provocar `RETRASO`) y código de entrega.
- En pruebas usa semilla fija y el `Reloj` simulado.

## 12. Tareas programadas

| Tarea | Frecuencia | RF |
|---|---|---|
| Iniciar reservas | cada 10 s | RF08 |
| Monitoreo | cada `INTERVALO_MONITOREO_SEG` | RF09–RF11, RF25 |
| Mantenimiento preventivo | diaria (06:00) y al cerrar cada servicio | RF16 |
| Retención de videos | diaria (02:00) | RF26 |
| Reintento de subidas pendientes | cada 5 min | RF12 |

## 13. Datos semilla (demo)

El comando `python -m app.semilla` es idempotente y acepta `--reiniciar`. Carga:

- **Usuarios:** 1 administrador y 3 operadores (el enunciado habla de 3 personas), con contraseñas de desarrollo que se documentan en el README.
- **Dispositivos:** 6 en total, 4 robots y 2 drones, con sus sensores. Las baterías varían. Un robot tiene un sensor en `FALLA` (para mostrar RF07) y un drone está cerca de 30 días / 50 h (para mostrar RF16).
- **Ubicaciones y zona:** un campus **de ejemplo** con Base de operaciones, Cafetería, Rectoría, Biblioteca, Bloque A, Bloque B, Coliseo y Cancha principal. Hay que marcarlas como coordenadas de ejemplo para reemplazar por las reales. La zona es un polígono que las contiene todas.
- **Historial:** unos 25 servicios finalizados en los últimos 4 meses, con telemetría (un punto cada ~30 s para no inflar la base), incidencias, alertas, atenciones y videos. Algunos videos tienen más de 3 meses, para mostrar RF26. También hay mantenimientos.
- **Reservas programadas** para hoy y mañana.

## 14. Pruebas y criterios de aceptación

- Pruebas **unitarias** para las reglas puras: umbrales, punto en polígono, tipo requerido y cálculo de alertas. Pruebas de **integración** contra PostgreSQL 16 real en Docker: base de prueba creada con las migraciones y limpiada entre pruebas.
- Cada RF tiene **al menos una prueba** cuyo nombre empieza con su id (`test_rf06_...`). `docs/trazabilidad.md` resume RF → endpoints → clases → pruebas.
- **Casos que deben existir, como mínimo:**
  - **RF01–RF04:** registro con sensores por defecto y número de serie duplicado (409); edición auditada y sin cambio de tipo; baja con reservas pendientes (409) y sin ellas (queda `FUERA_DE_SERVICIO`); filtros del inventario.
  - **RF05** y **RF21:** creación con código de 4 dígitos solo para robots; cancelar exige motivo y libera el horario; reprogramar revalida y solo funciona con la reserva `PROGRAMADA`.
  - **RF09** y **RF10:** `/api/monitoreo` refleja la última telemetría, y el stream SSE emite `telemetria` en cada ciclo.
  - **RF13:** búsqueda con cada filtro; el enlace firmado vencido o alterado responde 403; una petición con `Range` responde 206.
  - **RF15:** registrar pasa el dispositivo a `EN_MANTENIMIENTO`; cerrar lo deja `DISPONIBLE` con las horas en 0; no se permite con el dispositivo en servicio.
  - **RF27:** una sola atención por alerta (la segunda da 409), solo para alertas de servicio, y se emite el evento `alerta_atendida`.
  - **RF06:** cruce rechazado con la reserva en conflicto; reservas contiguas (10:00–10:30 y 10:30–11:00) permitidas; **dos creaciones simultáneas** del mismo horario terminan en un 201 y un 409.
  - **RF07:** batería 29 rechaza y 30 acepta; un sensor en falla rechaza.
  - **RF22:** orden por batería y descarte por cruce, batería, sensor, mantenimiento y baja; respuesta vacía con mensaje cuando no hay ninguno.
  - **RF23:** viento 31 rechaza y 30 acepta; lluvia 61 rechaza y 60 acepta; sin pronóstico, acepta con advertencia.
  - **RF24:** el código correcto deja `ENTREGADO` y la hora; el incorrecto, incidencia y evento; tras 3 errores, el robot regresa.
  - **RF11:** batería 19 genera alerta; retraso de más de 10 min (con el reloj simulado) genera alerta; un sensor en falla genera alerta; sin duplicados.
  - **RF25:** un punto fuera del polígono genera alerta e incidencia con ubicación; el borde cuenta como dentro.
  - **RF14:** la orden llega al simulador y queda como incidencia.
  - **RF08:** hora de salida y de regreso, ruta e incidencias.
  - **RF12** y **RF26:** el video se sube y se asocia; a los 3 meses se borra y se marca la fecha.
  - **RF16:** a los 30 días o 50 h hay una sola alerta, y se reinicia al cerrar un mantenimiento.
  - **RF17:** el reporte trae las cifras esperadas.
  - **RF18–RF20:** registro y login; un usuario desactivado ya no entra y su token deja de servir.
  - **RNF01:** el operador recibe 403 en los endpoints de administrador.
  - **RNF03:** con los datos semilla, los listados de inventario, reservas y bitácora responden en < 3 s.
  - **RNF05:** la contraseña queda con hash.
  - **RNF09:** hay filas de auditoría por cada creación, edición y baja.
  - **RNF10:** se registran 20 dispositivos y el monitoreo los atiende.
  - **RNF02:** prueba de humo (marcada `lenta`) con 6 dispositivos en servicio y una actualización de cada uno en ≤ 5 s.
- Los adaptadores falsos de clima, almacenamiento (local o `moto`) y dispositivo (simulador determinista) se inyectan; ninguna prueba sale a internet.
- `scripts/demo_e2e.py` recorre contra la API en ejecución el flujo completo del diagrama de secuencia: crear reserva, iniciar, telemetría, alerta, atención, entrega con código, cierre con video y reproducción.

## 15. Supuestos y decisiones (para validar con el equipo)

1. Tipo requerido por servicio: entregas → robot, grabación → drone (del enunciado).
2. RF23 evalúa el peor valor de cada hora del rango de la reserva, en el destino. Sin pronóstico disponible, acepta con advertencia.
3. RF24: espera de 5 min y 3 intentos. El aviso de código incorrecto es un evento del panel, no una `alerta_servicio`.
4. Base de operaciones como punto de salida y llegada de cada servicio; ruta base → origen → destino → base.
5. El operador también puede consultar todo y registrar mantenimientos y atenciones; el administrador puede hacer todo.
6. Cancelar una reserva y desactivar un usuario se auditan como `BAJA`; reprogramar, como `EDITAR`.
7. Videos en AWS S3 (RESTR04); almacenamiento local para desarrollo.
8. Las coordenadas del campus son de ejemplo.

Las decisiones que se tomen durante la construcción se anotan en `docs/decisiones.md`.
