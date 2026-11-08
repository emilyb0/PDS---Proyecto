# Requisitos — Sistema centralizado de robots y drones

> Fuente: *PDS – Proyecto Final* (Procesos y Diseño de Software), Entregables 1 y 2 — SRS versión 1 del 28/10/2026.
> Texto transcrito del PDF sin cambiar el contenido. Si algo de este archivo choca con otro documento, **este manda**.

## Contexto del proyecto

Una universidad tiene un servicio de transporte interno con **robots y drones**, usados como prototipo para validar después su uso en sitios de difícil acceso. Hoy el servicio es manual: tres personas atienden las solicitudes y, aunque hay **6 dispositivos**, no pueden atender en paralelo porque cada dispositivo necesita una persona que lo maneje y configure. Se necesita un sistema centralizado que configure y supervise los dispositivos sin depender de una persona por artefacto.

**Servicios que se ofrecen hoy**

- **Robots:** transporte de objetos pequeños — documentos entre oficinas y pedidos de cafetería al personal administrativo.
- **Drones:** grabación de encuentros artísticos o deportivos en zonas abiertas.

**Lo mínimo que debe tener el sistema (enunciado)**

- Administración e inventario de los dispositivos.
- Bitácora de los servicios (hora de salida, hora de regreso, etc.).
- Sistema de reservas para el uso de los dispositivos.
- Monitoreo centralizado del estado de los dispositivos antes, durante y al finalizar un servicio: ubicación, batería, estado de sensores, estado del pedido o servicio, etc.
- Robots y drones graban su recorrido con sus cámaras; los videos quedan guardados en un servicio cloud.

**Observaciones del enunciado**

- El sistema es para los **administradores de los dispositivos**, no para el cliente final.
- Se puede suponer o añadir lo que se considere necesario.
- El demo es **solo de software**: los datos del hardware se emulan (por ejemplo, registros de vuelo de un drone ya cargados en la base de datos).

**Usuarios del sistema:** Administrador y Operador (ver RF18–RF20). Stakeholders adicionales: personal administrativo, cafeterías, organizadores de eventos, directivos y el grupo que elabora el robot.

---

## Requisitos funcionales

| ID | Nombre | Prioridad | Dependencias |
|---|---|---|---|
| RF01 | Registrar dispositivo | Alta | RF20 |
| RF02 | Editar dispositivo | Media | RF01 |
| RF03 | Dar de baja dispositivo | Media | RF01 |
| RF04 | Consultar inventario | Alta | RF01 |
| RF05 | Crear reserva | Alta | RF04, RF20 |
| RF06 | Validar cruce de horarios | Alta | RF05 |
| RF07 | Validar batería y sensores | Alta | RF05, RF09 |
| RF08 | Registrar bitácora del servicio | Alta | RF05, RF09 |
| RF09 | Monitorear dispositivos | Alta | RF05 |
| RF10 | Actualizar monitoreo | Alta | RF09 |
| RF11 | Generar alertas de servicio | Alta | RF09 |
| RF12 | Almacenar video del servicio | Alta | RF08 |
| RF13 | Consultar videos | Media | RF12 |
| RF14 | Ordenar retorno o parada | Alta | RF09, RF08 |
| RF15 | Registrar mantenimiento | Media | RF01 |
| RF16 | Alertar mantenimiento preventivo | Media | RF15, RF08 |
| RF17 | Generar reportes | Media | RF08 |
| RF18 | Registrar usuario | Alta | N/A |
| RF19 | Desactivar usuario | Media | RF18 |
| RF20 | Iniciar sesión | Alta | RF18 |
| RF21 | Cancelar o reprogramar reserva | Media | RF05 |
| RF22 | Sugerir dispositivo | Alta | RF04, RF05, RF09 |
| RF23 | Validar clima para drones | Alta | RF05 |
| RF24 | Confirmar entrega con código | Media | RF05, RF08 |
| RF25 | Alertar salida de zona de operación | Alta | RF09 |
| RF26 | Eliminar videos vencidos | Media | RF12 |
| RF27 | Atender alerta de servicio | Media | RF11 |

### RF01 — Registrar dispositivo

**Descripción.** El sistema debe permitir al administrador registrar un dispositivo nuevo ingresando tipo (robot o drone), modelo, número de serie, capacidad de carga en kilogramos o autonomía de vuelo en minutos y estado inicial.

**Proceso**

1. El administrador abre el inventario y elige registrar un dispositivo.
2. El administrador ingresa los datos del dispositivo.
3. El sistema valida que los campos obligatorios estén completos y que el número de serie no exista.
4. El sistema guarda el dispositivo con estado Disponible y lo muestra en el inventario.

**Dependencias:** RF20 · **Referencias cruzadas:** RF04, RNF01 · **Prioridad:** Alta · **Estado:** Por validar

### RF02 — Editar dispositivo

**Descripción.** El sistema debe permitir al administrador modificar el modelo, la capacidad de carga o autonomía de vuelo y el estado de un dispositivo registrado.

**Proceso**

1. El administrador selecciona un dispositivo del inventario.
2. El administrador modifica los datos.
3. El sistema valida los campos obligatorios.
4. El sistema guarda los cambios con la fecha de modificación.

**Dependencias:** RF01 · **Referencias cruzadas:** RF04 · **Prioridad:** Media · **Estado:** Por validar

### RF03 — Dar de baja dispositivo

**Descripción.** Cuando un dispositivo no tenga reservas pendientes, el sistema debe permitir al administrador darlo de baja indicando el motivo y la fecha de la baja.

**Proceso**

1. El administrador selecciona el dispositivo y elige darlo de baja.
2. El sistema verifica que el dispositivo no tenga reservas pendientes; si las tiene, muestra un mensaje y no permite la baja.
3. El administrador ingresa el motivo de la baja.
4. El sistema cambia el estado del dispositivo a Fuera de servicio y lo excluye de nuevas asignaciones.

**Dependencias:** RF01 · **Referencias cruzadas:** RF06, RNF01 · **Prioridad:** Media · **Estado:** Por validar

**Comentarios:** Se agregó la condición de no tener reservas pendientes.

### RF04 — Consultar inventario

**Descripción.** El sistema debe mostrar al administrador la lista de dispositivos con tipo, modelo y estado actual (disponible, en servicio, en carga, en mantenimiento o fuera de servicio) y debe permitir filtrarla por tipo y por estado.

**Proceso**

1. El administrador abre el inventario.
2. El sistema muestra la lista de dispositivos con su estado actual.
3. El administrador aplica filtros por tipo o estado.
4. El sistema muestra solo los dispositivos que cumplen el filtro.

**Dependencias:** RF01 · **Referencias cruzadas:** RNF03 · **Prioridad:** Alta · **Estado:** Por validar

### RF05 — Crear reserva

**Descripción.** El sistema debe permitir al administrador crear una reserva indicando tipo de servicio (entrega de documentos, pedido de cafetería o grabación de evento), fecha, hora de inicio, duración estimada, punto de origen, punto de destino y operador responsable.

**Proceso**

1. El administrador registra la solicitud del servicio con sus datos.
2. El sistema muestra los dispositivos del tipo requerido que están disponibles y sugiere uno (RF22).
3. El administrador elige un dispositivo y el operador responsable.
4. El sistema valida RF06 y RF07 (y RF23 si el dispositivo es un drone) y guarda la reserva con el operador responsable.

**Dependencias:** RF04, RF20 · **Referencias cruzadas:** RF06, RF07, RF22, RF23, RNF07 · **Prioridad:** Alta · **Estado:** Por validar

### RF06 — Validar cruce de horarios

**Descripción.** Cuando el administrador asigne un dispositivo a una reserva, el sistema debe verificar que ese dispositivo no tenga otra reserva en el mismo rango de horario y, si existe un cruce, debe rechazar la asignación mostrando la reserva con la que se cruza.

**Proceso**

1. El administrador asigna un dispositivo a la reserva.
2. El sistema compara el horario con las reservas existentes del dispositivo.
3. Si hay cruce, el sistema rechaza la asignación y muestra la reserva en conflicto.
4. Si no hay cruce, el sistema confirma la asignación.

**Dependencias:** RF05 · **Referencias cruzadas:** N/A · **Prioridad:** Alta · **Estado:** Por validar

### RF07 — Validar batería y sensores

**Descripción.** Cuando el administrador asigne un dispositivo a una reserva, el sistema debe rechazar la asignación si el dispositivo tiene una batería inferior al 30% o algún sensor en estado de falla, indicando el motivo del rechazo.

**Proceso**

1. El administrador asigna un dispositivo a la reserva.
2. El sistema consulta la batería y el estado de los sensores del dispositivo.
3. Si la batería es inferior al 30% o hay un sensor en falla, el sistema rechaza la asignación y muestra el motivo.
4. Si cumple las condiciones, el sistema confirma la asignación.

**Dependencias:** RF05, RF09 · **Referencias cruzadas:** RF11 · **Prioridad:** Alta · **Estado:** Por validar

### RF08 — Registrar bitácora del servicio

**Descripción.** Cuando un servicio inicie y cuando finalice, el sistema debe registrar en la bitácora del servicio la hora de salida, la hora de regreso, el dispositivo, el operador responsable asignado en la reserva, la ruta recorrida y las incidencias reportadas.

**Proceso**

1. El dispositivo inicia el servicio.
2. El sistema registra la hora de salida, el dispositivo y el operador responsable asignado en la reserva.
3. Durante el servicio el sistema guarda la ruta y las incidencias.
4. Al finalizar, el sistema registra la hora de regreso y cierra la bitácora.

**Dependencias:** RF05, RF09 · **Referencias cruzadas:** RF14, RF17 · **Prioridad:** Alta · **Estado:** Por validar

### RF09 — Monitorear dispositivos

**Descripción.** Mientras un dispositivo tenga un servicio asignado, el sistema debe ser capaz de obtener su ubicación, nivel de batería, estado de sensores y estado del servicio mediante la API del dispositivo y debe mostrarlos al administrador en el panel de monitoreo.

**Proceso**

1. El sistema consulta la API del dispositivo.
2. El dispositivo responde con ubicación, batería y estado de sensores.
3. El sistema muestra los datos en el panel de monitoreo junto al estado del servicio.

**Dependencias:** RF05 · **Referencias cruzadas:** RF10, RNF02, RESTR01 · **Prioridad:** Alta · **Estado:** Por validar

**Comentarios:** En el demo la API del dispositivo es simulada.

### RF10 — Actualizar monitoreo

**Descripción.** Mientras un dispositivo esté en servicio, el sistema debe actualizar en el panel de monitoreo su ubicación, batería y estado de sensores con un intervalo máximo de 5 segundos.

**Proceso**

1. El sistema consulta la API del dispositivo cada 5 segundos.
2. El sistema actualiza los datos del panel sin que el administrador recargue la página.

**Dependencias:** RF09 · **Referencias cruzadas:** RNF02 · **Prioridad:** Alta · **Estado:** Por validar

### RF11 — Generar alertas de servicio

**Descripción.** Cuando un dispositivo en servicio tenga una batería inferior al 20%, un sensor en falla o un retraso mayor a 10 minutos respecto al tiempo estimado, el sistema debe mostrar una alerta en el panel de monitoreo al administrador y al operador, indicando el dispositivo y la causa.

**Proceso**

1. El sistema recibe los datos actualizados del dispositivo.
2. El sistema compara batería, sensores y tiempo transcurrido con los umbrales.
3. Si se supera un umbral, el sistema muestra la alerta al administrador y al operador con el dispositivo y la causa.
4. El operador atiende la alerta (RF27) y el administrador decide si aplica RF14.

**Dependencias:** RF09 · **Referencias cruzadas:** RF14, RF27 · **Prioridad:** Alta · **Estado:** Por validar

**Comentarios:** La alerta la ve el administrador y el operador; el operador la atiende (RF27).

### RF12 — Almacenar video del servicio

**Descripción.** Cuando un servicio finalice, el sistema debe ser capaz de recibir el video grabado por la cámara del dispositivo, asociarlo al servicio y almacenarlo en formato MP4 en el servicio cloud definido en RESTR04.

**Proceso**

1. El dispositivo termina el servicio y envía el video.
2. El sistema recibe el archivo en formato MP4.
3. El sistema lo guarda en el servicio cloud.
4. El sistema asocia el enlace del video al servicio en la bitácora.

**Dependencias:** RF08 · **Referencias cruzadas:** RNF04, RNF08, RESTR04 · **Prioridad:** Alta · **Estado:** Por validar

**Comentarios:** Ubicación y formato por validar con el cliente.

### RF13 — Consultar videos

**Descripción.** El sistema debe permitir al administrador y al operador buscar videos filtrando por fecha, dispositivo o tipo de servicio y reproducir el video seleccionado.

**Proceso**

1. El usuario abre el módulo de videos.
2. El usuario aplica filtros por fecha, dispositivo o tipo de servicio.
3. El sistema muestra los videos que cumplen el filtro.
4. El usuario selecciona un video y el sistema lo reproduce.

**Dependencias:** RF12 · **Referencias cruzadas:** RNF08 · **Prioridad:** Media · **Estado:** Por validar

### RF14 — Ordenar retorno o parada

**Descripción.** Cuando un dispositivo esté en servicio, el sistema debe permitir al administrador enviar una orden de retorno a base o de parada de emergencia y debe registrar la orden como incidencia en la bitácora.

**Proceso**

1. El administrador selecciona el dispositivo en el panel de monitoreo.
2. El administrador elige retorno a base o parada de emergencia y confirma.
3. El sistema envía la orden al dispositivo.
4. El sistema registra la orden como incidencia en la bitácora.

**Dependencias:** RF09, RF08 · **Referencias cruzadas:** RF11, RESTR01 · **Prioridad:** Alta · **Estado:** Por validar

**Comentarios:** En el demo la orden es simulada.

### RF15 — Registrar mantenimiento

**Descripción.** El sistema debe permitir al operador registrar un mantenimiento de un dispositivo con fecha, tipo (preventivo o correctivo), descripción y responsable, y debe cambiar el estado del dispositivo a En mantenimiento mientras este dure.

**Proceso**

1. El operador selecciona el dispositivo.
2. El operador ingresa los datos del mantenimiento.
3. El sistema guarda el registro y cambia el estado a En mantenimiento.
4. Al cerrar el mantenimiento, el sistema cambia el estado a Disponible.

**Dependencias:** RF01 · **Referencias cruzadas:** RF16 · **Prioridad:** Media · **Estado:** Por validar

### RF16 — Alertar mantenimiento preventivo

**Descripción.** Cuando un dispositivo cumpla 30 días o 50 horas de uso desde su último mantenimiento, lo que ocurra primero, el sistema debe mostrar al operador una alerta de mantenimiento preventivo.

**Proceso**

1. Al cerrar cada servicio, el sistema suma las horas de uso del dispositivo.
2. El sistema compara los días y las horas desde el último mantenimiento con la frecuencia definida.
3. Si se cumple la frecuencia, el sistema muestra la alerta al operador.

**Dependencias:** RF15, RF08 · **Referencias cruzadas:** RF15 · **Prioridad:** Media · **Estado:** Por validar

**Comentarios:** Frecuencia propuesta, por validar con el cliente.

### RF17 — Generar reportes

**Descripción.** El sistema debe permitir al administrador generar un reporte por dispositivo en un rango de fechas con el número de servicios realizados, las horas de uso y las incidencias registradas.

**Proceso**

1. El administrador elige el dispositivo y el rango de fechas.
2. El sistema consulta la bitácora de ese periodo.
3. El sistema muestra el reporte con servicios, horas de uso e incidencias.

**Dependencias:** RF08 · **Referencias cruzadas:** N/A · **Prioridad:** Media · **Estado:** Por validar

### RF18 — Registrar usuario

**Descripción.** El sistema debe permitir al administrador registrar un usuario nuevo ingresando nombre, correo institucional, contraseña y rol (administrador u operador).

**Proceso**

1. El administrador abre el módulo de usuarios y elige registrar un usuario.
2. El administrador ingresa nombre, correo, contraseña y rol.
3. El sistema valida que el correo no esté registrado.
4. El sistema guarda el usuario con estado Activo y la contraseña cifrada.

**Dependencias:** N/A · **Referencias cruzadas:** RNF01, RNF05 · **Prioridad:** Alta · **Estado:** Por validar

### RF19 — Desactivar usuario

**Descripción.** El sistema debe permitir al administrador desactivar un usuario registrado y, desde ese momento, debe impedir que ese usuario inicie sesión.

**Proceso**

1. El administrador selecciona el usuario.
2. El administrador elige desactivarlo y confirma.
3. El sistema cambia el estado del usuario a Inactivo.

**Dependencias:** RF18 · **Referencias cruzadas:** RF20, RNF01 · **Prioridad:** Media · **Estado:** Por validar

### RF20 — Iniciar sesión

**Descripción.** Cuando un usuario activo ingrese su correo institucional y su contraseña correctos, el sistema debe permitirle iniciar sesión y mostrar solo las funciones de su rol; si los datos son incorrectos, el sistema debe mostrar un mensaje de error.

**Proceso**

1. El usuario ingresa su correo y contraseña.
2. El sistema valida que el usuario exista, esté activo y la contraseña sea correcta.
3. Si los datos son correctos, el sistema muestra el menú según su rol.
4. Si no, el sistema muestra un mensaje de error.

**Dependencias:** RF18 · **Referencias cruzadas:** RNF05 · **Prioridad:** Alta · **Estado:** Por validar

### RF21 — Cancelar o reprogramar reserva

**Descripción.** Cuando una reserva no haya iniciado, el sistema debe permitir al administrador cancelarla o reprogramarla indicando el motivo, y debe liberar el horario del dispositivo asignado.

**Proceso**

1. El administrador selecciona una reserva que no ha iniciado.
2. El administrador elige cancelar o reprogramar e ingresa el motivo.
3. Si reprograma, el administrador ingresa la nueva fecha y hora, y el sistema valida RF06 y RF07.
4. El sistema guarda el cambio con el motivo y libera el horario anterior del dispositivo.

**Dependencias:** RF05 · **Referencias cruzadas:** RF06, RF07 · **Prioridad:** Media · **Estado:** Por validar

### RF22 — Sugerir dispositivo

**Descripción.** Cuando el administrador cree una reserva, el sistema debe ser capaz de sugerir el dispositivo disponible del tipo requerido que tenga mayor nivel de batería y cumpla RF06 y RF07, y debe permitir al administrador aceptarlo o elegir otro.

**Proceso**

1. El administrador ingresa los datos de la reserva.
2. El sistema consulta los dispositivos disponibles del tipo requerido y su nivel de batería.
3. El sistema descarta los que no cumplen RF06 y RF07 y sugiere el de mayor batería.
4. El administrador acepta la sugerencia o elige otro dispositivo.

**Dependencias:** RF04, RF05, RF09 · **Referencias cruzadas:** RF06, RF07, RNF07 · **Prioridad:** Alta · **Estado:** Por validar

**Comentarios:** Busca reducir el tiempo de asignación cuando llegan varias solicitudes al mismo tiempo.

### RF23 — Validar clima para drones

**Descripción.** Cuando el administrador asigne un drone a una grabación de evento, el sistema debe consultar la API de clima para la fecha y hora de la reserva. Debe rechazar la asignación si el pronóstico indica viento mayor a 30 km/h o probabilidad de lluvia mayor al 60%, mostrando el motivo.

**Proceso**

1. El administrador asigna un drone a una reserva de grabación.
2. El sistema consulta la API de clima para la fecha, hora y lugar del evento.
3. Si el viento supera 30 km/h o la probabilidad de lluvia supera el 60%, el sistema rechaza la asignación y muestra el motivo.
4. Si el pronóstico está dentro de los umbrales, el sistema confirma la asignación.

**Dependencias:** RF05 · **Referencias cruzadas:** RF06, RF07 · **Prioridad:** Alta · **Estado:** Por validar

### RF24 — Confirmar entrega con código

**Descripción.** Cuando un robot llegue al punto de destino, el sistema debe ser capaz de recibir desde la API del dispositivo el código de 4 dígitos que ingresa quien recibe. Si coincide con el código generado al crear la reserva, debe cambiar el estado del servicio a Entregado y registrar la hora de entrega en la bitácora.

**Proceso**

1. Al crear la reserva de un robot, el sistema genera un código de 4 dígitos.
2. Al llegar al destino, quien recibe ingresa el código en el robot.
3. El sistema recibe el código desde la API del dispositivo y lo compara con el de la reserva.
4. Si coincide, el sistema cambia el estado a Entregado y registra la hora. Si no coincide, registra una incidencia de entrega.

**Dependencias:** RF05, RF08 · **Referencias cruzadas:** RF08, RESTR01 · **Prioridad:** Media · **Estado:** Por validar

### RF25 — Alertar salida de zona de operación

**Descripción.** Cuando un dispositivo en servicio salga de la zona de operación definida para el campus, el sistema debe mostrar una alerta en el panel de monitoreo con el dispositivo y su ubicación, y debe registrar el evento como incidencia en la bitácora.

**Proceso**

1. El sistema recibe la ubicación actualizada del dispositivo.
2. El sistema compara la ubicación con los límites de la zona de operación.
3. Si el dispositivo está fuera de la zona, el sistema muestra la alerta con el dispositivo y su ubicación.
4. El sistema registra el evento como incidencia en la bitácora.

**Dependencias:** RF09 · **Referencias cruzadas:** RF10, RF11, RF14, RF27 · **Prioridad:** Alta · **Estado:** Por validar

**Comentarios:** La alerta también la atiende el operador (RF27).

### RF26 — Eliminar videos vencidos

**Descripción.** Cuando un video cumpla 3 meses desde su grabación, el sistema debe eliminarlo del servicio cloud y debe registrar la fecha de eliminación en la bitácora del servicio.

**Proceso**

1. El sistema revisa una vez al día la fecha de grabación de los videos.
2. El sistema identifica los videos con más de 3 meses.
3. El sistema los elimina del servicio cloud.
4. El sistema registra la fecha de eliminación en la bitácora del servicio.

**Dependencias:** RF12 · **Referencias cruzadas:** RNF04, RNF08, RESTR04 · **Prioridad:** Media · **Estado:** Por validar

### RF27 — Atender alerta de servicio

**Descripción.** Cuando el sistema muestre una alerta de servicio, el sistema debe permitir al operador registrar su atención indicando la causa revisada y las observaciones, y debe guardar la atención asociada a la alerta.

**Proceso**

1. El operador ve la alerta en el panel de monitoreo.
2. El operador revisa la causa e ingresa las observaciones.
3. El sistema guarda la atención asociada a la alerta y la muestra al administrador.

**Dependencias:** RF11 · **Referencias cruzadas:** RF11, RF14, RF25 · **Prioridad:** Media · **Estado:** Por validar

---

## Requisitos no funcionales

| ID | Requisito | Tipo | Stakeholder |
|---|---|---|---|
| RNF01 | El sistema debe permitir solo a los usuarios con rol administrador crear usuarios, cambiar permisos y dar de baja dispositivos. | Seguridad | Administradores |
| RNF02 | Mientras los 6 dispositivos estén en servicio al mismo tiempo, el sistema debe actualizar el panel de monitoreo de cada uno con un intervalo máximo de 5 segundos. | Rendimiento | Administradores |
| RNF03 | Cuando el administrador abra las pantallas de inventario, reservas o bitácora, el sistema debe mostrarlas en un tiempo máximo de 3 segundos. | Rendimiento | Administradores |
| RNF04 | El sistema debe conservar cada video durante 3 meses desde su grabación, según lo indicado por el cliente. | Operacional | Grupo que elabora el robot, directivos |
| RNF05 | El sistema debe almacenar cifradas las contraseñas de los usuarios y debe transmitir la información entre el navegador y el servidor mediante HTTPS. | Seguridad | Grupo que elabora el robot |
| RNF06 | El sistema debe estar disponible el 95 % del tiempo entre las 6:00 y las 18:00 de lunes a sábado. | Confiabilidad | Administradores, directivos |
| RNF07 | El sistema debe permitir a un administrador sin capacitación previa crear una reserva en un tiempo máximo de 2 minutos. | Usabilidad | Administradores |
| RNF08 | El sistema debe almacenar los videos y permitir su consulta cumpliendo la Ley 1581 de 2012 de protección de datos personales. | Legal | Directivos, organizadores de eventos |
| RNF09 | El sistema debe registrar en un historial de auditoría cada creación, edición o baja que realice un usuario, con la fecha, la hora y el usuario responsable. | Seguridad | Administradores, directivos |
| RNF10 | El sistema debe permitir registrar hasta 20 dispositivos sin requerir cambios en su código. | Escalabilidad | Directivos, grupo que elabora el robot |

## Restricciones técnicas

| ID | Restricción |
|---|---|
| RESTR01 | El sistema debe ser capaz de recibir la telemetría, la ubicación, el estado de los sensores y el video desde un simulador o desde datos precargados, sin conexión a dispositivos reales. |
| RESTR02 | El sistema debe desarrollarse como una aplicación web. |
| RESTR03 | El sistema debe funcionar en las dos últimas versiones de los navegadores Chrome, Firefox y Edge. |
| RESTR04 | El sistema debe almacenar los videos en Firebase Storage o AWS S3, usando la capa gratuita o educativa del proveedor. |

Todos los requisitos están en estado **Por validar** con el cliente.
