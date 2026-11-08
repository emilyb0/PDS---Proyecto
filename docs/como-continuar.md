# Cómo continuar el proyecto

> Para el equipo. Qué está hecho, qué falta, cómo levantar el backend y cómo agregar un requisito pendiente sin
> romper lo que ya funciona.

## 1. Qué está hecho

Este repositorio es la **entrega 1**: el núcleo del backend con **12 requisitos funcionales**, más la
infraestructura, los requisitos no funcionales y las restricciones. Todo tiene pruebas y funciona sin frontend:
se prueba con Swagger (`/docs`), con `backend/tests/http/api.http` o con `backend/scripts/demo_e2e.py`.

La columna "Especificación" dice dónde empieza cada regla en `docs/especificacion-backend.md`.

| RF | Nombre | Especificación |
|---|---|---|
| RF01 | Registrar dispositivo | 7.2, "Registrar (RF01)" |
| RF04 | Consultar inventario | 7.2, "Inventario (RF04)" |
| RF05 | Crear reserva | 7.4, "Crear (RF05)" |
| RF06 | Validar cruce de horarios | 7.4, "Crear", paso 3 |
| RF07 | Validar batería y sensores | 7.4, "Crear", paso 4 |
| RF08 | Registrar bitácora del servicio | 7.5, "Inicio" y "Cierre" |
| RF09 | Monitorear dispositivos | 7.5, "Monitoreo" |
| RF10 | Actualizar monitoreo (tiempo real) | 7.5, "Monitoreo", y 10 (SSE) |
| RF11 | Generar alertas de servicio | 7.5, "Alertas de servicio" |
| RF12 | Almacenar video del servicio | 7.5, "Cierre", y 7.6 |
| RF18 | Registrar usuario | 7.1, "Registrar" |
| RF20 | Iniciar sesión | 7.1, "Login", y 5 (roles) |

Qué hace hoy el sistema: usuarios y sesión con roles; registro e inventario de dispositivos; reservas con
validación de cruces, batería y sensores; inicio automático del servicio; monitoreo en tiempo real cada 5 s;
alertas de batería, sensor y retraso; bitácora con ruta e incidencias; y el video MP4 de cada servicio guardado en
disco o en AWS S3. Los robots y drones son simulados (RESTR01).

## 2. Qué falta

Faltan **15 requisitos**. Cada uno se agrega como un **módulo**: una carpeta aparte que se "enchufa" al núcleo
sin modificarlo (sección 5).

- **Prioridad:** la de `docs/requisitos.md`.
- **Especificación:** dónde empieza la regla en `docs/especificacion-backend.md`. Sus endpoints están en la
  tabla de la sección 9 y sus eventos de tiempo real en la sección 10.
- **Decisiones:** las de `docs/decisiones.md` que ya resolvieron dudas de ese RF. Léalas antes de empezar.

| RF | Nombre | Prioridad | Especificación | Carpeta | Se engancha en | Decisiones |
|---|---|---|---|---|---|---|
| RF02 | Editar dispositivo | Media | 7.2, "Editar (RF02)" | `rf02_editar_dispositivo` | `routers` | D6, F2-5 |
| RF03 | Dar de baja dispositivo | Media | 7.2, "Dar de baja (RF03)" | `rf03_dar_de_baja` | `routers` | F2-3, F2-4, F2-5 |
| RF13 | Consultar videos | Media | 7.6, "Buscar" y "Reproducir" | `rf13_consultar_videos` | `routers`, `funciones` | M-8, D20, F5-2 a F5-4 |
| RF14 | Ordenar retorno o parada | Alta | 7.5, "Órdenes" | `rf14_ordenar_retorno` | `routers`, `funciones` | M-9, F4-15 |
| RF15 | Registrar mantenimiento | Media | 7.3, "Registrar" y "Cerrar" | `rf15_mantenimiento` | `routers`, `funciones` | D6, D7, F2-4, F2-5, M-10 |
| RF16 | Alertar mantenimiento preventivo | Media | 7.3, "Alerta preventiva", y 12 | `rf16_mantenimiento_preventivo` | `al_finalizar_servicio`, `tareas` | D8, F2-6, F4-19, F5-10 |
| RF17 | Generar reportes | Media | 7.7, "Reporte" | `rf17_reportes` | `routers`, `funciones` | D17, F5-6 |
| RF19 | Desactivar usuario | Media | 7.1, "Desactivar" | `rf19_desactivar_usuario` | `routers` | P2, D11, F1-9 |
| RF21 | Cancelar o reprogramar reserva | Media | 7.4, "Cancelar" y "Reprogramar" | `rf21_cancelar_reprogramar` | `routers` | M-9, F3-8 |
| RF22 | Sugerir dispositivo | Alta | 7.4, "Sugerencia" | `rf22_sugerir_dispositivo` | `routers` (usa `evaluador_clima` si existe) | T8, M-12, F3-10 |
| RF23 | Validar clima para drones | Alta | 7.4, "Crear", paso 5 | `rf23_validar_clima` | `validadores_reserva`, `evaluador_clima`, `servicios`, `routers` | D3, F3-9, F3-11, F3-12 |
| RF24 | Confirmar entrega con código | Media | 7.5, "Entrega con código" | `rf24_entrega_con_codigo` | `ajustes_orden_inicio`, `manejadores_evento`, `verificaciones_monitor`, `routers` | D4, M-6, F4-16 |
| RF25 | Alertar salida de zona de operación | Alta | 7.5, "Alertas de servicio" (`SALIDA_DE_ZONA`) | `rf25_salida_de_zona` | `verificaciones_monitor`, `eventos_demo`, `chequeos_salud`, `routers` | D19, F2-7, F2-8, F4-17 |
| RF26 | Eliminar videos vencidos | Media | 7.6, "Retención", y 12 | `rf26_eliminar_videos_vencidos` | `tareas` | D16, D20, F5-5 |
| RF27 | Atender alerta de servicio | Media | 7.5, "Atención" | `rf27_atender_alerta` | `routers`, `funciones` | D14, F4-18 |

Algunos dependen de otros: RF16 necesita los mantenimientos de RF15, y RF22 usa el clima de RF23 si está. Lo que
el núcleo ya trae para ellos: los modelos de las 18 tablas, los métodos de dominio (por ejemplo
`Dispositivo.editar`, `Dispositivo.requiere_mantenimiento`, `Video.esta_vencido`), el código de entrega de 4
dígitos de cada reserva de robot y el simulador completo (órdenes, espera del código, salida de zona).

## 3. Cómo levantar el proyecto

Necesita Windows con **Docker Desktop** encendido y **PowerShell**. Desde la carpeta del proyecto:

```powershell
Copy-Item .env.example .env                      # solo la primera vez
docker compose up --build -d                     # base de datos y API
docker compose exec api python -m app.semilla    # datos de ejemplo
```

- Abra **http://localhost:8010/docs**, entre con `admin@campus.edu.co` / `Admin123*` en `POST /api/auth/login` y
  pegue el `token` en **Authorize**.
- Para ver el flujo completo: `docker compose exec api python scripts/demo_e2e.py --url http://localhost:8000`.
- Pruebas y estilo: `docker compose exec api pytest` y `docker compose exec api ruff check .`.

El `README.md` tiene el resto: usuarios, comandos, S3 y problemas comunes.

## 4. Qué leer primero

1. `CLAUDE.md`: las reglas del proyecto (esquema, hora, nombres, pruebas, núcleo y módulos).
2. `docs/requisitos.md`: el RF que le tocó. **Manda sobre todo lo demás.**
3. `docs/arquitectura.md`: cómo se arma un módulo y qué puntos de extensión hay.
4. `docs/especificacion-backend.md`: la sección del RF (tabla de la sección 2), sus endpoints (9) y eventos (10).
5. `docs/decisiones.md`: las decisiones de la tabla de la sección 2 y las de núcleo y módulos (M-1 a M-12).
6. `docs/guia-frontend.md`: el formato de las respuestas y de los errores, para que el módulo responda igual.

## 5. Cómo implementar un RF pendiente

Resumen de `docs/arquitectura.md`, secciones 3 y 6:

1. **Lea** el RF, su sección de la especificación y sus decisiones. Si algo se contradice, pregunte al equipo y
   anote la respuesta en `docs/decisiones.md`.
2. **Cree la carpeta** `backend/app/modulos/rfXX_nombre/` con su `__init__.py`, que declara
   `MODULO = ModuloRF(...)`. Ahí van sus rutas, su lógica, sus tareas y sus controles de demo. El módulo se
   descubre solo: no hay que registrarlo en otro archivo.
3. **Enganche** el módulo en los puntos de extensión que necesite (columna "Se engancha en"). Puede importar todo
   el núcleo, pero **nunca otro módulo**, y **el núcleo nunca importa el módulo**. Si el núcleo necesita avisarle
   algo que hoy no tiene punto de extensión, se agrega uno en `app/nucleo/extensiones.py`; nunca un import.
4. **Escriba las pruebas** en `backend/tests/modulos/rfXX_nombre/`, con nombres `test_rfXX_…`: los casos del RF,
   los permisos (403 al operador si es solo del administrador, RNF01) y la auditoría (RNF09) si crea, edita o da
   de baja algo.
5. **Verifique** que todo siga en verde:

   ```powershell
   docker compose exec api pytest                    # núcleo + módulos
   docker compose exec api pytest --solo-entrega-1   # el núcleo sigue funcionando sin los módulos
   docker compose exec api ruff check .
   docker compose exec api ruff format --check .
   ```

6. **Documente:** su fila en `docs/trazabilidad.md` (de ⏳ a ✅), sus endpoints en `docs/guia-frontend.md`, los
   puntos de extensión que usa en `docs/arquitectura.md` (sección 3), sus decisiones en `docs/decisiones.md`, el
   estado en `CLAUDE.md` y, si aplica, sus peticiones en
   `backend/tests/http/api.http`, su paso en `docs/demo.md` y sus datos de ejemplo en `backend/app/semilla.py`.

Para apagar un módulo sin borrarlo: `MODULOS_ACTIVOS` en el `.env` (`todos`, `ninguno` o una lista como
`rf15,rf16`) y `docker compose up -d api`.

## 6. Prompt de ejemplo para Claude Code

Abra Claude Code en la carpeta del proyecto y adapte este texto: cambie el RF, su carpeta, la sección de la
especificación y las decisiones según la tabla de la sección 2.

```text
Lee CLAUDE.md, docs/como-continuar.md y docs/arquitectura.md. Vamos a implementar RF15 (Registrar mantenimiento)
como módulo removible.

1. Antes de escribir código, lee RF15 en docs/requisitos.md, la sección 7.3 de docs/especificacion-backend.md
   ("Registrar" y "Cerrar"), sus filas en la tabla de la sección 9 y las decisiones D6, D7, F2-4, F2-5 y
   M-10 de docs/decisiones.md. Dime en pocas líneas qué vas a hacer y qué dudas tienes. Si dos documentos se
   contradicen, pregúntame antes de seguir.
2. Crea el módulo en backend/app/modulos/rf15_mantenimiento/ con MODULO = ModuloRF(...). No modifiques el núcleo;
   si de verdad hace falta un punto de extensión nuevo, explícame por qué antes de agregarlo. El núcleo nunca
   importa el módulo y el módulo no importa otros módulos.
3. Escribe las pruebas en backend/tests/modulos/rf15_mantenimiento/ (test_rf15_...), con los casos del RF, los
   permisos (RNF01) y la auditoría (RNF09).
4. Corre en Docker: pytest, pytest --solo-entrega-1, ruff check . y ruff format --check . Todo debe quedar en
   verde; no avances con pruebas fallando.
5. Actualiza docs/trazabilidad.md, docs/guia-frontend.md, docs/arquitectura.md (puntos de extensión),
   docs/decisiones.md (si decidiste algo), el estado en CLAUDE.md y, si aplica, backend/tests/http/api.http, docs/demo.md y backend/app/semilla.py.
6. Dame un resumen corto: qué hiciste, qué pruebas pasan y qué decidiste. No hagas commit hasta que lo revise.
```
