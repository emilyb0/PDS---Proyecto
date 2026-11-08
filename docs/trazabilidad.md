# Trazabilidad: requisitos → endpoints → clases → pruebas

> Se actualiza con cada RF. Las pruebas están en `backend/tests/` y su nombre empieza por el id del requisito
> (`test_rf06_…`).
>
> - **Entrega:** 1 = núcleo (este repositorio) · 2 = módulo en `app/modulos/rfXX_nombre/`, con sus pruebas en
>   `tests/modulos/rfXX_nombre/` (CLAUDE.md, "Entregas").
> - **Estado:** ✅ implementado y probado · ⏳ pendiente.
> - **Especificación:** dónde empieza la regla en `docs/especificacion-backend.md`. Sus endpoints están en la tabla
>   de la sección 9 y sus eventos en la sección 10.

## Requisitos funcionales de la entrega 1 (implementados)

| RF | Nombre | Especificación | Endpoints | Clases / módulos | Pruebas | Estado |
|---|---|---|---|---|---|---|
| RF01 | Registrar dispositivo | 7.2, "Registrar (RF01)" | `POST /api/dispositivos` | `Dispositivo`, `Robot`, `Drone`, `Sensor`, `ServicioDispositivos.registrar_dispositivo` | `integracion/test_rf01_registrar_dispositivo.py` (15) | ✅ |
| RF04 | Consultar inventario | 7.2, "Inventario (RF04)" | `GET /api/dispositivos`, `GET /api/dispositivos/{id}` | `ServicioDispositivos.listar/detalle` | `integracion/test_rf04_consultar_inventario.py` (3) | ✅ |
| RF05 | Crear reserva | 7.4, "Crear (RF05)" | `POST /api/reservas`, `GET /api/reservas`, `GET /api/reservas/{id}`, `GET /api/ubicaciones` | `Reserva`, `GestorReservas.crear_reserva/obtener/listar`, `ReservaSalida` | `integracion/test_rf05_crear_reserva.py` (15), `integracion/test_rf05_catalogo_ubicaciones.py` (1) | ✅ |
| RF06 | Validar cruce de horarios | 7.4, "Crear", paso 3 | `POST /api/reservas` | `GestorReservas.validar_cruce_horario/buscar_cruce/guardar_con_exclusion`, `Reserva.se_cruza_con`, `ex_reserva_cruce` | `integracion/test_rf06_cruce_horario.py` (5, incluye las dos pruebas de concurrencia) | ✅ |
| RF07 | Validar batería y sensores | 7.4, "Crear", paso 4 | `POST /api/reservas` | `GestorReservas.validar_bateria_y_sensores`, `IApiDispositivo.obtener_telemetria`, `ApiDispositivoSimulada`, `Dispositivo.motivos_no_apto` | `integracion/test_rf07_bateria_sensores.py` (4) | ✅ |
| RF08 | Registrar bitácora del servicio | 7.5, "Inicio" y "Cierre" | `GET /api/bitacoras`, `GET /api/bitacoras/{id}`, `GET /api/bitacoras/{id}/ruta`, SSE `servicio`, `servicio_en_espera`, `servicio_no_iniciado`, `POST /api/demo/reservas/{id}/iniciar` | `MonitorServicios.iniciar_reservas_pendientes/iniciar_servicio/finalizar_servicio/reanudar_servicios`, `BitacoraServicio`, `RegistroTelemetria`, `Incidencia`, `servicios.consultas` | `integracion/test_rf08_bitacora.py` (8: inicio, en espera, no apto, ventana vencida, sin respuesta, listado y ruta, robot sin RF24, reanudación P1), `integracion/test_servicio_completo.py` | ✅ |
| RF09 | Monitorear dispositivos | 7.5, "Monitoreo" | `GET /api/monitoreo` | `MonitorServicios.actualizar_monitoreo/monitorear_dispositivo`, `IApiDispositivo.obtener_telemetria`, `servicios.consultas.foto_monitoreo` | `integracion/test_rf09_rf10_monitoreo.py` (2 de RF09), `test_servicio_completo.py` | ✅ |
| RF10 | Actualizar monitoreo | 7.5, "Monitoreo", y 10 | `GET /api/monitoreo/stream?token=` (SSE) | `BusEventos`, `servicios.router.flujo`, tarea `monitoreo` (APScheduler) | `integracion/test_rf09_rf10_monitoreo.py` (4 de RF10: telemetría por ciclo y ping, `Last-Event-ID`, token, cierre al desactivar), `test_rnf02_tiempo_real.py` | ✅ |
| RF11 | Generar alertas de servicio | 7.5, "Alertas de servicio" | `GET /api/alertas`, `GET /api/alertas/{id}`, SSE `alerta` | `MonitorServicios.evaluar_umbrales/_registrar_alertas`, `CondicionAlerta`, `AlertaServicio`, `alertas.servicio` | `integracion/test_rf11_alertas_servicio.py` (7: batería 19/20, sensor, retraso > 10 min, sin duplicados, reinicio, sin servicio), `integracion/test_rf11_consultar_alertas.py` (2), `unitarias/test_reglas.py` | ✅ |
| RF12 | Almacenar video del servicio | 7.5, "Cierre", y 7.6 | detalle de bitácora (`video`), `POST /api/demo/tareas/reintento-subidas/ejecutar` | `GestorVideos.almacenar_video/registrar_video/reintentar_subidas`, `IAlmacenamientoCloud`, `AlmacenamientoLocal`, `AlmacenamientoS3`, `IApiDispositivo.descargar_video` | `integracion/test_rf12_almacenar_video.py` (5: drone, pendiente y reintento de la subida, reintento de la descarga, solo MP4, adaptador local), `test_servicio_completo.py`, `test_restr04_almacenamiento_s3.py` | ✅ |
| RF18 | Registrar usuario | 7.1, "Registrar" | `POST /api/usuarios`, `GET /api/usuarios` | `Usuario`, `ServicioUsuarios.registrar_usuario` | `integracion/test_rf18_registrar_usuario.py` (4) | ✅ |
| RF20 | Iniciar sesión | 7.1, "Login", y 5 | `POST /api/auth/login`, `GET /api/auth/yo` | `ServicioUsuarios.iniciar_sesion`, `EmisorTokens`, `permisos.funciones_de` | `integracion/test_rf20_iniciar_sesion.py` (4), `unitarias/test_nucleo` | ✅ |

## Requisitos funcionales de la entrega 2 (pendientes)

La columna "Ya en el núcleo" dice qué existe para ese RF aunque el módulo falte. Cómo implementarlos:
`docs/como-continuar.md`.

| RF | Nombre | Especificación | Endpoints y eventos previstos (sección 9 y 10) | Ya en el núcleo | Estado |
|---|---|---|---|---|---|
| RF02 | Editar dispositivo | 7.2, "Editar (RF02)" | `PATCH /api/dispositivos/{id}` | `Dispositivo.editar`, `ServicioDispositivos.detalle`, `advertencia_reservas_programadas` | ⏳ |
| RF03 | Dar de baja dispositivo | 7.2, "Dar de baja (RF03)" | `POST /api/dispositivos/{id}/baja` | `Dispositivo.dar_de_baja`, trigger `fn_validar_baja`, `reservas_del_dispositivo` | ⏳ |
| RF13 | Consultar videos | 7.6, "Buscar" y "Reproducir" | `GET /api/videos`, `GET /api/videos/{id}/reproducir`, `GET /api/videos/{id}/contenido` | `Video`, `IAlmacenamientoCloud.tamano/obtener_rango` (para `Range`) | ⏳ |
| RF14 | Ordenar retorno o parada | 7.5, "Órdenes" | `POST /api/bitacoras/{id}/ordenes`, SSE `orden` | `IApiDispositivo.enviar_orden` (el simulador detiene o hace volver), `TipoOrden`, `BitacoraServicio.registrar_incidencia` | ⏳ |
| RF15 | Registrar mantenimiento | 7.3, "Registrar" y "Cerrar" | `GET/POST /api/dispositivos/{id}/mantenimientos`, `POST /api/mantenimientos/{id}/cerrar` | `Mantenimiento`, `app/mantenimiento/consultas.py` | ⏳ |
| RF16 | Alertar mantenimiento preventivo | 7.3, "Alerta preventiva", y 12 | `GET /api/alertas` (núcleo), SSE `alerta` | `Dispositivo.requiere_mantenimiento`, `AlertaMantenimiento`, extensión `al_finalizar_servicio` | ⏳ |
| RF17 | Generar reportes | 7.7, "Reporte" | `GET /api/dispositivos/{id}/reporte` | función SQL `reporte_dispositivo()` | ⏳ |
| RF19 | Desactivar usuario | 7.1, "Desactivar" | `POST /api/usuarios/{id}/desactivar` | `obtener_usuario`, `exigir_otro_administrador_activo`; el núcleo ya revisa en cada petición y en el SSE que el usuario siga activo | ⏳ |
| RF21 | Cancelar o reprogramar reserva | 7.4, "Cancelar" y "Reprogramar" | `POST /api/reservas/{id}/cancelar`, `…/reprogramar` | `Reserva.cancelar/reprogramar`, validaciones de `GestorReservas` | ⏳ |
| RF22 | Sugerir dispositivo | 7.4, "Sugerencia" | `GET /api/reservas/sugerencia` | validaciones de RF06 y RF07 en `GestorReservas`; la ruta con id usa `{id_reserva:int}` para no chocar | ⏳ |
| RF23 | Validar clima para drones | 7.4, "Crear", paso 5 | validador de `POST /api/reservas`, `PUT /api/demo/clima` | extensiones `validadores_reserva` y `evaluador_clima`; variables `VIENTO_MAX_KMH`, `LLUVIA_MAX_PCT`, `CLIMA_PROVEEDOR` | ⏳ |
| RF24 | Confirmar entrega con código | 7.5, "Entrega con código" | SSE `entrega`, `POST /api/demo/dispositivos/{id}/codigo-entrega` | el código de 4 dígitos (`Reserva.generar_codigo_entrega`), `BitacoraServicio.confirmar_entrega`, `IApiDispositivo.leer_codigo_entrega/confirmar_entrega`, `OrdenInicio.esperar_codigo` en el simulador | ⏳ |
| RF25 | Alertar salida de zona de operación | 7.5, "Alertas de servicio" | `GET /api/zona-operacion`, SSE `alerta` y `fuera_de_zona` en `telemetria`, eventos de demo `SALIR_DE_ZONA` y `VOLVER_A_ZONA` | `ZonaOperacion.contiene`, `punto_en_poligono`, `desviar` en el simulador, `fuera_de_zona` en la telemetría (hoy `null`) | ⏳ |
| RF26 | Eliminar videos vencidos | 7.6, "Retención", y 12 | tarea diaria (02:00), `POST /api/demo/tareas/retencion-videos/ejecutar` | `Video.esta_vencido`, `sumar_meses`, `IAlmacenamientoCloud.eliminar` | ⏳ |
| RF27 | Atender alerta de servicio | 7.5, "Atención" | `POST /api/alertas/{id}/atencion`, SSE `alerta_atendida` | `AlertaServicio.registrar_atencion`, `AtencionAlerta`; el filtro `atendida` de `GET /api/alertas` | ⏳ |

## Requisitos no funcionales y restricciones

| ID | Cómo se cumple | Pruebas | Estado |
|---|---|---|---|
| RNF01 | `solo_administrador` (403 al operador); funciones de menú por rol (y por módulo cuando existan) | `test_rnf01_permisos.py`, `test_demo_controles.py` | ✅ (cada módulo agrega su prueba) |
| RNF02 | Monitor en paralelo (`asyncio.gather`) cada `INTERVALO_MONITOREO_SEG` (≤ 5 s) + SSE | `test_rnf02_tiempo_real.py` (lenta: 6 dispositivos en servicio, servidor real con APScheduler) | ✅ |
| RNF03 | Listados paginados con índices | `test_semilla::test_rnf03_…` (inventario, reservas, bitácoras, alertas y monitoreo en < 3 s con los datos semilla) | ✅ |
| RNF04 | Retención de 3 meses | — | ⏳ con RF26 |
| RNF05 | Argon2id; HTTPS documentado en el README | `test_rnf05_contrasenas.py`, `unitarias/test_nucleo::test_rnf05_…` | ✅ (HTTPS solo documentado) |
| RNF06 | `/health` con base de datos, almacenamiento y simulador (y los chequeos de los módulos cuando existan); `restart: unless-stopped` | `test_salud.py` (3) | ✅ |
| RNF07 | La sugerencia trae todo lo del formulario: crear una reserva toma dos pasos | — | ⏳ con RF22 |
| RNF08 | Bucket privado (README) y logs que ocultan el token; los enlaces firmados y el registro de cada acceso a un video llegan con RF13 | `unitarias/test_nucleo::test_logs_ocultan_token_y_firma` | ⏳ parcial: se completa con RF13 |
| RNF09 | `registrar_auditoria` en la misma transacción, `GET /api/auditoria` | `test_rnf09_auditoria.py`, `test_rf05_crear_reserva` (reserva CREAR) | ✅ (cada módulo agrega su prueba) |
| RNF10 | Sin límite fijo de dispositivos; el simulador carga solo cualquier dispositivo nuevo | `test_rnf10_veinte_dispositivos.py` (registro y monitoreo de 20 en un ciclo) | ✅ |
| RESTR01 | Simulador (`ApiDispositivoSimulada` con `escenario.json` y `muestra.mp4`) y datos semilla | `unitarias/test_restr01_simulador.py` (9), `test_rf07_bateria_sensores`, `test_semilla::test_restr01_…` (semilla de la entrega 1, idempotente) | ✅ |
| RESTR02 | API REST + SSE + CORS | `test_salud::test_cors_…`, `test_salud::test_openapi_…`, `test_rf09_rf10_monitoreo.py` | ✅ |
| RESTR03 | EventSource y MP4 H.264 (la transmisión con `Range` llega con RF13) | `test_rf09_rf10_monitoreo.py` (EventSource), `test_restr01_simulador::test_restr01_escenario_precargado` (MP4 H.264) | ✅ (`Range` con RF13) |
| RESTR04 | `AlmacenamientoS3` (boto3, bucket privado) con `ALMACENAMIENTO=s3`; local para desarrollo | `test_restr04_almacenamiento_s3.py` (3, con `moto`: operaciones, cierre de servicio que sube al bucket, configuración) | ✅ (el bucket real lo crea el equipo, ver README) |

## Base técnica

| Tema | Pruebas |
|---|---|
| Migración 0001 literal, tablas, triggers, función y EXCLUDE | `test_migracion.py` |
| Sesión de PostgreSQL en America/Bogota; URL de la base desde `PUERTO_BD` | `test_migracion::test_sesion_…`, `unitarias/test_configuracion.py` |
| Mapeo de los 18 modelos (herencias, columna calculada `horario`) | `test_modelos.py` |
| Traducción de SQLSTATE (23505, 23514, P0001, 23503, 23P01) y formato de error | `test_errores.py` |
| Reloj, meses de calendario, tokens, logs sin secretos | `unitarias/test_nucleo.py` |
| Punto en polígono (el borde cuenta como dentro), distancias | `unitarias/test_geometria.py` |
| Reglas puras del dominio: tipo requerido, umbrales de RF07, cruce de horarios, cálculo de alertas de RF11, y los métodos que usarán RF16 y RF26 (`requiere_mantenimiento`, `esta_vencido`) | `unitarias/test_reglas.py` |
| **Servicio completo con el núcleo:** reserva → inicio automático → monitoreo → alertas → cierre con video | `integracion/test_servicio_completo.py` |
| Controles de demo del núcleo (iniciar, eventos del dispositivo, tareas) | `integracion/test_demo_controles.py` |
| Recorrido completo contra la API en ejecución (12 RF) | `backend/scripts/demo_e2e.py` |
| **Regla de entregas:** el núcleo no importa módulos, un módulo no importa otro, las pruebas de un módulo solo importan su módulo, cada módulo tiene sus pruebas, `MODULOS_ACTIVOS` | `unitarias/test_modulos.py`, `pytest --solo-entrega-1` |
