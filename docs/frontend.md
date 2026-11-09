# Frontend — Torre de control

React 18 + Vite + TypeScript en `frontend/`. Librerías: React Router y Leaflet. Nada más.
Sigue el contrato de `docs/guia-frontend.md`.

## Cómo correrlo (PowerShell)

```powershell
# Backend arriba primero (ver README): docker compose up --build -d ; docker compose exec api python -m app.semilla
cd frontend
npm install
npm run dev          # http://localhost:5173 (el proxy de Vite manda /api y /health a http://127.0.0.1:8010)
npm run build        # verificación de tipos + build de producción
```

## Diseño

Dirección visual de "torre de control del campus":
- Paneles rectos de 1 px sobre una retícula técnica, en modo claro (papel de plano) u oscuro (sala de control). El botón **Claro/Oscuro** está en la barra superior.
- Un solo acento, naranja de señalización, reservado para lo activo y las alertas.
- Tipografías Archivo (condensada en los rótulos) e IBM Plex Mono para datos y telemetría.
- Glifos SVG propios de robot y drone.
- Batería como medidor de 10 celdas: pasa al acento bajo 30 % y parpadea bajo 20 %.

## Pantallas y requisitos

Cada pantalla aparece solo si sus RF están en `requisitos_activos` y su función en `funciones` (`src/sesion/permisos.ts`).

| Pantalla | Ruta | RF | Función |
|---|---|---|---|
| Login (token en `sessionStorage`, `/auth/yo` al recargar, cierre ante 401 o a las 8 h) | `/login` | RF20 | — |
| Monitoreo: mapa en vivo (SSE), flota con batería, sensores y fase, avance del servicio, alertas, registro en vivo | `/monitoreo` | RF09, RF10, RF11 | `monitoreo.ver` |
| Inventario con filtros por tipo y estado, y detalle (sensores, última lectura en el mapa, reservas, servicios) | `/inventario`, `/inventario/:id` | RF04 | `inventario.ver` |
| Registrar dispositivo | `/inventario/nuevo` | RF01 | `inventario.gestionar` |
| Reservas: lista con filtros y detalle (con código de entrega para el admin) | `/reservas`, `/reservas/:id` | RF05 | `reservas.ver` |
| Nueva reserva: tarjetas de dispositivo con su aptitud, agenda del día del dispositivo, errores `CRUCE_HORARIO`, `DISPOSITIVO_NO_APTO` y `VALIDACION` junto a cada campo | `/reservas/nueva` | RF05, RF06, RF07 | `reservas.gestionar` |
| Bitácoras: lista y detalle con ruta en el mapa, reproducción del recorrido, incidencias y video | `/bitacoras`, `/bitacoras/:id` | RF08, RF12 | `bitacoras.ver` |
| Alertas: historial y detalle con su ubicación | `/alertas`, `/alertas/:id` | RF11 | `alertas.ver` |
| Usuarios: listar, crear y editar nombre y rol | `/usuarios` | RF18 | `usuarios.gestionar` |
| Usuarios: botón **Desactivar** con confirmación (oculto hasta que el backend active RF19) | `/usuarios` | RF19 | `usuarios.gestionar` |
| Auditoría | `/auditoria` | RNF09 | `auditoria.ver` |
| Panel de demo | `/demo` | — | `demo.usar` |

Las alertas que llegan por SSE se muestran como aviso en **cualquier pantalla**, con enlace "Ver en el mapa". Al operador se le resaltan las alertas de los servicios a su cargo.

## Guion de la demo (≈ 10 min)

Antes: en el `.env`, `MODO_DEMO=true` y `RETRASO_ALERTA_MIN=1`. Luego cargue la semilla limpia (`--reiniciar` y después `docker compose restart api`) y abra `npm run dev`.

1. **Login (RF20).** Entre como `operador1@campus.edu.co`: el menú tiene 5 opciones y no puede crear reservas. Salga y entre como `admin@campus.edu.co` / `Admin123*`: aparecen Usuarios, Auditoría y Panel de demo.
2. **Inventario (RF04, RF01).** Use los filtros por tipo y estado. R-003 tiene la batería al 28 % y R-004 el LIDAR en falla. Registre `R-010`; repetirlo da `DUPLICADO`.
3. **Reserva (RF05–RF07).** En Reservas → Nueva reserva, elija Pedido de cafetería, pulse **Ahora**, 3 min, un operador, Cafetería → Rectoría y R-001. Confirme y aparece el **código de 4 dígitos**. Luego:
   - "Crear otra" con R-001 a la misma hora da **CRUCE_HORARIO**, con la reserva en conflicto y el tramo naranja en la agenda.
   - Con R-004 da **DISPOSITIVO_NO_APTO** ("Sensor LIDAR en falla").
4. **Inicio y monitoreo (RF08–RF10).** Pulse "Iniciar ahora (demo)", o espere: arranca sola en segundos. En Monitoreo, R-001 sale de la base con el anillo naranja, deja su recorrido y una línea punteada hacia el destino. Las lecturas llegan cada 5 s y la fila destella con cada una.
5. **Alertas (RF11).** En el Panel de demo, en "Provocar eventos", elija R-001 y pulse **Provocar falla** en el LIDAR: llega el aviso "R-001: sensor LIDAR en falla" y el marcador late. Luego **Batería 19 %** → **Aplicar**: llega una segunda alerta. **Reparar** y **80 %** lo normalizan. Para mostrar el retraso: **Pausar**, esperar a que pase el fin estimado + 1 min, y **Reanudar**.
6. **Cierre y bitácora (RF08, RF12).** Cuando el robot vuelve a la base llega "Servicio finalizado" con enlace a la bitácora. Allí se ven la ruta, **Reproducir** recorrido, las incidencias (al hacer clic se ubican en el mapa) y el video guardado.
7. **Auditoría (RNF09).** Quién creó el dispositivo y la reserva.

El Panel de demo también tiene una **Reserva rápida para ahora** (dispositivo → reservar e iniciar en un clic) y una **consola** con los comandos enviados y los eventos recibidos.

Nota: el mapa usa las teselas de OpenStreetMap, que necesitan internet. Sin conexión, los marcadores y las rutas se dibujan igual sobre el fondo liso.
