# Decisiones del backend

> **Alcance final del proyecto: los 12 RF de la entrega 1.** Donde este documento dice "pendiente" o "entrega 2",
> léase **fuera del alcance**: el profesor pidió 12 requisitos y los otros 15 no se implementaron.

> Decisiones tomadas durante la construcción, con el porqué. Completan la especificación donde quedó
> abierta; no la contradicen. Si una decisión cambia, se marca como reemplazada y se agrega la nueva.
> Orden de prioridad de los documentos: `requisitos.md` > `esquema_bd.sql` > `especificacion-backend.md`
> > diagramas.
>
> **Este repositorio es la entrega 1.** El backend se construyó completo (fases 0 a 5) y después se separó el núcleo.
> Las decisiones sobre los RF de la entrega 2 se tomaron al construirlos; su código no está aquí, pero siguen
> valiendo como guía para implementarlos. La tabla de `docs/trazabilidad.md` lista cada RF
> pendiente.

## Cierre del proyecto (2026-11-09)

| ID | Decisión | Por qué |
|---|---|---|
| C-1 | El alcance final son los 12 RF de la entrega 1. Los otros 15 no se implementan y se marcan "fuera del alcance" en `docs/trazabilidad.md`. Se borran `docs/como-continuar.md`, `docs/plan.md` y `docs/pendientes-backend.md`. | El profesor pidió 12 requisitos y el proyecto no tendrá más desarrollo. |
| C-2 | **Ajusta E1-3.** La semilla es mínima: 2 usuarios (la administradora Emily Bonilla y el operador Santiago Figueroa), los 6 dispositivos, el campus de ejemplo y 5 reservas (3 terminadas con ruta, video y 2 alertas; 2 programadas para mañana). No crea registros de auditoría y ya no usa `R-004` en el historial. | Que en la demostración el equipo cree en vivo los usuarios, dispositivos y reservas. El operador es obligatorio: `fn_validar_reserva` exige un operador activo en cada reserva. `R-004` tiene el LIDAR en falla y RF07 no deja reservarlo, así que un servicio suyo en el historial era inconsistente. |
| C-3 | `GET /api/monitoreo` serializa la `telemetria` con `a_json`, igual que el evento SSE: `fecha_hora` llega con `-05:00`. | Antes llegaba sin desfase, contra la decisión T7 y la guía. |
| C-4 | `POST /api/reservas` revisa la fecha, el origen, el destino y el operador juntos y responde todos los campos con error en una sola respuesta (`ErrorValidacion.de_campos`). Con uno solo, el mensaje es el de ese campo; con varios, "Hay N datos por corregir.". | Que el usuario corrija todo de una vez y no un error por envío. |
| C-5 | El `mensaje` de `CRUCE_HORARIO` muestra la fecha como DD/MM/AAAA. `detalles.reserva_en_conflicto.fecha` sigue en ISO. | El mensaje es para personas; el detalle, para el programa. |

## Entrega 1 — este repositorio (2026-11-08)

| ID | Decisión | Por qué |
|---|---|---|
| E1-1 | El repositorio de la entrega 1 es una copia de los archivos versionados del proyecto completo (commit `427fe8a`) sin los 15 módulos (`app/modulos/rfXX_…`) ni sus pruebas (`tests/modulos/rfXX_…`), sin `PROMPT_BACKEND.md` y con un historial git nuevo de un solo commit. | Para subir al repositorio del grupo solo lo de la entrega 1. El núcleo ya funcionaba sin los módulos (`pytest --solo-entrega-1`), así que no hubo que cambiar su lógica. |
| E1-2 | Se conservan `app/modulos/__init__.py` (el mecanismo que descubre los módulos, que importan `main.py` y `contenedor.py`) y `tests/modulos/conftest.py` (enciende los módulos en sus pruebas). Las dos carpetas no tienen ningún módulo. | Sin el primero la API no arranca. Con los dos, agregar un RF pendiente es solo crear su carpeta, como explica `docs/arquitectura.md`. |
| E1-3 | **Ajusta F5-7.** La semilla trae solo datos de la entrega 1: sin zona de operación (RF25), mantenimientos (RF15), atenciones (RF27), videos eliminados (RF26) ni hora de entrega (RF24). Quedan 3 alertas de servicio (batería, sensor y retraso), todas sin atender, y `D-002` ya no está cerca de las 50 h. | Que la demo no muestre datos de funciones que no existen. Quien implemente un RF pendiente agrega sus datos a `app/semilla.py`; las tablas ya existen. |
| E1-4 | **Ajusta F5-8.** `scripts/demo_e2e.py` recorre solo los 12 RF: inventario, reserva con los rechazos de RF06 y RF07, inicio, telemetría, alerta, cierre con video, ruta y consulta de alertas. Ya no tiene pasos de módulos. | Que funcione y se entienda sin los módulos. RF01 y RF18 no se recorren para no dejar datos de más en cada corrida; los cubren las pruebas y `docs/demo.md`. |
| E1-5 | `docs/guia-frontend.md`, `docs/demo.md` y `backend/tests/http/api.http` describen solo lo que existe; lo pendiente va en secciones aparte con su sección de la especificación. Los comentarios del código que decían que un módulo existía ahora dicen que está pendiente. | La guía del frontend debe coincidir con el código, y nadie debe buscar un archivo que no está. |
| E1-6 | `.env.example` documenta `COMPOSE_PROJECT_NAME` (comentado) y separa los parámetros de negocio de la entrega 1 de los de los RF pendientes, que siguen en la configuración. | Para correr esta copia junto al proyecto completo en la misma máquina sin compartir contenedores, volúmenes ni puertos. Quien implemente un RF encuentra sus parámetros listos. |

**Para validar con el cliente o el equipo** (vienen de la verificación final del proyecto completo y aplican a la
entrega 1):

1. **RESTR04:** los videos van a disco local por defecto (P3). Para cumplir RESTR04 en la demo, el equipo debe
   crear el bucket y configurar `ALMACENAMIENTO=s3` (README). El adaptador está probado con `moto`.
2. **RNF05 (HTTPS):** documentado en el README, no implementado en local. Alternativa: un servicio opcional de Caddy
   en Compose con certificado local.
3. **Demo en producción:** los controles de demo no se auditan (D13) y `MODO_DEMO=true` viene activado en
   `.env.example` para desarrollo; en un despliegue real debe ir en `false`.
4. **Coordenadas:** las del campus son de ejemplo (`backend/app/semilla.py`).

Al implementar RF17, RF13 y RF27, revisar también los puntos 3, 4 y 6 de "Verificación final del proyecto
completo".

## Fase 0 — aprobadas el 2026-11-07

### Preguntas que respondió el equipo

| ID | Decisión | Por qué | Alternativa descartada |
|---|---|---|---|
| P1 | **Al reiniciar el backend, los servicios abiertos se reanudan siempre:** desde su último punto de telemetría o, si no hay ninguno, desde la base. | La especificación pide cerrar "con una incidencia" el servicio que no se pueda reanudar, pero `tipo_incidencia` no tiene un valor que lo describa. Reanudar siempre es posible: la reserva, la bitácora y la ruta están en la BD, y el trigger impide dar de baja un dispositivo con un servicio en curso. Así ese caso no ocurre y el esquema no cambia. | Migración 0002 con `ALTER TYPE tipo_incidencia ADD VALUE 'INTERRUPCION'`. |
| P2 | **Desactivar un operador que tiene reservas programadas está permitido, con una advertencia** que lista esas reservas. Si una de ellas llega a su hora, el servicio se inicia igual y el operador queda como dato histórico en la bitácora. | RF21 solo permite cancelar o reprogramar, así que no hay cómo cambiar el operador de una reserva sin salirse del SRS. La advertencia le da al administrador lo que necesita para cancelarlas y crearlas de nuevo con otro operador. El dispositivo trabaja solo, así que no hace falta bloquear el inicio. | Aceptar `id_operador` opcional al reprogramar (extiende RF21). |
| P3 | **Desarrollo y pruebas con `ALMACENAMIENTO=local` y S3 simulado con `moto`; el adaptador `AlmacenamientoS3` queda listo.** Para la demo, el equipo crea un bucket privado en AWS (capa gratuita) y pone las credenciales en `.env`. Si no hay bucket, la demo corre en local y RESTR04 queda como configuración documentada. | Las pruebas no pueden salir a internet y nadie del equipo debe subir credenciales al repositorio. Cambiar de local a S3 es solo configuración, sin cambios de código. | — |

### Huecos que se resolvieron sin cambiar el comportamiento pedido

| ID | Decisión | Por qué |
|---|---|---|
| D1 | Al registrar un dispositivo, el estado es opcional: `DISPONIBLE` por defecto, también se acepta `EN_CARGA` o `FUERA_DE_SERVICIO`, y nunca `EN_SERVICIO` ni `EN_MANTENIMIENTO`. | RF01 se contradice: pide "estado inicial" y luego dice "guarda con estado Disponible". La especificación (7.2) lo resuelve así, y los dos estados excluidos solo los maneja el sistema. |
| D2 | Cambios a las interfaces del diagrama (ver la sección "Cambios para el diagrama de clases"). | Hacen falta para que un solo simulador atienda todos los dispositivos, para devolverle al robot el resultado de la entrega y para transmitir video con `Range`. |
| D3 | RF23 revisa cada hora cuyo intervalo se cruza con la reserva (10:15–11:15 revisa las 10:00 y las 11:00) y toma el peor viento y la peor lluvia. | Open-Meteo da pronósticos por hora. Tomar el peor valor es lo más seguro para un vuelo. |
| D4 | La espera del código de entrega (5 min) y los intentos (3) los controla el servidor. Los intentos se cuentan con las incidencias `ENTREGA_NO_CONFIRMADA` y el inicio de la espera es el primer punto `ESPERANDO_CODIGO` guardado. | Son reglas de negocio configurables por variables de entorno, se prueban con el reloj simulado y, como viven en la BD, sobreviven a un reinicio. |
| D5 | Un dispositivo `EN_CARGA` pasa solo a `DISPONIBLE` cuando su batería llega al 100 %. | La especificación dice cuándo entra a `EN_CARGA` (batería < 30 % al cerrar un servicio, o a mano), pero no cuándo sale. Sin esta regla se quedaría en carga para siempre. |
| D6 | Un dispositivo `EN_MANTENIMIENTO` se puede editar (modelo, capacidad o autonomía), pero no se puede cambiar su estado mientras el mantenimiento esté abierto: responde 409 "cierre el mantenimiento". | RF15 dice que la salida de mantenimiento ocurre al cerrarlo. Cambiar el estado a mano dejaría un mantenimiento abierto con el dispositivo disponible. |
| D7 | Si un administrador registra un mantenimiento, debe indicar el operador responsable (422 si no lo hace). Si el dispositivo tiene reservas programadas, el mantenimiento se registra con una advertencia. | La columna `mantenimiento.id_operador` es el responsable (RF15: lo registra el operador). La advertencia sigue el mismo criterio que RF02. Esas reservas no se inician mientras el mantenimiento dure (7.5). |
| D8 | RF16 no alerta a dispositivos dados de baja ni con un mantenimiento abierto. | No tiene sentido pedir un mantenimiento preventivo a un equipo retirado o que ya está en mantenimiento. |
| D9 | Toda fecha y hora que escribe la aplicación sale del `Reloj` (creación, auditoría, incidencias, fecha de registro); los `DEFAULT now()` de la BD quedan solo de respaldo. | Así las pruebas con reloj simulado son coherentes (por ejemplo, simular 10 min de retraso o 3 meses de antigüedad). |
| D10 | `Usuario` es una sola clase con `rol`. `Robot`/`Drone` y `AlertaServicio`/`AlertaMantenimiento` sí son subclases (herencia de SQLAlchemy). | Cambiar el rol (RNF01) cambiaría la clase del objeto, y SQLAlchemy no maneja bien ese cambio. El tipo de un dispositivo o de una alerta nunca cambia. |
| D11 | Un token de un usuario desactivado responde **401** `NO_AUTENTICADO` ("Usuario inactivo"). El login de un usuario inactivo responde **403**, como dice 7.1. El rol se lee de la BD en cada petición, no del token. | Con 401 el frontend cierra la sesión: el token "deja de servir" (RF19). Leer el rol de la BD hace que un cambio de rol aplique de inmediato. |
| D12 | La validación "no en el pasado" acepta el minuto en curso. La hora de inicio se guarda sin segundos. | Si no, una reserva para "ya" fallaría por segundos. Además, los formularios trabajan en HH:MM. |
| D13 | **Qué se audita (RNF09).** Se auditan: `usuario` (CREAR, EDITAR, BAJA al desactivar), `dispositivo` (CREAR, EDITAR, BAJA), `mantenimiento` (CREAR, EDITAR al cerrar), `reserva` (CREAR, EDITAR al reprogramar, BAJA al cancelar), `atencion_alerta` (CREAR) y la `incidencia` que crea una orden RF14 (CREAR). Los sensores van dentro del CREAR de su dispositivo. No se auditan el login, las acciones automáticas ni los controles de demo. | RNF09 pide auditar lo que hace un usuario. Lo automático queda en la bitácora (especificación, sección 4). Los controles de demo simulan al dispositivo o al reloj, no son acciones de negocio. |
| D14 | Las "alertas abiertas" del monitoreo son las alertas de servicio sin atención y las de mantenimiento que no tienen un mantenimiento registrado después. El filtro `atendida` de `GET /api/alertas` solo aplica a las alertas de servicio. | Solo las alertas de servicio se atienden (RF27). Una alerta de mantenimiento se resuelve registrando el mantenimiento. |
| D15 | `POST /api/demo/reservas/{id}/iniciar` aplica las mismas validaciones del inicio automático y solo se salta la hora. El retraso se mide contra el horario reservado. Para mostrar `RETRASO` en la presentación sin esperar 10 min, se baja `RETRASO_ALERTA_MIN` en el `.env` de la demo. | Así el control de demo no se salta reglas de negocio. Los umbrales ya son configurables (especificación, sección 6). |
| D16 | RF26 borra un video cuando `fecha_grabacion::date + 3 meses ≤ hoy`, contando meses de calendario (31 de agosto + 3 meses = 30 de noviembre). | Es la regla de la especificación (sección 6) y coincide con "cuando un video cumpla 3 meses" de RF26. |
| D17 | **Para validar con el cliente** (ver "Verificación final"): RF17 dice "servicios realizados". RF17 usa `reporte_dispositivo()` sin cambios. La lista de servicios que acompaña al reporte muestra el estado de cada uno. | La función SQL está probada y tiene prioridad sobre la especificación. Cuenta los servicios que salieron en el rango, incluidos los que siguen en curso, y suma horas solo de los cerrados. La lista aclara cuáles están abiertos. |
| D18 | Una telemetría repetida para el mismo instante (`uq_telemetria_punto`) se omite sin error. | Solo puede pasar si el reloj no avanzó entre dos ciclos de monitoreo, por ejemplo en pruebas. Perder ese punto no afecta la ruta. |
| D19 | La zona de operación es la que se llama como `ZONA_OPERACION` (por defecto, la única que haya). Si no hay zona, RF25 no se evalúa y se avisa en el log y en `/health`. | El diagrama asocia `MonitorServicios` con **una** `ZonaOperacion`, pero la tabla admite varias. |
| D20 | Un video eliminado por retención responde 404 al pedir su enlace o su contenido, y sigue apareciendo en la búsqueda con `incluir_eliminados=true`. | El objeto ya no existe en el almacenamiento, pero el registro conserva la fecha de eliminación (RF26). |

### Decisiones técnicas

| ID | Decisión | Por qué |
|---|---|---|
| T1 | Dependencias con **uv** (`pyproject.toml` + `uv.lock`), versiones fijadas y verificadas en Python 3.12.14. | El *lockfile* hace que todos instalen exactamente lo mismo. La imagen Docker y las pruebas locales en Windows usan el mismo archivo. |
| T2 | Tareas con **APScheduler 3.11** (`AsyncIOScheduler`, zona America/Bogota, `max_instances=1`, `coalesce`), más una tarea `asyncio` permanente que consume los eventos del dispositivo. | La especificación lo permite. Las tareas diarias (06:00 y 02:00) quedan con *cron* en hora local, y una vuelta de monitoreo nunca se solapa con la siguiente. |
| T3 | El simulador **no tiene hilo propio**: cada consulta avanza su estado desde la anterior hasta `reloj.ahora()`. | Es determinista con el reloj simulado (avanzar 10 min = una consulta) y exacto con el reloj real. Las pruebas no tienen que esperar. |
| T4 | Los eventos del dispositivo al servidor (`CODIGO_INGRESADO`, `LLEGADA_BASE`) van a una **cola en memoria** (`asyncio.Queue`). | La especificación deja la forma abierta. Una cola separa al "dispositivo" del servidor como en el diagrama de secuencia, y en las pruebas se vacía a mano. |
| T5 | Un **`asyncio.Lock` por dispositivo** serializa el monitoreo, los eventos, las órdenes y el inicio de servicio. | Evita que dos operaciones choquen sobre la misma bitácora; por ejemplo, cerrar el servicio mientras el ciclo pasa la bitácora a `RETORNANDO`. Es posible porque corre un solo proceso. |
| T6 | Las pruebas de SSE y de RNF02 levantan un `uvicorn.Server` real dentro del mismo *event loop*. Las demás usan `httpx.ASGITransport`. | `ASGITransport` espera a que termine la respuesta, y un flujo SSE no termina. |
| T7 | Las fechas y horas se aceptan con o sin zona (sin zona se asume America/Bogota) y se devuelven con `-05:00`. | Así el navegador las interpreta bien aunque el equipo no esté en hora de Colombia. Colombia no tiene horario de verano, así que el desfase es fijo. |
| T8 | La sugerencia (RF22) devuelve también los operadores activos. | RNF07: el formulario de reserva queda completo con una sola llamada, y crear una reserva toma dos pasos (sugerir y confirmar). |
| T9 | El video de muestra es H.264 en MP4, generado con PyAV (`scripts/generar_video_muestra.py`) y guardado en el repositorio. | H.264 lo reproducen Chrome, Firefox y Edge (RESTR03), y PyAV trae `libx264` en su *wheel*, así que no se descarga nada. |
| T10 | En Windows, las pruebas y el arranque local fijan el *selector event loop*. | psycopg en modo async no funciona con el `ProactorEventLoop`, que es el predeterminado en Windows. |
| T11 | Los parámetros `token` y `firma` se ocultan en el log de accesos. El SSE vuelve a validar cada 30 s el token y que el usuario siga activo. | La especificación pide no escribir el token en los logs. La revalidación cumple RF19 ("queda fuera de inmediato") también en conexiones largas. |

## Fase 1 — base (2026-11-07)

| ID | Decisión | Por qué |
|---|---|---|
| F1-1 | La API aplica `alembic upgrade head` al arrancar el contenedor, antes de Uvicorn. | Así `docker compose up` deja la base lista sin pasos extra. El comando manual sigue disponible (`docker compose exec api alembic upgrade head`). |
| F1-2 | La migración 0001 ejecuta el script con `exec_driver_sql(..., no_parameters=True)`. | Sin parámetros, psycopg envía el script completo tal cual, con varias sentencias, los cuerpos `$$` y los `%` de los `RAISE`. Ninguna línea del SQL se toca. |
| F1-3 | La imagen de Compose usa la etapa `dev`, con pytest, moto y ruff, y monta `backend/` y `docs/` como volúmenes. | Así las pruebas corren en Linux con `docker compose exec api pytest` sin reconstruir la imagen. La prueba de copia literal lee `docs/` montado en `/docs`. La etapa `prod` queda lista sin herramientas de prueba. |
| F1-4 | La base de pruebas (`<base>_test`, o `BD_URL_PRUEBAS`) se borra y se recrea en cada corrida, y su nombre debe contener `test`. | Cada corrida prueba la migración 0001 desde cero. La regla del nombre evita borrar por error la base de la demo. |
| F1-5 | PyJWT no valida `exp` ni `iat`: el `EmisorTokens` los compara contra el `Reloj`. | PyJWT usa la hora del sistema, lo que rompía la regla "nadie llama a `datetime.now()`" y no dejaba simular el vencimiento en las pruebas. |
| F1-6 | El costo de Argon2 es configurable (`ARGON2_ITERACIONES`, `ARGON2_MEMORIA_KIB`). En producción vale 3 iteraciones y 64 MiB; en las pruebas, el mínimo. | Las pruebas crean muchos usuarios y no deben tardar. El cifrado corre en un hilo aparte (`asyncio.to_thread`) para no frenar el monitoreo ni el SSE. |
| F1-7 | Las subclases de alerta usan `polymorphic_load="inline"` y la atención se carga con `selectin`. | En modo async no hay cargas perezosas: así un listado de alertas trae subclase y atención sin consultas ocultas. |
| F1-8 | Las relaciones de los modelos usan `lazy="raise"` salvo las pequeñas (sensores, vértices). | Una carga perezosa olvidada falla de inmediato y con un mensaje claro, no con un error de greenlet difícil de rastrear. |
| F1-9 | Para cambiar el rol de un administrador o desactivarlo, se bloquean las filas de los administradores activos siempre en orden de id. | Dos cambios simultáneos no pueden dejar el sistema sin administradores, y el orden fijo de los bloqueos evita *deadlocks*. |
| F1-10 | 405 responde con el código `METODO_NO_PERMITIDO`. | El formato único de error debe cubrir todos los casos; la especificación no lista un código para 405. |
| F1-11 | La configuración busca el `.env` en la raíz y en `backend/` (el de `backend/` tiene prioridad). | Compose lee el de la raíz, y `uv run` desde `backend/` encuentra el mismo archivo. |
| F1-12 | ~~Los puertos de la base y de la API se configuran en `.env` (`PUERTO_BD`, `PUERTO_API`).~~ **Reemplazada por I-1 e I-2.** | En el equipo de desarrollo el 5432 ya lo usaba otro proyecto. |
| F1-13 | Ruff con largo de línea 120 y `ruff format`. | Los textos en español son largos y el formateador no parte cadenas. |

## Ajuste de infraestructura: convivir con otros proyectos Docker (2026-11-07, pedido del equipo)

| ID | Decisión | Por qué |
|---|---|---|
| I-1 | Por defecto, la base se publica en el **5433** y la API en el **8010**; los dos puertos se cambian en el `.env` (`PUERTO_BD`, `PUERTO_API`). | El 5432 y el 8000 son los que más usan otros proyectos, por ejemplo `geovisor_bt` en este equipo. Con estos valores nadie del equipo tiene que cambiar nada al copiar `.env.example`. |
| I-2 | Lo que corre en la máquina arma la URL de la base sola con `127.0.0.1:PUERTO_BD` y los `POSTGRES_*` (`ConfiguracionBD.url_bd`); `BD_URL` queda vacío y solo sirve para apuntar a otra base. Dentro de Compose, `BD_URL` se fija a `db:5432`. | Así el puerto se configura en un solo lugar. Antes había que cambiar `PUERTO_BD` y además el puerto dentro de `BD_URL`. |
| I-3 | Los puertos se publican en `127.0.0.1` por defecto (`IP_PUBLICACION`). | La base de desarrollo no queda expuesta en la red local. `geovisor_bt` hace lo mismo. |
| I-4 | El proyecto Compose se llama `robots-drones` y no fija `container_name`. | Los contenedores, los volúmenes y la red llevan ese prefijo, así que no chocan con los de otros proyectos. |
| I-5 | Alembic toma la URL de `ConfiguracionBD`, que no exige `JWT_SECRETO`. | Migrar desde la máquina funciona sin la configuración completa de la API. |
| I-6 | El host por defecto de la base en la máquina es `127.0.0.1`, no `localhost` (`HOST_BD`). | En Windows, `localhost` prueba primero `::1` (IPv6), donde Compose no publica, y cada conexión nueva esperaba el rechazo: 10 s con psycopg frente a 0,04 s con `127.0.0.1`. Las pruebas pasaban de 25 s a varios minutos. |

## Entregas: núcleo y módulos removibles (2026-11-07, pedido del equipo)

La entrega 1 lleva RF01, RF04, RF05, RF06, RF07, RF08, RF09, RF10, RF11, RF12, RF18 y RF20. Los otros 15 se
entregan después. Se construyen todos, pero los 15 deben poder quitarse limpiamente. La regla está en
`CLAUDE.md`; estas son las decisiones que la concretan.

| ID | Decisión | Por qué |
|---|---|---|
| M-1 | Cada RF removible es un paquete `app/modulos/rfXX_nombre/` que expone `MODULO = ModuloRF(...)` y **se descubre solo** (`pkgutil`). | Para quitarlo basta con borrar la carpeta: no hay listas que mantener en otros archivos. |
| M-2 | El núcleo ofrece **puntos de extensión** (`app/nucleo/extensiones.py`): validadores de reserva, evaluador de clima, ajustes de la orden de inicio, verificaciones del monitor, manejadores de eventos del dispositivo, acciones al cerrar un servicio, tareas programadas, eventos de demo, chequeos de salud y funciones de menú. | El núcleo nunca importa un módulo; los módulos se enganchan. Una prueba (`test_modulos.py`) revisa con `ast` que ningún archivo del núcleo, ni de sus pruebas, importe `app.modulos.rf…`, y que un módulo no importe otro. |
| M-3 | `MODULOS_ACTIVOS` (`todos`, `ninguno` o una lista como `rf02,rf03`) apaga módulos sin borrar código. | Así se puede preparar o mostrar la entrega 1 sin tocar el repositorio. |
| M-4 | Las pruebas del núcleo corren con **todos los módulos apagados**; las de `tests/modulos/` los encienden todos. `pytest --solo-entrega-1` corre solo el núcleo. | Cada prueba tiene un entorno fijo, y la corrida del núcleo solo demuestra que los 12 no dependen de los 15. Los flujos completos con todo encendido quedan en las pruebas de los módulos y en `demo_e2e.py`. |
| M-5 | Los modelos de las 18 tablas siguen en el núcleo, y también las consultas de solo lectura que comparten varios módulos (`app/mantenimiento/consultas.py`). | El esquema es literal y completo; borrar un módulo no toca la base. |
| M-6 | El **código de entrega de 4 dígitos se genera en el núcleo** (RF05), aunque RF24 sea removible. | El trigger `fn_validar_reserva` exige el código en toda reserva de robot. RF24 aporta la espera del robot en el destino y la confirmación del código. Sin RF24, el robot deja el pedido y vuelve (Fase 4). |
| M-7 | `GET /api/alertas` (consulta de alertas) es del núcleo (RF11). La atención (RF27), las alertas de salida de zona (RF25) y las de mantenimiento (RF16) son de sus módulos. | RF11 pide mostrar las alertas; el listado sirve para todos los tipos y no depende del código de los módulos. |
| M-8 | El video almacenado se ve en el detalle de la bitácora (RF12, núcleo). La búsqueda, el enlace firmado y la transmisión con `Range` (`/api/videos…`) son del módulo RF13. | RF12 termina en "asocia el enlace del video al servicio en la bitácora"; buscar y reproducir es RF13. |
| M-9 | Los métodos del diagrama que solo usa un RF removible viven en su módulo: `MonitorServicios.enviar_orden` (RF14), `recibir_codigo_entrega` (RF24), `verificar_zona` (RF25), `AlertaServicio.registrar_atencion` se usa desde RF27, y `GestorReservas.cancelar_reserva`/`reprogramar_reserva`/`sugerir_dispositivo`/`validar_clima` están en RF21, RF22 y RF23. | Así se quitan junto con su módulo. El equipo debe anotarlo en el diagrama de clases (paquetes por entrega). |
| M-10 | El detalle de un dispositivo (RF04) ya no trae `mantenimiento_abierto`; eso se consulta con `GET /api/dispositivos/{id}/mantenimientos` (RF15). | El núcleo no debe mostrar datos de un RF removible. |
| M-11 | `POST /api/auth/login` y `GET /api/auth/yo` devuelven `requisitos_activos` (los 12 del núcleo más los módulos encendidos), además de `funciones`. | El frontend necesita saber qué hay. Algunos RF no tienen una función de menú propia (por ejemplo, RF21 dentro de `reservas.gestionar`). |
| M-12 | RF22 usa el clima solo si hay un `evaluador_clima` registrado (lo registra RF23). | Así RF22 y RF23 se pueden quitar por separado. |

## Fase 2 — inventario y mantenimiento (2026-11-07)

| ID | Decisión | Por qué |
|---|---|---|
| F2-1 | El número de serie se guarda sin espacios y en mayúsculas (`r-010` → `R-010`). | Para la base son distintos, pero para una persona son el mismo serial. Así se evitan duplicados por mayúsculas. |
| F2-2 | En el inventario, `sensores_en_falla` es la lista de nombres (vacía si no hay), igual que en la sugerencia. | Con la lista el frontend muestra el nombre del sensor y también puede contarlos. |
| F2-3 | Dar de baja un dispositivo con un mantenimiento abierto lo cierra (con la fecha de la baja, auditado como `EDITAR mantenimiento`) y devuelve la advertencia `MANTENIMIENTO_CERRADO`. | La especificación permite la baja desde cualquier estado salvo en servicio, y no tiene sentido un dispositivo retirado con un mantenimiento abierto. |
| F2-4 | La fecha de baja y la fecha de inicio de un mantenimiento no pueden ser futuras ni anteriores al registro del dispositivo (422). La fecha de fin no puede ser futura ni anterior al inicio. | Son fechas de hechos ocurridos. El CHECK `ck_mant_fechas` es la última barrera. |
| F2-5 | Editar, dar de baja, registrar y cerrar mantenimiento bloquean la fila del dispositivo con `FOR UPDATE`, **siempre antes** que la del mantenimiento. | Evita condiciones de carrera (dos mantenimientos abiertos, baja simultánea) sin *deadlocks*. En la Fase 3, crear una reserva tomará la misma fila con `FOR SHARE`, así una baja y una reserva simultáneas se ordenan. |
| F2-6 | **La deduplicación la reemplaza F5-10.** RF16 se serializa con un *advisory lock* de PostgreSQL (`pg_advisory_xact_lock`). La deduplicación compara fechas: hay alerta si `fecha_hora::date > último mantenimiento`. | Así la tarea diaria y la revisión al cerrar un servicio no crean dos alertas a la vez. Con `>` estricto, una alerta del mismo día en que se cerró el mantenimiento no tapa la del siguiente ciclo de 30 días. |
| F2-7 | `/health` responde 503 solo si cae una dependencia crítica (base de datos, almacenamiento). Las demás, como `zona_operacion` de RF25, ponen `estado: degradado` con 200. | Una zona sin configurar impide RF25, pero la API sigue sirviendo todo lo demás. |
| F2-8 | Si hay varias zonas y `ZONA_OPERACION` está vacío, se usa la de menor id y se avisa en el log. | Completa D19, que solo trataba el caso de una o ninguna. |
| F2-9 | En `.env.example`, los comentarios van siempre en su propia línea (una prueba lo verifica). | Docker Compose leía `ZONA_OPERACION=   # texto` como si el valor fuera `# texto`; dentro del contenedor, RF25 buscaba una zona con ese nombre. |

## Fase 3 — reservas (2026-11-07)

| ID | Decisión | Por qué |
|---|---|---|
| F3-1 | **Reemplazada en la Fase 4** (el simulador ya implementa misiones, órdenes, código y video). `IApiDispositivo` se define completa en esta fase. `ApiDispositivoSimulada` trae el estado de cada dispositivo (batería, sensores, posición en la base, cargado solo desde la base) y los controles de batería y sensores. Las misiones, órdenes, códigos y video llegan en la Fase 4; mientras tanto esos métodos responden `NotImplementedError`. | RF07 exige consultar la batería y los sensores al dispositivo "en ese momento". |
| F3-2 | La lectura de RF07 se guarda en `dispositivo.nivel_bateria` y `sensor.estado` en su **propia transacción**, antes de guardar la reserva. | Es la lectura más reciente y vale aunque la reserva se rechace. Además evita un *deadlock*: si dos creaciones simultáneas actualizaran la fila del dispositivo mientras la tienen con `FOR SHARE`, se bloquearían entre sí. |
| F3-3 | Al guardar, la reserva toma la fila del dispositivo con `FOR SHARE` y vuelve a revisar su estado. | Dos reservas pueden avanzar a la vez (decide el `EXCLUDE`), pero una baja simultánea, que toma `FOR UPDATE`, queda en orden. Así se completa la decisión F2-5. |
| F3-4 | Si la base rechaza la reserva por `ex_reserva_cruce` (23P01), se deshace la transacción, se busca la reserva en conflicto y se responde igual que en la validación del servicio: 409 `CRUCE_HORARIO` con `reserva_en_conflicto`. | La especificación pide devolver la reserva en conflicto también en el caso concurrente. Una prueba fuerza ese camino saltándose la validación del servicio. |
| F3-5 | Origen, destino y operador inválidos responden 422 con el campo; un dispositivo inexistente responde 404. El detalle del conflicto incluye también el `estado` de la otra reserva. | Origen, destino y operador son datos del formulario; el dispositivo es un recurso. Con el estado se distingue un cruce con una reserva programada de uno con un servicio en curso. |
| F3-6 | Si el dispositivo no responde durante RF07, la respuesta es 503 `SERVICIO_NO_DISPONIBLE`. | Sin la lectura no se puede validar RF07, y no es culpa de los datos de la solicitud. |
| F3-7 | Las rutas con id de reserva usan el convertidor `{id_reserva:int}`. | Así `GET /api/reservas/sugerencia` (módulo RF22) no choca con `GET /api/reservas/{id_reserva}` (núcleo), sin importar el orden en que se incluyan los routers. |
| F3-8 | Reprogramar (RF21) también revisa el estado del dispositivo (paso 2), no solo RF06, RF07 y el clima. El código de entrega no cambia. Primero valida sin bloqueos y después bloquea la reserva, verifica que siga PROGRAMADA y guarda. | Reprogramar un dispositivo que entró en mantenimiento no tiene sentido. La validación de RF07 confirma su propia transacción, por eso el bloqueo se toma después. |
| F3-9 | RF23 vive entero en su módulo: `IServicioClima`, `Pronostico`, el adaptador de Open-Meteo y el clima falso. El lugar es el `Punto` del núcleo. La caché de Open-Meteo vence con el reloj monotónico del proceso. Un 400 de la API (más de 16 días) o un dato nulo cuentan como "sin pronóstico". | Quitar RF23 no deja código de clima en el núcleo. La caché no usa una hora de negocio, así que no viola la regla del `Reloj`. |
| F3-10 | La sugerencia (RF22) también guarda la lectura de batería y sensores de cada candidato. Lista los descartados con su motivo, incluido el estado (mantenimiento, baja, fuera de servicio). | Es la misma consulta de RF07, y la especificación pide mostrar los descartes por mantenimiento y baja. |
| F3-11 | `ModuloRF.configurar` recibe la `Configuracion`, y las extensiones tienen un registro `servicios` para los objetos de cada módulo. | RF23 elige su proveedor de clima según `CLIMA_PROVEEDOR`, y el control de demo y las pruebas llegan al clima falso por ese registro. |
| F3-12 | Los controles de demo de los módulos usan la dependencia común `ModoDemo`: sin `MODO_DEMO=true` responden 404. `PUT /api/demo/clima` responde 409 si el proveedor no es el falso. | En producción los controles de demo no deben existir. |
| F3-13 | Las pruebas de un módulo solo importan su propio módulo. Si prueban una interacción con otro (por ejemplo, reprogramar un drone con clima), se omiten cuando el otro no está. | Así borrar un módulo no rompe las pruebas de los demás. `test_modulos.py` lo verifica. |

## Fase 4 — servicio en curso (2026-11-07)

### Núcleo

| ID | Decisión | Por qué |
|---|---|---|
| F4-1 | **Misión del simulador:** base → origen → destino → base en `FRACCION_RECORRIDO` × la duración. El robot reparte ese tiempo entre los tramos según su largo; el drone vuela la mitad y graba en el destino la otra mitad. **Sin RF24, el robot deja el pedido y vuelve:** la bitácora pasa de `EN_CURSO` a `RETORNANDO` y a `FINALIZADO` sin `hora_entrega`. | Es el plan aprobado. Sin el módulo RF24 nadie confirma la entrega, así que no se registra una hora de entrega que nadie verificó. |
| F4-2 | **Batería simulada:** baja 1 %/min (robot) o 2 %/min (drone) durante la misión y sube 2 %/min en la base **solo después de un servicio** (o si la base de datos dice `EN_CARGA` al cargarlo). Un dispositivo que no ha salido conserva su nivel. El control de demo `BATERIA` detiene la recarga. | Si todos se recargaran solos en la base, los niveles de la semilla (que muestran RF07) subirían al 100 % a los pocos minutos de arrancar. Los valores están en `escenario.json`. |
| F4-3 | **Inicio:** bloquea primero la reserva y después el dispositivo (el mismo orden de reprogramar, RF21). Revisa en este orden: ventana vencida → la cancela con "No se inició: …" y el último motivo; dispositivo en otro servicio → `servicio_en_espera`; estado, batería y sensores en ese momento → `servicio_no_iniciado`. Cada motivo se avisa **una sola vez** por SSE, no cada 10 s. Un dispositivo `EN_CARGA` sí puede iniciar si su batería cumple RF07. La orden se envía al dispositivo antes del *commit*: si no la recibe, se deshace todo. | El mismo orden de bloqueo evita *deadlocks* con RF21. `EN_CARGA` no impide crear la reserva, así que tampoco impide iniciarla si ya tiene batería. Enviar la orden antes del *commit* evita una bitácora abierta de un dispositivo que nunca salió. |
| F4-4 | **Alertas sin duplicados:** el monitor guarda en memoria las causas activas de cada bitácora. Una causa vuelve a alertar solo si se normalizó y volvió a ocurrir; `RETRASO` sale una vez por servicio. Después de un reinicio, las causas que ya alertaron en ese servicio cuentan como el mismo episodio. Todas las alertas de servicio guardan la ubicación del dispositivo, no solo `SALIDA_DE_ZONA`. | Es la regla de la especificación (7.5). Reconstruir desde la base evita repetir alertas al reiniciar; el costo es no avisar un episodio que empezó y terminó mientras el backend estaba caído. RF11 y RF25 piden mostrar dónde está el dispositivo. |
| F4-5 | **Ciclo de monitoreo:** cada dispositivo tiene como máximo 0,9 × `INTERVALO_MONITOREO_SEG` para responder. Las transacciones en paralelo se limitan con `MONITOR_CONCURRENCIA` (8). El monitor toma la fila del dispositivo con `FOR UPDATE`. Se monitorean todos los dispositivos que no están dados de baja; la ruta, las alertas y el estado de la bitácora solo cuando hay un servicio abierto. | Así una vuelta nunca se pisa con la siguiente y 20 dispositivos no agotan las conexiones de la base. La especificación pide monitorear "antes, durante y al finalizar". |
| F4-6 | **Cierre:** `hora_regreso` es la hora de llegada que reporta el dispositivo (entre la salida y ahora). `duracion_seg` del video es la duración real del servicio. Se guarda el último punto de la ruta. El dispositivo queda `EN_CARGA` si su batería es menor a `BATERIA_MINIMA_ASIGNACION` (30) y si no `DISPONIBLE`. Las horas se suman con dos decimales. Las acciones de los módulos (`al_finalizar_servicio`, RF16) corren en la misma transacción y sus alertas se publican después del *commit*. | El monitor se entera de la llegada en el siguiente ciclo (≤ 5 s); usar la hora reportada hace exacta la bitácora. El umbral de carga es el mismo de RF07, así que un dispositivo `DISPONIBLE` siempre es asignable. |
| F4-7 | **Video:** se valida que sea MP4 (caja `ftyp`). El objeto se llama `videos/AAAA/MM/bitacora-N.mp4`. El adaptador local escribe en un archivo temporal y lo renombra. Los pendientes son un `.mp4` y un `.json` con sus datos en `PENDIENTES_DIR`; el reintento crea la fila `video` solo si la bitácora no tiene una. | RF12 pide MP4. El nombre por fecha ordena el bucket y facilita revisar la retención (RF26). El renombrado evita objetos a medias, y el `.json` permite crear la fila después aunque el backend se reinicie. |
| F4-8 | **SSE:** sin `?token=` responde 401 (no 422), para que el frontend lo trate como sesión vencida. Cada navegador tiene una cola de 1000 eventos; si se llena, se le cierra el flujo y al reconectarse recupera lo que falte con `Last-Event-ID`. El ping es el comentario `: ping`, y los intervalos se configuran con `SSE_PING_SEG` y `SSE_REVALIDAR_SEG`. | Un navegador lento no debe frenar a los demás ni llenar la memoria. Los intervalos configurables permiten probar el cierre por usuario desactivado sin esperar 30 s. |
| F4-9 | `/health` agrega `almacenamiento` (crítico: 503 si falla) y `simulador` (`ok`, `sin_base` si falta la ubicación base o `detenido` si murió el consumidor de eventos; no crítico). | Sin almacenamiento no se pueden cerrar servicios con video. Sin base, el simulador sigue respondiendo, pero los recorridos saldrían de (0, 0). |
| F4-10 | **Reanudación (P1):** el dispositivo sigue desde su último punto. Si la bitácora ya estaba `ENTREGADO` o `RETORNANDO`, va directo a la base; si estaba `DETENIDO`, sigue detenido hasta un `RETORNO_BASE`. Si no, se calcula en qué tramo del plan iba según el tiempo transcurrido hasta ese punto y continúa desde ahí. `OrdenInicio` lleva estos datos en `reanudacion`. | Completa P1 sin guardar más estado: todo sale de la bitácora y su ruta. Si hubo una pausa antes del reinicio, el cálculo puede adelantar el tramo, lo que es aceptable en un prototipo. |
| F4-11 | Los **controles de demo del núcleo** se adelantan a esta fase: iniciar una reserva, eventos del dispositivo (`BATERIA`, `FALLA_SENSOR`, `REPARAR_SENSOR`, `PAUSAR`, `REANUDAR`, más los de los módulos) y ejecutar tareas (`iniciar-reservas`, `monitoreo`, `reintento-subidas`, más las de los módulos). | Los módulos de esta fase (RF24, RF25) se enganchan a ellos, y sirven para probar a mano. |
| F4-12 | `Dispositivo.motivos_estado` y `Dispositivo.actualizar_lectura` pasan al modelo. | Los usan las reservas y el inicio automático; así la regla está en un solo lugar. |
| F4-13 | Los mensajes de APScheduler en el log se limitan a advertencias y errores. | Si no, el log anota cada vuelta del monitoreo (cada 5 s) y tapa lo importante. |
| F4-14 | **Reemplazada por F5-1** (el adaptador S3 ya existe). El adaptador S3 llega en la Fase 5. Por ahora `ALMACENAMIENTO=s3` falla al arrancar con un mensaje claro. | El cierre con video necesitaba el almacenamiento ya; el plan deja S3 y `moto` para la Fase 5. |

### Módulos (su código no está en este repositorio: guía para implementarlos)

| ID | Decisión | Por qué |
|---|---|---|
| F4-15 | **RF14:** la orden se envía con el candado del dispositivo y la bitácora bloqueada. Se registra como incidencia con la posición del dispositivo justo después de la orden y se audita (CREAR `incidencia`). Si el dispositivo no responde, devuelve 503 y no registra nada; si el servicio ya terminó, 409. | Así la orden no se cruza con el cierre ni con el ciclo de monitoreo, y la bitácora solo guarda órdenes que el dispositivo recibió. |
| F4-16 | **RF24:** cada código incorrecto es una incidencia `ENTREGA_NO_CONFIRMADA` ("intento N de 3"). En el último intento, la descripción dice que el robot regresa sin entregar. El tiempo agotado deja otra incidencia con ese motivo. La espera empieza en el primer punto `ESPERANDO_CODIGO` guardado, así que puede durar hasta un ciclo más (≤ 5 s). Se compara con `≥ ESPERA_ENTREGA_MIN`. Un código que llega cuando el robot ya no espera se ignora. El evento `entrega` trae `intento` (`null` si se agotó el tiempo), `robot_regresa` y `motivo`. | Completa D4 sin contar nada en memoria: la bitácora muestra cada intento y el motivo del regreso. El frontend puede mostrar "intento 2 de 3" y si el robot ya vuelve. |
| F4-17 | **RF25:** la verificación corre para todos los dispositivos (`fuera_de_zona` va en toda telemetría), pero solo alerta si hay un servicio en curso. La zona se lee en cada ciclo. Los eventos de demo `SALIR_DE_ZONA` y `VOLVER_A_ZONA` desplazan la posición reportada según `desvio_salida_zona` de `escenario.json` (0,03° de latitud, unos 3 km). | El mapa del monitoreo puede marcar a cualquier dispositivo fuera de la zona, y RF25 pide la alerta "cuando un dispositivo en servicio salga". Leer la zona en cada ciclo permite corregirla sin reiniciar. |
| F4-18 | **RF27:** el administrador también puede atender (sección 5 de la especificación). `atencion_alerta.id_operador` guarda a quien atendió. Para que dos atenciones simultáneas den 201 y 409, se bloquea solo la fila de `alerta`: con la herencia *joined*, `FOR UPDATE OF` alcanzaría las tablas de las subclases, que van con LEFT JOIN, y PostgreSQL no lo permite. | La matriz de permisos dice "ambos". La columna se llama `id_operador` pero apunta a `usuario`, así que admite a un administrador. |
| F4-19 | **RF16 al cerrar un servicio** se prueba de punta a punta: el cierre suma las horas y, si llegan a 50, la alerta de mantenimiento sale en la misma transacción y se publica por SSE con el evento `servicio` FINALIZADO. | Cierra lo que quedó pendiente de la Fase 2 (la extensión `al_finalizar_servicio` ya existía, pero ningún servicio cerraba todavía). |

## Fase 5 — videos, reportes y cierre (2026-11-08)

| ID | Decisión | Por qué |
|---|---|---|
| F5-1 | `AlmacenamientoS3` corre cada llamada de boto3 en un hilo y usa tiempos máximos (5 s de conexión, 30 s de lectura, 3 intentos). Las credenciales pueden ir en `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` del `.env`; si están vacías, boto3 usa su cadena habitual. Con `ALMACENAMIENTO=s3` y sin `S3_BUCKET`, la API no arranca y lo dice. | boto3 es síncrono y no debe frenar el monitoreo ni el SSE. pydantic-settings lee el `.env` pero no lo exporta al entorno, así que sin esos campos `uv run` no vería las credenciales. |
| F5-2 | **Enlace firmado (RF13):** HMAC-SHA256 con `JWT_SECRETO` sobre video, usuario y expiración (segundos Unix del `Reloj`). Al abrirlo se revisa además que el usuario siga activo. La firma vive en el módulo RF13. | Se usa la clave que ya existe (nunca está en el repositorio) y la regla de RF19 alcanza también a los enlaces. Si RF13 se quita, la firma se va con él. |
| F5-3 | **`Range`:** se atiende el primer rango de `bytes=a-b`, `bytes=a-` o `bytes=-n`; un rango mal escrito se ignora y se envía todo (200); uno fuera del archivo responde 416 con `Content-Range: bytes */tamaño`. El contenido se lee del almacenamiento por partes de 512 KB. | Es lo que piden los reproductores HTML5 (RESTR03). Leer por partes evita cargar videos grandes en memoria. |
| F5-4 | **RF13:** `fecha` y `desde`/`hasta` no se combinan (422). Cada enlace emitido y cada acceso al contenido se escriben en el log `app.videos.accesos` (usuario, video y bytes); el parámetro `firma` se oculta en el log de accesos. | Evita búsquedas ambiguas. RNF08 pide registrar cada acceso sin exponer el secreto. |
| F5-5 | **RF26:** la búsqueda de vencidos se hace en SQL (`fecha_grabacion::date + make_interval(months => 3) <= hoy`) y se confirma con `Video.esta_vencido`. Cada video se marca en su propia transacción después de borrar el objeto. | PostgreSQL ya usa meses de calendario (31-ago + 3 meses = 30-nov, decisión D16). Marcar uno por uno deja bien los que sí se borraron aunque otro falle. |
| F5-6 | **RF17:** `desde` y `hasta` son obligatorios (422 si falta uno) y ambos se incluyen. La lista de servicios agrega `hora_regreso` y `duracion_min` (`null` si no ha terminado). | La función SQL recibe las dos fechas. La lista explica por qué un servicio en curso cuenta en `numero_servicios` pero no en `horas_uso` (D17). |
| F5-7 | **Ajustada en la entrega 1 (E1-3).** **Semilla:** idempotente (si existe el administrador, no hace nada); `--reiniciar` borra los datos **y los videos** y vuelve a sembrar. Inserta directamente en la base (no por la API), con semilla fija para todo menos las horas, que salen del reloj. Los servicios de más de 3 meses tienen el video vigente (para mostrar RF26) y el más antiguo ya aparece eliminado. Las reservas de hoy solo se crean si faltan más de 30 minutos. Después de `--reiniciar` hay que reiniciar la API. | La especificación pide un comando idempotente con `--reiniciar`. Insertar directo permite crear el historial con fechas pasadas, que la API rechaza. El simulador guarda en memoria el estado de los dispositivos y no se entera del borrado. |
| F5-8 | **Ajustada en la entrega 1 (E1-4).** `scripts/demo_e2e.py` usa la hora del servidor (`generado` de `/api/monitoreo`), los controles de demo para no esperar, y salta con aviso los pasos de los módulos apagados. Termina con código 0 o 1. | Así funciona desde Windows o dentro del contenedor, con cualquier `MODULOS_ACTIVOS`, y sirve para verificar una instalación. |
| F5-9 | La colección `tests/http/api.http` usa la sintaxis de REST Client de VS Code (tokens tomados del login). | El equipo trabaja con VS Code; Swagger queda para quien prefiera el navegador. |
| F5-10 | **RF16, deduplicación por ciclo:** cada alerta preventiva guarda `dias_desde_ultimo`, así que su fecha menos esos días es la referencia con que se calculó. Una alerta tapa a otra solo si su referencia es la vigente (o posterior). Una alerta de mantenimiento queda resuelta si después se registró un mantenimiento o si se cerró uno posterior a su referencia. La tarea diaria (y su control de demo) publica por SSE las alertas que crea. **Reemplaza la parte de deduplicación de F2-6.** | Lo encontró la revisión final: con un mantenimiento registrado con fechas pasadas, una alerta vieja tapaba para siempre las del ciclo nuevo y quedaba abierta; y la tarea diaria no avisaba en tiempo real (7.3 pide publicar por SSE). Al corregirlo apareció otro defecto: la consulta no filtraba el tipo y una alerta de servicio posterior al mantenimiento también tapaba la preventiva. Ahora usa la consulta de la subclase. Las tres situaciones tienen prueba. |
| F5-11 | **RF12:** al cerrar, el video se pide al dispositivo hasta 3 veces (con 1 s entre intentos). Si no llega, el servicio se cierra sin video y queda un error en el log. | Lo señaló la revisión final. Sin el archivo no hay nada que dejar pendiente; reintentar la descarga cubre los cortes momentáneos y no deja la bitácora abierta para siempre. |

## Verificación final del proyecto completo (2026-11-08)

> Se hizo sobre el proyecto con los 27 RF. Lo que sigue vigente para la entrega 1 está en "Entrega 1".

- Desde cero (`docker compose down -v` del proyecto y `up --build`): migración 0001 en `head`, semilla, suite
  completa con `--lentas` en el contenedor y `scripts/demo_e2e.py` contra la API (13 pasos, ~100 s).
- Un revisor independiente comparó `requisitos.md` con el código y las pruebas, RF por RF.
  - **Corregido:** RF16 (F5-10, con un defecto adicional que apareció al corregirlo), RF12 (F5-11), pruebas
    unitarias de las reglas puras (`tests/unitarias/test_reglas.py`), reprogramar una reserva cancelada (RF21),
    límites del pronóstico (RF23) y documentación desactualizada (F3-1, F4-14 y el docstring de `alertas/servicio.py`).
  - **Para validar con el cliente o el equipo** (no se cambiaron porque son decisiones aprobadas o de la
    especificación):
    1. **RESTR04:** los videos van a disco local por defecto (P3). Para cumplir RESTR04 en la demo, el equipo debe
       crear el bucket y configurar `ALMACENAMIENTO=s3` (README). El adaptador está probado con `moto`.
    2. **RNF05 (HTTPS):** la especificación lo deja documentado (README) y no implementado en local, aunque
       `requisitos.md` lo pide. Alternativa: un servicio opcional de Caddy en Compose con certificado local.
    3. **RF17:** "servicios realizados" frente a D17 (la función SQL cuenta también los que siguen en curso). La
       respuesta trae la lista con el estado de cada uno. Alternativa: contar solo los terminados en
       `numero_servicios` y agregar `numero_en_curso`.
    4. **RNF08:** el registro de accesos a videos va al log de la aplicación, como dice la especificación. Si el
       cliente lo quiere consultable, haría falta una tabla nueva (migración 0002). Los aspectos legales de la
       Ley 1581 (autorización, aviso de privacidad) quedan fuera del backend.
    5. **RNF09 y la demo:** los controles de demo no se auditan (D13) y `MODO_DEMO=true` viene activado en
       `.env.example` para desarrollo; en un despliegue real debe ir en `false`.
    6. **RF27:** `observaciones` es opcional (el esquema lo permite); RF27 dice "indicando la causa revisada y las
       observaciones".

## Cambios para el diagrama de clases

El equipo debe pasar estos cambios a `docs/modelo/diagrama_clases.puml`:

1. `IApiDispositivo`:
   - Todos los métodos reciben `numeroSerie`: un solo simulador atiende todos los dispositivos, mientras que el diagrama modela una API por dispositivo.
   - `enviarOrdenInicio` recibe una `OrdenInicio` (id de la reserva, tipo de servicio, origen, destino y base con coordenadas, inicio y duración) en lugar de la entidad `Reserva`.
   - Se agrega `confirmarEntrega(numeroSerie, resultado : ResultadoEntrega)`, con `ResultadoEntrega` = `CONFIRMADA`, `NO_CONFIRMADA` o `AGOTADA`. La especificación (7.5) lo permite.
   - Se agrega `esperarEvento() : EventoDispositivo` para los eventos `CODIGO_INGRESADO` y `LLEGADA_BASE`.
   - `OrdenInicio` tiene `esperarCodigo : boolean` (lo activa RF24) y `reanudacion : Reanudacion [0..1]` (decisión F4-10).
2. `IAlmacenamientoCloud`: se agregan `tamano(url) : long` y `obtenerRango(url, inicio, fin) : byte[]`, para transmitir el video con `Range` sin cargar el objeto completo, y `revisar() : void` para `/health`.
3. `IServicioClima`: no cambia. `Pronostico` agrega `fechaHora`.
4. Organizar el diagrama en dos paquetes, **Núcleo (entrega 1)** y **Módulos (entrega 2)**. Los métodos de M-9
   pasan al paquete de su RF (en este repositorio, todavía pendientes).
5. `MonitorServicios` agrega `iniciarReservasPendientes()`, `procesarEvento(e)` y `reanudarServicios()`.
   `IAlmacenamientoCloud` tiene dos implementaciones: `AlmacenamientoS3` y `AlmacenamientoLocal`.
   `ReporteDispositivo` agrega la lista de servicios del periodo.
   `GestorVideos` agrega `registrarVideo(b, url, duracion)` y `reintentarSubidas()`: la subida va fuera de la
   transacción y la fila `video` dentro (especificación 7.5).
