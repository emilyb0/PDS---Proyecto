# Guía de la API para el frontend

> Para quien construya la aplicación web. Describe cómo autenticarse, qué devuelve cada endpoint, cómo
> se reportan los errores y cómo recibir el monitoreo en tiempo real.
> La documentación interactiva siempre actualizada está en **`http://localhost:8010/docs`** (OpenAPI).
> Si esta guía y `/docs` no coinciden, avísale al equipo de backend: hay que corregir uno de los dos.
>
> **Esta guía describe la entrega 1 (12 RF).** Lo que agregarán los RF pendientes está en la sección 11.
> Para probar sin frontend: `backend/tests/http/api.http` (REST Client de VS Code) y el guion `docs/demo.md`.

## 0. Entregas: qué existe

- **Entrega 1 (núcleo, esta versión):** RF01, RF04, RF05, RF06, RF07, RF08, RF09, RF10, RF11, RF12, RF18 y RF20.
- **Entrega 2 (pendiente):** RF02, RF03, RF13, RF14, RF15, RF16, RF17, RF19, RF21, RF22, RF23, RF24, RF25, RF26 y
  RF27. Se agregarán como módulos que el backend puede encender o apagar (`MODULOS_ACTIVOS`). Mientras un módulo
  no exista o esté apagado, sus rutas responden **404** (o **405** si comparten la dirección de una ruta del
  núcleo, como `PATCH /api/dispositivos/{id}`) y sus eventos SSE no llegan.

**Cómo saber qué hay:** `POST /api/auth/login` y `GET /api/auth/yo` devuelven:

- `requisitos_activos`: hoy, los 12 de la entrega 1 (`["RF01", "RF04", …, "RF20"]`);
- `funciones`: el menú del rol, que incluirá las funciones de los módulos activos cuando existan.

Muestre un botón o una pantalla solo si su RF está en `requisitos_activos` (y su función en `funciones`). Así el
frontend sirve igual hoy y cuando lleguen los módulos.

## 1. Lo básico

| Tema | Regla |
|---|---|
| URL base | `http://localhost:8010` (con Docker Compose; el puerto sale de `PUERTO_API` en el `.env`). Todas las rutas empiezan por `/api`, salvo `/health` y `/docs` |
| CORS | Permitido por defecto para `http://localhost:5173` (Vite). Otros orígenes se agregan en `CORS_ORIGENES` del `.env` |
| Proxy de desarrollo | Si configura un proxy en Vite, apúntelo a `http://127.0.0.1:8010` y no a `localhost`: el backend se publica solo en IPv4 y Node puede intentar primero `::1` |
| Formato | JSON en UTF-8 con nombres de campos en español y `snake_case` |
| Fecha | `"2026-11-09"` |
| Hora | `"10:30"` (HH:MM, 24 h) |
| Fecha y hora | ISO 8601 en hora de Colombia, con desfase: `"2026-11-09T10:30:00-05:00"`. Al enviar, si no se pone desfase, se asume Colombia |
| Números | Los decimales (batería, horas, coordenadas) son números JSON, no texto |
| IDs | Enteros |
| Autenticación | `Authorization: Bearer <token>` en todas las rutas salvo `login` y `/health` |

### Listados paginados

Todo listado que puede crecer se pagina con `limite` (por defecto 50, máximo 200) y `desplazamiento` (por defecto 0):

```json
{ "items": [ … ], "total": 128, "limite": 50, "desplazamiento": 0 }
```

El catálogo de ubicaciones (`/api/ubicaciones`) es pequeño y devuelve el arreglo sin paginar.

### Advertencias

Algunas respuestas traen `"advertencias"`: acciones que se completan pero conviene avisarle algo al usuario. Es una
lista, vacía si no hay nada que avisar:

```json
"advertencias": [
  { "codigo": "RESERVAS_PROGRAMADAS", "mensaje": "El dispositivo tiene 2 reservas programadas.", "detalles": { "reservas": [14, 15] } }
]
```

En la entrega 1 la lista llega vacía (en la reserva y en el detalle del dispositivo). Muestre cada `mensaje` si
llega alguno: los RF pendientes agregarán `RESERVAS_PROGRAMADAS` (RF02, RF15), `RESERVAS_DEL_OPERADOR` (RF19),
`MANTENIMIENTO_CERRADO` (RF03) y `CLIMA_NO_VERIFICADO` (RF23).

## 2. Errores

Todos los errores, incluidos los de validación, tienen esta forma:

```json
{
  "error": {
    "codigo": "CRUCE_HORARIO",
    "mensaje": "El dispositivo R-002 ya tiene la reserva #14 de 10:00 a 10:30.",
    "detalles": { "reserva_en_conflicto": { "id_reserva": 14 } }
  }
}
```

`mensaje` siempre está en español y se puede mostrar tal cual al usuario. `detalles` puede ser `null`.

| HTTP | `codigo` | Qué hacer en el frontend |
|---|---|---|
| 401 | `NO_AUTENTICADO` | Token ausente, inválido o vencido, o usuario desactivado. Borrar el token e ir al login |
| 403 | `SIN_PERMISO` | El rol no puede hacer esto. No debería pasar si se respeta `funciones` (sección 3) |
| 404 | `NO_ENCONTRADO` | El recurso no existe, o se envió un id que no existe (también una ruta de un RF pendiente) |
| 422 | `VALIDACION` | Campos inválidos. `detalles.campos` = `[{ "campo": "duracion_estimada_min", "mensaje": "…" }]`; mostrar cada mensaje junto a su campo |
| 409 | `DUPLICADO` | Correo o número de serie ya registrado |
| 409 | `CRUCE_HORARIO` | `detalles.reserva_en_conflicto` = `{ id_reserva, fecha, hora_inicio, hora_fin, tipo_servicio, estado, operador: { id_usuario, nombre } }` (RF06) |
| 409 | `DISPOSITIVO_NO_APTO` | `detalles.motivos` = `["Batería 25 % (mínimo 30 %)", "Sensor LIDAR en falla"]` (RF07) |
| 409 | `TIPO_DISPOSITIVO_INCORRECTO` | Se eligió un robot para una grabación o un drone para una entrega |
| 409 | `REGLA_NEGOCIO` | Otra regla de negocio; el `mensaje` dice cuál |
| 405 | `METODO_NO_PERMITIDO` | Se usó un método HTTP que la ruta no admite: error de programación del cliente, o una ruta de un RF pendiente que comparte la dirección con una del núcleo (`PATCH /api/dispositivos/{id}`) |
| 500 | `ERROR_INTERNO` | Mensaje genérico; reintentar o avisar |
| 503 | `SERVICIO_NO_DISPONIBLE` | Una dependencia no responde: base de datos, almacenamiento, o el dispositivo al consultar su batería (RF07) |

Los RF pendientes agregarán `CLIMA_NO_APTO` (RF23) y `RESERVAS_PENDIENTES` (RF03), con la misma forma.

## 3. Sesión y roles (RF20, RNF01)

### Flujo

1. `POST /api/auth/login` con correo y contraseña. Guarde el `token` (por ejemplo en `sessionStorage`).
2. Envíe `Authorization: Bearer <token>` en cada petición.
3. Arme el menú con `funciones`: muestre solo lo que esté en esa lista.
4. Al recargar la página, llame a `GET /api/auth/yo` para recuperar el usuario, sus funciones y los
   requisitos activos.
5. Ante cualquier 401, cierre la sesión. El token vence a las 8 h.

```http
POST /api/auth/login
{ "correo": "admin@campus.edu.co", "contrasena": "Admin123*" }
```

```json
200
{
  "token": "eyJhbGciOi…",
  "tipo": "bearer",
  "expira": "2026-11-09T18:30:00-05:00",
  "usuario": { "id_usuario": 1, "nombre": "Ana Admin", "correo_institucional": "admin@campus.edu.co",
               "rol": "ADMINISTRADOR", "estado": "ACTIVO", "fecha_creacion": "2026-11-01T08:00:00-05:00" },
  "funciones": ["inventario.ver", "reservas.ver", "…", "demo.usar"],
  "requisitos_activos": ["RF01", "RF04", "RF05", "RF06", "RF07", "RF08", "RF09", "RF10", "RF11", "RF12", "RF18", "RF20"]
}
```

Errores: 401 "Correo o contraseña incorrectos" (el mismo mensaje si el correo no existe) y 403 "Usuario inactivo".

### Funciones por rol

| Función | Pantalla o acción | Admin | Operador |
|---|---|:---:|:---:|
| `inventario.ver` | Inventario y detalle de dispositivo | ✔ | ✔ |
| `inventario.gestionar` | Registrar dispositivos | ✔ | |
| `reservas.ver` | Lista y detalle de reservas | ✔ | ✔ |
| `reservas.gestionar` | Crear reservas | ✔ | |
| `bitacoras.ver` | Bitácoras y rutas | ✔ | ✔ |
| `monitoreo.ver` | Panel de monitoreo en tiempo real | ✔ | ✔ |
| `alertas.ver` | Alertas | ✔ | ✔ |
| `usuarios.gestionar` | Registrar y editar usuarios | ✔ | |
| `auditoria.ver` | Historial de auditoría | ✔ | |
| `demo.usar` | Panel de controles de demo (solo si el backend corre con `MODO_DEMO=true`) | ✔ | |

Los módulos de la entrega 2 agregarán sus propias funciones a esta lista.

## 4. Valores fijos (enumeraciones)

Los valores van en mayúsculas en la API. La columna "Texto sugerido" es para mostrar en pantalla. La base de datos
ya tiene todos los valores; los marcados con † solo aparecerán cuando existan los RF pendientes.

| Campo | Valores → texto sugerido |
|---|---|
| `rol` | `ADMINISTRADOR` Administrador · `OPERADOR` Operador |
| `estado` (usuario) | `ACTIVO` Activo · `INACTIVO` Inactivo |
| `tipo` (dispositivo) | `ROBOT` Robot · `DRONE` Drone |
| `estado` (dispositivo) | `DISPONIBLE` Disponible · `EN_SERVICIO` En servicio · `EN_CARGA` En carga · `EN_MANTENIMIENTO` En mantenimiento † · `FUERA_DE_SERVICIO` Fuera de servicio |
| `estado` (sensor) | `OK` · `FALLA` En falla |
| `tipo_servicio` | `ENTREGA_DOCUMENTOS` Entrega de documentos (robot) · `PEDIDO_CAFETERIA` Pedido de cafetería (robot) · `GRABACION_EVENTO` Grabación de evento (drone) |
| `estado` (reserva) | `PROGRAMADA` Programada · `EN_CURSO` En curso · `FINALIZADA` Finalizada · `CANCELADA` Cancelada |
| `estado` (bitácora) | `EN_CURSO` En curso · `ENTREGADO` Entregado † · `RETORNANDO` Retornando · `FINALIZADO` Finalizado |
| `estado_servicio` (fase que reporta el dispositivo) | `EN_BASE` En base · `EN_RUTA` En ruta · `EN_DESTINO` En destino (drone grabando) · `ESPERANDO_CODIGO` Esperando código † · `RETORNANDO` Retornando · `DETENIDO` Detenido † |
| `tipo` (incidencia) | `BATERIA_BAJA` · `SENSOR_EN_FALLA` · `RETRASO` · `SALIDA_DE_ZONA` † · `ORDEN_RETORNO` † · `PARADA_EMERGENCIA` † · `ENTREGA_NO_CONFIRMADA` † |
| `tipo` (alerta) | `SERVICIO` · `MANTENIMIENTO` † |
| `causa` (alerta de servicio) | `BATERIA_BAJA` Batería baja · `SENSOR_EN_FALLA` Sensor en falla · `RETRASO` Retraso · `SALIDA_DE_ZONA` Fuera de zona † |
| `accion` (auditoría) | `CREAR` · `EDITAR` · `BAJA` |

Tipo de dispositivo según el servicio: las entregas (documentos o cafetería) solo van con **robot**; la grabación de eventos solo con **drone**.

## 5. Pantallas sugeridas y endpoints que usan

| Pantalla | Endpoints |
|---|---|
| Login | `POST /api/auth/login`, `GET /api/auth/yo` |
| Inventario | `GET /api/dispositivos?tipo=&estado=` · registrar `POST /api/dispositivos` |
| Detalle de dispositivo | `GET /api/dispositivos/{id}` |
| Nueva reserva | `GET /api/ubicaciones`, `GET /api/dispositivos?tipo=…` (para elegir el dispositivo), `GET /api/usuarios?rol=OPERADOR&estado=ACTIVO` (para elegir el operador) → `POST /api/reservas` |
| Reservas | `GET /api/reservas?fecha=&estado=&id_dispositivo=` · `GET /api/reservas/{id}` |
| Monitoreo | `GET /api/monitoreo` (foto inicial) + `GET /api/monitoreo/stream` (SSE) |
| Bitácoras | `GET /api/bitacoras?desde=&hasta=&id_dispositivo=&estado=` · `GET /api/bitacoras/{id}` · `GET /api/bitacoras/{id}/ruta` |
| Alertas | `GET /api/alertas?tipo=&atendida=&id_dispositivo=&desde=&hasta=` · `GET /api/alertas/{id}` |
| Usuarios | `GET /api/usuarios?rol=&estado=` · `POST /api/usuarios` · `PATCH /api/usuarios/{id}` |
| Auditoría | `GET /api/auditoria?id_usuario=&entidad=&accion=&desde=&hasta=` |
| Panel de demo | `/api/demo/...` (sección 8) |

## 6. Endpoints

### 6.1 Usuarios (RF18, RNF01) · solo administrador

**Usuario**

```json
{ "id_usuario": 2, "nombre": "Óscar Operador", "correo_institucional": "operador1@campus.edu.co",
  "rol": "OPERADOR", "estado": "ACTIVO", "fecha_creacion": "2026-11-01T08:00:00-05:00" }
```

| Método y ruta | Cuerpo / parámetros | Respuesta |
|---|---|---|
| `POST /api/usuarios` | `{ nombre, correo_institucional, contrasena, rol }`. La contraseña tiene mínimo 8 caracteres. Si el backend define un dominio institucional, el correo debe ser de ese dominio | 201 Usuario · 409 `DUPLICADO` |
| `GET /api/usuarios` | `?rol=OPERADOR&estado=ACTIVO` | Paginado de Usuario |
| `PATCH /api/usuarios/{id}` | `{ nombre?, rol? }` | Usuario · 409 si se quitaría el último administrador activo |

La contraseña nunca se devuelve.

### 6.2 Dispositivos (RF01, RF04)

**Dispositivo (en el listado)**

```json
{ "id_dispositivo": 1, "tipo": "ROBOT", "numero_serie": "R-001", "modelo": "Rover Mk2",
  "estado": "DISPONIBLE", "nivel_bateria": 87, "horas_uso_desde_mant": 12.5,
  "capacidad_carga_kg": 5.0, "autonomia_vuelo_min": null,
  "fecha_registro": "2026-08-01", "dado_de_baja": false, "fecha_baja": null, "motivo_baja": null,
  "sensores_en_falla": [] }
```

**Detalle** (`GET /api/dispositivos/{id}`): lo anterior, más:

```json
{ "sensores": [ { "id_sensor": 1, "nombre": "GPS", "estado": "OK" } ],
  "servicio_activo": { "id_bitacora": 40, "id_reserva": 55, "estado": "EN_CURSO" },
  "ultima_telemetria": { "fecha_hora": "…", "latitud": 4.6381, "longitud": -74.0842, "nivel_bateria": 87, "estado_servicio": "EN_RUTA" },
  "advertencias": [] }
```

`sensores_en_falla` es la lista de nombres de los sensores en falla (vacía si todos están bien). El número de
serie se guarda en mayúsculas.

| Método y ruta | Cuerpo / parámetros | Respuesta |
|---|---|---|
| `GET /api/dispositivos` | `?tipo=ROBOT&estado=DISPONIBLE`. Incluye los dados de baja (salen con `FUERA_DE_SERVICIO` y `dado_de_baja: true`) | Paginado |
| `POST /api/dispositivos` (admin) | `{ tipo, numero_serie, modelo, capacidad_carga_kg (robot) \| autonomia_vuelo_min (drone), estado?, sensores?: ["GPS", …] }`. `estado` es `DISPONIBLE` (por defecto), `EN_CARGA` o `FUERA_DE_SERVICIO`. Si no se envían sensores, se crean los del tipo | 201 Detalle · 409 `DUPLICADO` |
| `GET /api/dispositivos/{id}` | — | Detalle |

### 6.3 Ubicaciones y reservas (RF05–RF07)

| Método y ruta | Respuesta |
|---|---|
| `GET /api/ubicaciones` | `[ { "id_ubicacion": 1, "nombre": "Base de operaciones", "latitud": 4.638, "longitud": -74.084, "es_base": true } ]` |

**Crear una reserva**

En la entrega 1 el formulario arma la lista de dispositivos con `GET /api/dispositivos?tipo=ROBOT` (o `DRONE`) y
la de operadores con `GET /api/usuarios?rol=OPERADOR&estado=ACTIVO`. Al confirmar, el backend valida el cruce, la
batería y los sensores. (La sugerencia automática del mejor dispositivo es del RF22, pendiente.)

```http
POST /api/reservas
{ "tipo_servicio": "PEDIDO_CAFETERIA", "fecha": "2026-11-09", "hora_inicio": "10:00",
  "duracion_estimada_min": 30, "id_origen": 2, "id_destino": 3, "id_dispositivo": 2, "id_operador": 2 }
```

- Responde 201 con la Reserva + `advertencias`.
- Si el dispositivo es un robot, `codigo_entrega` trae un **código de 4 dígitos**. Siempre se genera (la base lo
  exige); lo usará el RF24 (pendiente) para confirmar la entrega.
- Errores posibles, en este orden: `TIPO_DISPOSITIVO_INCORRECTO`, `DISPOSITIVO_NO_APTO` (estado),
  `CRUCE_HORARIO`, `DISPOSITIVO_NO_APTO` (batería o sensores).
- Validaciones (422, con el campo en `detalles.campos`): la fecha y hora no pueden estar en el pasado (se acepta
  el minuto en curso); la duración va de 1 a 480 min; el origen y el destino existen y son distintos; el
  responsable es un operador activo. Un dispositivo inexistente responde 404.
- La batería y los sensores se consultan al dispositivo en ese momento; si no responde, 503.

**Reserva**

```json
{ "id_reserva": 55, "tipo_servicio": "PEDIDO_CAFETERIA", "estado": "PROGRAMADA",
  "fecha": "2026-11-09", "hora_inicio": "10:00", "hora_fin": "10:30", "duracion_estimada_min": 30,
  "inicio": "2026-11-09T10:00:00-05:00", "fin": "2026-11-09T10:30:00-05:00",
  "origen": { "id_ubicacion": 2, "nombre": "Cafetería" }, "destino": { "id_ubicacion": 3, "nombre": "Rectoría" },
  "dispositivo": { "id_dispositivo": 2, "numero_serie": "R-002", "tipo": "ROBOT", "modelo": "Rover Mk2" },
  "operador": { "id_usuario": 2, "nombre": "Óscar Operador" },
  "administrador": { "id_usuario": 1, "nombre": "Ana Admin" },
  "codigo_entrega": "4821", "motivo_cambio": null, "fecha_creacion": "…", "id_bitacora": null }
```

`codigo_entrega` solo lo recibe el administrador; al operador le llega `null`. `id_bitacora` se llena cuando el servicio inicia.

| Método y ruta | Cuerpo / parámetros | Respuesta |
|---|---|---|
| `POST /api/reservas` (admin) | ver arriba | 201 Reserva + `advertencias` |
| `GET /api/reservas` | `?fecha=2026-11-09&estado=PROGRAMADA&id_dispositivo=2`, ordenadas por inicio | Paginado |
| `GET /api/reservas/{id}` | — | Reserva |

### 6.4 Bitácoras (RF08)

**Bitácora (en el listado)**

```json
{ "id_bitacora": 40, "id_reserva": 55, "estado": "EN_CURSO", "tipo_servicio": "PEDIDO_CAFETERIA",
  "hora_salida": "2026-11-09T10:00:05-05:00", "hora_regreso": null, "hora_entrega": null, "entregado": false,
  "dispositivo": { "id_dispositivo": 2, "numero_serie": "R-002", "tipo": "ROBOT", "modelo": "Rover Mk2" },
  "operador": { "id_usuario": 2, "nombre": "Óscar Operador" }, "numero_incidencias": 1, "tiene_video": false }
```

**Detalle** (`GET /api/bitacoras/{id}`): lo anterior, más:

```json
{ "reserva": { "…": "la Reserva" },
  "horas_uso": null,
  "incidencias": [ { "id_incidencia": 9, "fecha_hora": "…", "tipo": "BATERIA_BAJA", "descripcion": "Batería 19 %",
                     "latitud": 4.63, "longitud": -74.08, "id_alerta": 12 } ],
  "video": { "id_video": 7, "fecha_grabacion": "…", "duracion_seg": 1520, "eliminado": false, "fecha_eliminacion": null } }
```

| Método y ruta | Cuerpo / parámetros | Respuesta |
|---|---|---|
| `GET /api/bitacoras` | `?desde=2026-11-01&hasta=2026-11-09&id_dispositivo=2&estado=FINALIZADO`, de la más reciente a la más antigua | Paginado |
| `GET /api/bitacoras/{id}` | — | Detalle |
| `GET /api/bitacoras/{id}/ruta` | — | `{ "id_bitacora": 40, "puntos": [ { "fecha_hora", "latitud", "longitud", "nivel_bateria", "estado_servicio", "sensores": [ { "id_sensor", "nombre", "estado" } ] } ] }` |

- La bitácora se crea sola cuando la reserva inicia (a su hora, o con el control de demo) y se cierra cuando
  el dispositivo vuelve a la base. Estados en la entrega 1: `EN_CURSO` → `RETORNANDO` → `FINALIZADO`. El robot deja
  el pedido y vuelve, y `hora_entrega` queda en `null` (la confirmación con código es del RF24, pendiente).
- `horas_uso` es `null` mientras el servicio no termine.
- `video` es `null` mientras no se haya guardado. Si la subida falló, se reintenta cada 5 min y aparece después.
- `estado_servicio` en la ruta es la fase que reportó el dispositivo: en la entrega 1, `EN_BASE`, `EN_RUTA`,
  `EN_DESTINO` o `RETORNANDO`.

### 6.5 Monitoreo (RF09) · ambos roles

`GET /api/monitoreo` es la foto inicial del panel. Después se actualiza con el SSE (sección 7).

```json
{
  "generado": "2026-11-09T10:05:00-05:00",
  "intervalo_seg": 5,
  "dispositivos": [
    { "id_dispositivo": 2, "numero_serie": "R-002", "tipo": "ROBOT", "modelo": "Rover Mk2", "estado": "EN_SERVICIO",
      "telemetria": { "…": "igual que el evento telemetria" },
      "servicio": { "id_bitacora": 40, "id_reserva": 55, "tipo_servicio": "PEDIDO_CAFETERIA", "estado": "EN_CURSO",
                    "hora_salida": "…", "fin_estimado": "2026-11-09T10:30:00-05:00",
                    "destino": { "id_ubicacion": 3, "nombre": "Rectoría" }, "operador": { "id_usuario": 2, "nombre": "…" } } }
  ],
  "alertas_abiertas": [ { "…": "Alerta (sección 6.6)" } ]
}
```

Se monitorean todos los dispositivos que no están dados de baja, tengan servicio o no, ordenados por número de
serie. `servicio` es `null` si el dispositivo no está en servicio, y `telemetria` es `null` si todavía no hay
ninguna lectura desde que arrancó el backend (llega en el primer ciclo, en menos de 5 s). `alertas_abiertas` son
las alertas de servicio sin atender; en la entrega 1, todas, porque atenderlas es del RF27 (pendiente).

### 6.6 Alertas (RF11)

El núcleo genera las alertas de servicio `BATERIA_BAJA`, `SENSOR_EN_FALLA` y `RETRASO`.

**Alerta**

```json
{ "id_alerta": 12, "tipo": "SERVICIO", "causa": "BATERIA_BAJA", "descripcion": "R-002: batería 19 % (mínimo 20 %)",
  "fecha_hora": "…", "id_dispositivo": 2, "numero_serie": "R-002",
  "id_bitacora": 40, "id_incidencia": 9, "id_operador": 2, "latitud": 4.63, "longitud": -74.08,
  "atendida": false, "atencion": null,
  "dias_desde_ultimo": null, "horas_desde_ultimo": null }
```

- `id_operador` es el operador responsable del servicio. Úselo para resaltarle la alerta.
- Descripciones: `"R-002: batería 19 % (mínimo 20 %)"`, `"R-002: sensor LIDAR en falla"` (o
  `"sensores GPS, LIDAR en falla"`) y `"R-002: 11 min de retraso sobre el fin estimado (10:30)"`. Todas traen la
  ubicación del dispositivo en `latitud` y `longitud`.
- Una causa no se repite en el mismo servicio mientras siga activa; si se normaliza y vuelve a ocurrir, llega otra
  alerta. `RETRASO` llega una sola vez por servicio.
- En la entrega 1, `atendida` es `false` y `atencion` es `null`. `dias_desde_ultimo` y `horas_desde_ultimo` son de
  las alertas de mantenimiento (RF16, pendiente).

| Método y ruta | Cuerpo / parámetros | Respuesta |
|---|---|---|
| `GET /api/alertas` | `?tipo=SERVICIO&atendida=false&id_dispositivo=2&desde=&hasta=`. `atendida` solo filtra alertas de servicio | Paginado, de la más reciente a la más antigua |
| `GET /api/alertas/{id}` | — | Alerta |

### 6.7 Videos (RF12)

El video de cada servicio se guarda al cerrarlo y aparece como dato en `GET /api/bitacoras/{id}` (`video`). En la
entrega 1 no hay ruta para buscarlo ni reproducirlo: eso es del RF13 (pendiente, sección 11).

### 6.8 Auditoría (RNF09) · solo administrador

| Método y ruta | Parámetros | Respuesta |
|---|---|---|
| `GET /api/auditoria` | `?id_usuario=&entidad=reserva&accion=CREAR&desde=&hasta=` | Paginado de `{ id_auditoria, fecha_hora, accion, entidad, id_entidad, usuario: { id_usuario, nombre } }` |

### 6.9 Salud

`GET /health` (público) devuelve 200, o 503 si falla una dependencia.

```json
{ "estado": "ok", "base_datos": "ok", "almacenamiento": "ok", "simulador": "ok", "version": "0.1.0" }
```

`simulador` es `ok`, `sin_base` si falta la ubicación base o `detenido` si dejó de atender los eventos de los
dispositivos. `estado` es `degradado` si algún componente no está `ok`. La respuesta es 503 solo si falla la base de
datos o el almacenamiento. Los módulos podrán agregar líneas (por ejemplo `zona_operacion`, de RF25).

## 7. Tiempo real: SSE (RF10, RNF02)

`EventSource` no puede enviar cabeceras, así que el token va en la URL. El servidor no lo escribe en sus registros.

```js
const fuente = new EventSource(`${API_BASE}/api/monitoreo/stream?token=${encodeURIComponent(token)}`);

fuente.addEventListener("telemetria", (e) => actualizarDispositivo(JSON.parse(e.data)));
fuente.addEventListener("alerta", (e) => mostrarAlerta(JSON.parse(e.data)));
fuente.addEventListener("servicio", (e) => recargarServicio(JSON.parse(e.data)));
fuente.addEventListener("servicio_en_espera", (e) => aviso(JSON.parse(e.data)));
fuente.addEventListener("servicio_no_iniciado", (e) => aviso(JSON.parse(e.data)));
fuente.onerror = () => { /* EventSource se reconecta solo; si el token venció, vuelva al login */ };
```

- Sin `token`, con un token inválido o de un usuario inactivo, la respuesta es 401 antes de abrir el flujo
  (`EventSource` llama a `onerror`).
- Cada dispositivo envía `telemetria` como máximo cada **5 s**.
- Cada 15 s llega un comentario `: ping` para mantener viva la conexión; `EventSource` lo ignora.
- Cada evento tiene un `id`. Al reconectarse, el navegador envía `Last-Event-ID` y el servidor reenvía los
  eventos que faltaron (guarda los últimos 200).
- Si el token vence o el usuario deja de estar activo, el servidor cierra el flujo en menos de 30 s.

| Evento | Datos |
|---|---|
| `telemetria` | `{ id_dispositivo, numero_serie, tipo, id_bitacora, fecha_hora, latitud, longitud, nivel_bateria, sensores: [ { nombre, estado } ], estado_servicio, estado_dispositivo, fuera_de_zona }` (`id_bitacora` es `null` si no hay servicio; `fuera_de_zona` es `null` hasta que exista RF25) |
| `alerta` | Igual que una Alerta (6.6) |
| `servicio` | `{ id_bitacora, id_reserva, id_dispositivo, evento: "INICIADO" \| "FINALIZADO", fecha_hora }` |
| `servicio_en_espera` | `{ id_reserva, id_dispositivo, motivo, fecha_hora }`: la hora llegó pero el dispositivo sigue en otro servicio |
| `servicio_no_iniciado` | `{ id_reserva, id_dispositivo, motivo, cancelada, fecha_hora }`: el dispositivo no está apto (el administrador decide) o, si `cancelada` es `true`, la ventana terminó y la reserva se canceló |

Los RF pendientes agregarán los eventos `alerta_atendida` (RF27), `entrega` (RF24) y `orden` (RF14). Si el frontend
los escucha desde ya, empezarán a llegar cuando existan.

## 8. Controles de demo · solo administrador y con `MODO_DEMO=true`

Para mostrar las reglas en la presentación sin esperar. Si `MODO_DEMO` es `false`, estas rutas responden 404.

| Método y ruta | Cuerpo | Efecto |
|---|---|---|
| `POST /api/demo/reservas/{id}/iniciar` | — | Inicia ya el servicio de una reserva `PROGRAMADA` (con las mismas validaciones del inicio automático). 200 `{ resultado: "iniciada", id_reserva, id_bitacora }` · 409 con el motivo (no está programada, el dispositivo sigue en otro servicio o no está apto) |
| `POST /api/demo/dispositivos/{id}/eventos` | `{ "tipo": "BATERIA", "nivel": 19 }` · `{ "tipo": "FALLA_SENSOR", "sensor": "LIDAR" }` · `{ "tipo": "REPARAR_SENSOR", "sensor": "LIDAR" }` · `{ "tipo": "PAUSAR" }` · `{ "tipo": "REANUDAR" }` | Cambia el estado del dispositivo simulado; el efecto se ve en el siguiente ciclo de monitoreo. 200 `{ id_dispositivo, numero_serie, tipo, mensaje }` · 422 si el tipo no existe · 409 si el sensor no existe |
| `POST /api/demo/tareas/{nombre}/ejecutar` | — | Ejecuta ya una tarea: `iniciar-reservas`, `monitoreo` o `reintento-subidas`. 200 `{ tarea, resultado }` con lo que hizo · 404 si la tarea no existe |

## 9. Rendimiento y compatibilidad

- Los listados de inventario, reservas y bitácoras responden en menos de 3 s con los datos de la demo
  (RNF03). Use la paginación en lugar de pedir todo.
- Solo se usan estándares web: `EventSource` hoy, y video MP4 H.264 con `Range` cuando exista RF13. Funcionan en
  las dos últimas versiones de Chrome, Firefox y Edge (RESTR03).
- En producción la API va detrás de HTTPS (RNF05); el README explica cómo. En local es HTTP.

## 10. Usuarios y datos de prueba

Se cargan con `docker compose exec api python -m app.semilla` (ver el README).

| Correo | Contraseña | Rol |
|---|---|---|
| `admin@campus.edu.co` | `Admin123*` | Administrador |
| `operador1@campus.edu.co` … `operador3@campus.edu.co` | `Operador123*` | Operador |

Son contraseñas solo para desarrollo. El dominio `campus.edu.co` es de ejemplo.

| Datos | Detalle |
|---|---|
| Dispositivos | 1–4: robots `R-001`…`R-004` (`R-003` con batería baja, `R-004` con el LIDAR en falla); 5–6: drones `D-001`, `D-002` |
| Ubicaciones | 1 Base de operaciones, 2 Cafetería, 3 Rectoría, 4 Biblioteca, 5 Bloque A, 6 Bloque B, 7 Coliseo, 8 Cancha principal (coordenadas de ejemplo) |
| Historial | 25 servicios terminados en los últimos 4 meses, con ruta, incidencias, 3 alertas de servicio y videos |
| Reservas | Programadas para hoy (desde las 17:00) y mañana |

## 11. Lo que agregarán los RF pendientes

**Todavía no existen**: responden 404, salvo `PATCH /api/dispositivos/{id}`, que responde 405 porque esa
dirección ya existe para `GET`. Se listan para que el frontend pueda planear sus pantallas. El contrato
previsto está en `docs/especificacion-backend.md` (secciones 9 y 10); cuando cada módulo se implemente, esta guía
se actualiza con el detalle.

| RF | Qué agregará en la interfaz | Rutas y eventos previstos |
|---|---|---|
| RF02 | Editar dispositivo | `PATCH /api/dispositivos/{id}` |
| RF03 | Dar de baja dispositivo | `POST /api/dispositivos/{id}/baja` |
| RF13 | Buscar y reproducir videos (enlace firmado y `Range`) | `GET /api/videos`, `GET /api/videos/{id}/reproducir`, `GET /api/videos/{id}/contenido` |
| RF14 | Botones de retorno a base y parada de emergencia | `POST /api/bitacoras/{id}/ordenes`, evento `orden` |
| RF15 | Mantenimientos | `GET/POST /api/dispositivos/{id}/mantenimientos`, `POST /api/mantenimientos/{id}/cerrar` |
| RF16 | Alertas de mantenimiento preventivo | alertas de tipo `MANTENIMIENTO` en `GET /api/alertas` y en el evento `alerta` |
| RF17 | Reporte por dispositivo | `GET /api/dispositivos/{id}/reporte?desde=&hasta=` |
| RF19 | Desactivar usuario | `POST /api/usuarios/{id}/desactivar` |
| RF21 | Cancelar y reprogramar reservas | `POST /api/reservas/{id}/cancelar`, `POST /api/reservas/{id}/reprogramar` |
| RF22 | Sugerencia de dispositivo (reserva en dos pasos, RNF07) | `GET /api/reservas/sugerencia` |
| RF23 | Validación de clima para drones | error `CLIMA_NO_APTO` y advertencia `CLIMA_NO_VERIFICADO` en `POST /api/reservas`; `PUT /api/demo/clima` |
| RF24 | Confirmación de entrega con código | evento `entrega`; `POST /api/demo/dispositivos/{id}/codigo-entrega` |
| RF25 | Zona de operación en el mapa y alertas `SALIDA_DE_ZONA` | `GET /api/zona-operacion`, `fuera_de_zona` en `telemetria`, eventos de demo `SALIR_DE_ZONA` y `VOLVER_A_ZONA` |
| RF26 | Borrado de videos vencidos | tarea diaria; los videos mostrarán `eliminado` |
| RF27 | Atender alertas | `POST /api/alertas/{id}/atencion`, evento `alerta_atendida` |
