# Guion de la demo por la API

> Paso a paso para presentar el backend (12 RF) en unos 15 minutos sin el frontend: con Swagger
> (`http://localhost:8010/docs`) o con `backend/tests/http/api.http` (REST Client de VS Code). Cada paso dice qué
> requisito muestra y qué se espera ver. Los controles `/api/demo/...` existen solo con `MODO_DEMO=true`.
> Para la demo con la interfaz web, use el guion de `docs/frontend.md`.

## 0. Preparación (antes de la presentación)

1. En el `.env` de la demo:

   ```ini
   MODO_DEMO=true
   RETRASO_ALERTA_MIN=1       # la alerta de retraso aparece al minuto en vez de a los 10 (decisión D15)
   ```

   Si el equipo tiene el bucket de AWS, agregue la configuración de S3 del README (RESTR04).
2. Levante todo y cargue datos limpios (PowerShell, en la raíz del proyecto):

   ```powershell
   docker compose up --build -d
   docker compose exec api python -m app.semilla --reiniciar
   docker compose restart api
   Invoke-RestMethod http://localhost:8010/health     # todo "ok"
   ```

3. Ensayo rápido del flujo completo (≈ 2 min). Deja una reserva y su servicio de más; si quiere empezar limpio,
   vuelva a correr el paso 2 después:

   ```powershell
   docker compose exec api python scripts/demo_e2e.py --url http://localhost:8000
   ```

4. Tenga abierta una terminal con el tiempo real, para que el público vea los eventos llegar (reemplace el token
   por el del operador, que sale del login del paso 1):

   ```powershell
   curl.exe -N "http://localhost:8010/api/monitoreo/stream?token=TOKEN_DEL_OPERADOR"
   ```

Datos útiles de la semilla: ubicaciones 1 Base de operaciones, 2 Cafetería, 3 Rectoría, 4 Biblioteca, 5 Bloque A,
6 Bloque B, 7 Coliseo, 8 Cancha principal. Dispositivos 1–4 `R-001`…`R-004` (robots) y 5–6 `D-001`, `D-002`
(drones). Usuarios: 1 Emily Bonilla (administradora) y 2 Santiago Figueroa (operador). Reservas 1 a 3
terminadas y 4 y 5 programadas para mañana (R-001 a las 09:00 y D-002 a las 10:00). La auditoría empieza vacía.

## 1. Sesión, roles y usuarios (RF20, RF18, RNF01)

- `POST /api/auth/login` con `emily.bonilla@campus.edu.co` / `Admin123*` → token, `funciones` y
  `requisitos_activos` (los 12 RF).
- Lo mismo con `santiago.figueroa@campus.edu.co` / `Operador123*`: recibe menos funciones.
- Con el token del operador, `POST /api/dispositivos` → **403**: solo el administrador registra dispositivos.
- **RF18:** `POST /api/usuarios` con un operador nuevo → 201, sin la contraseña en la respuesta. Repetir el correo
  → **409 `DUPLICADO`**.

## 2. Inventario (RF01, RF04)

- `GET /api/dispositivos`: los 6 dispositivos con estado, batería y sensores en falla (`R-004` tiene el LIDAR).
- `POST /api/dispositivos` con `{ "tipo": "ROBOT", "numero_serie": "R-010", "modelo": "Rover Mk3", "capacidad_carga_kg": 6 }`
  → 201 con los sensores por defecto. Repetirlo → **409 `DUPLICADO`**.
- `GET /api/dispositivos/7`: el detalle con sus sensores. Aparece solo en el monitoreo en el siguiente ciclo
  (RNF10). `GET /api/auditoria?entidad=dispositivo` muestra quién lo creó (RNF09).

## 3. Reserva (RF05, RF06, RF07)

1. `POST /api/reservas` con `{ "tipo_servicio": "PEDIDO_CAFETERIA", "fecha": HOY, "hora_inicio": HH:MM,
   "duracion_estimada_min": 3, "id_origen": 2, "id_destino": 3, "id_dispositivo": 1, "id_operador": 2 }` (use la
   hora actual) → 201 con el **código de entrega de 4 dígitos**.

Reglas que se pueden mostrar aquí mismo:

- **RF06:** otra reserva del mismo robot que se cruce → **409 `CRUCE_HORARIO`** con la reserva en conflicto.
- **RF07:** reservar `R-004` (id 4) → **409 `DISPOSITIVO_NO_APTO`**, "Sensor LIDAR en falla". `R-003` (id 3) →
  "Batería 28 % (mínimo 30 %)".
- Tipo equivocado: un drone para un pedido de cafetería → **409 `TIPO_DISPOSITIVO_INCORRECTO`**.

## 4. Servicio en curso (RF08–RF11, RNF02)

1. La reserva del paso 3 empieza sola en menos de 10 s (o use `POST /api/demo/reservas/{id}/iniciar`). En la
   terminal del SSE llega `servicio` **INICIADO** y luego `telemetria` del robot cada 5 s.
2. `GET /api/monitoreo`: la foto del panel, con el robot en servicio, su posición, batería, fase y destino.
3. **RF11:** `POST /api/demo/dispositivos/{id}/eventos` con `{ "tipo": "BATERIA", "nivel": 19 }` → llega un
   evento `alerta` "batería 19 % (mínimo 20 %)" con la ubicación. Con `{ "tipo": "FALLA_SENSOR", "sensor": "LIDAR" }`
   llega otra; no se repiten mientras sigan activas. `{ "tipo": "REPARAR_SENSOR", "sensor": "LIDAR" }` la normaliza.
4. **Retraso (RF11):** `{ "tipo": "PAUSAR" }` y espere a que pase el fin de la reserva + 1 min (con
   `RETRASO_ALERTA_MIN=1`) → alerta `RETRASO`. `{ "tipo": "REANUDAR" }` para seguir.
5. `GET /api/alertas?tipo=SERVICIO`: las alertas del servicio, con su incidencia y ubicación.

## 5. Cierre, bitácora y video (RF08, RF12)

1. El robot deja el pedido en el destino y vuelve a la base (la confirmación con código era del RF24, fuera del
   alcance).
   Al llegar llega `servicio` **FINALIZADO**.
2. `GET /api/bitacoras/{id}`: salida, regreso, horas de uso, incidencias (con su alerta) y el **video** guardado
   (RF12). `GET /api/bitacoras/{id}/ruta`: los puntos del recorrido con las lecturas de los sensores.
3. El dispositivo quedó `DISPONIBLE` (o `EN_CARGA` si terminó con menos de 30 %) y sus horas de uso aumentaron.
4. Si la subida del video falla (por ejemplo, sin conexión a S3), la bitácora se cierra igual y
   `POST /api/demo/tareas/reintento-subidas/ejecutar` lo sube después.

## 6. Reinicio y auditoría (P1, RNF09)

- Con un servicio en curso, `docker compose restart api`: al volver, el dispositivo sigue desde su último punto.
- `GET /api/auditoria` muestra quién creó cada usuario, dispositivo y reserva durante la demo (empieza vacía).
