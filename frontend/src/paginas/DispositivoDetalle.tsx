import { Link, useParams } from 'react-router-dom';
import { api } from '../api/servicios';
import {
  Advertencias,
  Bateria,
  Cargando,
  Dato,
  ErrorApiVista,
  Estado,
  Glifo,
  Pagina,
  Panel,
  Vacio,
  useCarga,
} from '../componentes/ui';
import { MapaPunto } from '../mapa/MapaPunto';
import { useSesion } from '../sesion/SesionContext';
import { useMonitoreo } from '../tiempoReal/MonitoreoContext';
import { coordenada, fecha, fechaHora, numero, texto } from '../utils/formato';

export function DispositivoDetalle() {
  const { id } = useParams();
  const { puede } = useSesion();
  const { ubicaciones } = useMonitoreo();
  const det = useCarga(() => api.dispositivo(id!), [id]);
  const reservas = useCarga(
    () => (puede('reservas') ? api.reservas({ id_dispositivo: id, estado: 'PROGRAMADA', limite: 6 }) : Promise.resolve(null)),
    [id],
  );
  const bitacoras = useCarga(
    () => (puede('bitacoras') ? api.bitacoras({ id_dispositivo: id, limite: 6 }) : Promise.resolve(null)),
    [id],
  );

  if (det.cargando && !det.datos) return <Cargando />;
  if (det.error)
    return (
      <Pagina codigo="RF04" titulo="Dispositivo">
        <ErrorApiVista error={det.error} />
      </Pagina>
    );
  const d = det.datos!;
  const t = d.ultima_telemetria;

  return (
    <Pagina
      codigo={`RF04 · Dispositivo #${d.id_dispositivo}`}
      titulo={`${d.numero_serie} · ${d.modelo}`}
      subtitulo={
        <span className="fila-gap">
          <Glifo tipo={d.tipo} /> {texto('tipoDispositivo', d.tipo)} <Estado grupo="estadoDispositivo" valor={d.estado} />
          {d.dado_de_baja && <span className="texto-acento">Dado de baja {fecha(d.fecha_baja)}</span>}
        </span>
      }
      acciones={
        <>
          {puede('monitoreo') && (
            <Link className="boton" to={`/monitoreo?d=${d.id_dispositivo}`}>
              Ver en el mapa
            </Link>
          )}
          <Link className="boton boton--fantasma" to="/inventario">
            ← Inventario
          </Link>
        </>
      }
    >
      <Advertencias lista={d.advertencias} />
      <div className="rejilla-3">
        <Panel codigo="01" titulo="Ficha técnica">
          <dl className="datos">
            <Dato etiqueta="Número de serie" mono>
              {d.numero_serie}
            </Dato>
            <Dato etiqueta="Modelo">{d.modelo}</Dato>
            <Dato etiqueta={d.tipo === 'ROBOT' ? 'Capacidad de carga' : 'Autonomía de vuelo'} mono>
              {d.tipo === 'ROBOT' ? `${numero(d.capacidad_carga_kg, 1)} kg` : `${numero(d.autonomia_vuelo_min)} min`}
            </Dato>
            <Dato etiqueta="Horas desde mantenimiento" mono>
              {numero(d.horas_uso_desde_mant, 2)} h
            </Dato>
            <Dato etiqueta="Fecha de registro" mono>
              {fecha(d.fecha_registro)}
            </Dato>
            {d.dado_de_baja && <Dato etiqueta="Motivo de baja">{d.motivo_baja ?? '—'}</Dato>}
          </dl>
        </Panel>

        <Panel codigo="02" titulo="Energía y sensores">
          <div className="bateria-grande">
            <Bateria nivel={d.nivel_bateria} />
            <span className="tenue">{(d.nivel_bateria ?? 0) < 30 ? 'Por debajo del mínimo para asignar (30 %)' : 'Apta para asignar'}</span>
          </div>
          <ul className="lista-sensores">
            {d.sensores.map((s) => (
              <li key={s.id_sensor} className={s.estado === 'FALLA' ? 'sensor--falla' : ''}>
                <i />
                <span>{s.nombre}</span>
                <span className="mono">{texto('estadoSensor', s.estado)}</span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel codigo="03" titulo="Última lectura" cuerpo={false}>
          {t ? (
            <>
              <MapaPunto latitud={t.latitud} longitud={t.longitud} tipo={d.tipo} etiqueta={d.numero_serie} clases={d.servicio_activo ? 'm-servicio' : ''} ubicaciones={ubicaciones} />
              <dl className="datos datos--compactos panel-cuerpo">
                <Dato etiqueta="Fase">{texto('faseServicio', t.estado_servicio)}</Dato>
                <Dato etiqueta="Hora" mono>
                  {fechaHora(t.fecha_hora, true)}
                </Dato>
                <Dato etiqueta="Posición" mono>
                  {coordenada(t.latitud)}, {coordenada(t.longitud)}
                </Dato>
              </dl>
            </>
          ) : (
            <Vacio>Sin lecturas todavía.</Vacio>
          )}
        </Panel>
      </div>

      <div className="rejilla-2">
        <Panel
          codigo="04"
          titulo="Servicio y próximas reservas"
          acciones={
            puede('reservas') && (
              <Link to={`/reservas?id_dispositivo=${d.id_dispositivo}`} className="mono">
                Todas →
              </Link>
            )
          }
        >
          {d.servicio_activo && (
            <div className="servicio-activo">
              <span className="estado estado--en_servicio">En servicio</span>
              <Link to={`/bitacoras/${d.servicio_activo.id_bitacora}`}>Bitácora #{d.servicio_activo.id_bitacora}</Link>
              <Link to={`/reservas/${d.servicio_activo.id_reserva}`}>Reserva #{d.servicio_activo.id_reserva}</Link>
              <Estado grupo="estadoBitacora" valor={d.servicio_activo.estado} />
            </div>
          )}
          {reservas.datos?.items.length ? (
            <table className="tabla tabla--compacta">
              <tbody>
                {reservas.datos.items.map((r) => (
                  <tr key={r.id_reserva}>
                    <td>
                      <Link to={`/reservas/${r.id_reserva}`} className="mono">
                        #{r.id_reserva}
                      </Link>
                    </td>
                    <td className="mono">
                      {fecha(r.fecha)} {r.hora_inicio}–{r.hora_fin}
                    </td>
                    <td>{texto('tipoServicio', r.tipo_servicio)}</td>
                    <td>{r.operador.nombre}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            !d.servicio_activo && <Vacio>Sin reservas programadas.</Vacio>
          )}
        </Panel>
        <Panel
          codigo="05"
          titulo="Últimos servicios"
          acciones={
            puede('bitacoras') && (
              <Link to={`/bitacoras?id_dispositivo=${d.id_dispositivo}`} className="mono">
                Todas →
              </Link>
            )
          }
        >
          {bitacoras.datos?.items.length ? (
            <table className="tabla tabla--compacta">
              <tbody>
                {bitacoras.datos.items.map((b) => (
                  <tr key={b.id_bitacora}>
                    <td>
                      <Link to={`/bitacoras/${b.id_bitacora}`} className="mono">
                        #{b.id_bitacora}
                      </Link>
                    </td>
                    <td className="mono">{fechaHora(b.hora_salida)}</td>
                    <td>{texto('tipoServicio', b.tipo_servicio)}</td>
                    <td>
                      <Estado grupo="estadoBitacora" valor={b.estado} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <Vacio>Sin servicios registrados.</Vacio>
          )}
        </Panel>
      </div>
    </Pagina>
  );
}
