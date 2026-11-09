# Pendientes para el backend (encontrados al construir el frontend)

> Lo anota el equipo de frontend para la persona 1. El frontend no modifica `backend/`; cada punto dice cómo se
> resolvió del lado del cliente mientras tanto.

| # | Prioridad | Qué pasa | Dónde | Cómo lo maneja hoy el frontend |
|---|---|---|---|---|
| 1 | Media | `telemetria.fecha_hora` llega **sin desfase** y con microsegundos (`"2026-11-09T11:57:59.434450"`). La guía (sección 1) dice ISO con `-05:00`. El evento SSE `telemetria` y el resto de endpoints sí traen `-05:00` | `GET /api/monitoreo` → `dispositivos[].telemetria.fecha_hora` | `utils/formato.ts › aFecha()` asume Bogotá si no hay desfase y recorta a milisegundos |
| 2 | Baja | `VALIDACION` devuelve **un solo campo** por respuesta. Con fecha en el pasado y origen = destino solo llega `hora_inicio`; el usuario corrige un error a la vez | `POST /api/reservas` | El formulario valida en el cliente origen ≠ destino, la duración y los obligatorios antes de enviar |
| 3 | Baja | El `mensaje` de `CRUCE_HORARIO` trae la fecha en ISO ("… la reserva #32 el 2026-11-09 de 11:54 a 11:57") | `POST /api/reservas` | Se muestra tal cual, y debajo la reserva en conflicto con la fecha formateada |
| 4 | Baja | En la semilla, la bitácora #25 (R-004) registra el LIDAR en `FALLA` durante todo el recorrido, pero tiene 0 incidencias y 0 alertas. Además, R-004 no debería poder reservarse con el sensor en falla (RF07). Parece un dato inconsistente del historial | `app/semilla.py` | Nada: solo se muestra |
| 5 | Media | Se pidió que el administrador pueda quitar operadores desde Usuarios. No hay ruta para borrar usuarios, y los requisitos piden **desactivar** (RF19), porque reservas, bitácoras y auditoría los referencian. Falta implementar `POST /api/usuarios/{id}/desactivar` (especificación 7.1 y 8: 409 si es uno mismo o el último admin activo; auditado como `BAJA`) y sumar `RF19` a `requisitos_activos`. Confirmar si el módulo usará la función `usuarios.gestionar` o una nueva | Usuarios (RF19) | El botón **Desactivar** con confirmación ya está hecho (`paginas/Usuarios.tsx`) y aparece solo cuando `RF19` esté en `requisitos_activos`. Hoy no se ve |
| 6 | Informativo | Una reserva creada para el minuto en curso arranca sola en ~1 s, así que `POST /api/demo/reservas/{id}/iniciar` responde 409 "no está programada" | Inicio automático | Si el inicio por demo da 409, el frontend consulta la reserva y, si ya está `EN_CURSO`, sigue como si hubiera iniciado |
