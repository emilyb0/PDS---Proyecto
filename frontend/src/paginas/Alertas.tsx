import { useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api/servicios';
import { Cargando, Causa, Dato, ErrorApiVista, LIMITE, Pagina, Paginacion, Panel, Serie, Vacio, useCarga } from '../componentes/ui';
import { MapaPunto } from '../mapa/MapaPunto';
import { useSesion } from '../sesion/SesionContext';
import { useMonitoreo } from '../tiempoReal/MonitoreoContext';
import { coordenada, fechaHora, texto } from '../utils/formato';

export function Alertas() {
  const navegar = useNavigate();
  const { sesion } = useSesion();
  const { alertas: vivas } = useMonitoreo();
  const [params, setParams] = useSearchParams();
  const [desp, setDesp] = useState(0);
  const f = {
    id_dispositivo: params.get('id_dispositivo') ?? '',
    desde: params.get('desde') ?? '',
    hasta: params.get('hasta') ?? '',
  };
  const fijar = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v);
    else p.delete(k);
    setParams(p, { replace: true });
    setDesp(0);
  };
  // Se recarga sola cuando llega una alerta nueva por el tiempo real.
  const lista = useCarga(
    () => api.alertas({ tipo: 'SERVICIO', ...f, limite: LIMITE, desplazamiento: desp }),
    [f.id_dispositivo, f.desde, f.hasta, desp, vivas.length],
  );
  const dispositivos = useCarga(() => api.dispositivos({ limite: 200 }), []);
  const mias = sesion?.usuario.rol === 'OPERADOR' ? sesion.usuario.id_usuario : null;

  return (
    <Pagina codigo="RF11 · Alertas" titulo="Alertas de servicio" subtitulo="Batería baja (< 20 %), sensor en falla y retraso sobre el fin estimado. De la más reciente a la más antigua.">
      <div className="filtros">
        <label className="filtro">
          <span>Dispositivo</span>
          <select value={f.id_dispositivo} onChange={(e) => fijar('id_dispositivo', e.target.value)}>
            <option value="">Todos</option>
            {dispositivos.datos?.items.map((d) => (
              <option key={d.id_dispositivo} value={d.id_dispositivo}>
                {d.numero_serie} · {d.modelo}
              </option>
            ))}
          </select>
        </label>
        <label className="filtro">
          <span>Desde</span>
          <input type="date" value={f.desde} onChange={(e) => fijar('desde', e.target.value)} />
        </label>
        <label className="filtro">
          <span>Hasta</span>
          <input type="date" value={f.hasta} onChange={(e) => fijar('hasta', e.target.value)} />
        </label>
        {(f.id_dispositivo || f.desde || f.hasta) && (
          <button className="boton boton--fantasma" onClick={() => setParams({}, { replace: true })}>
            Limpiar filtros
          </button>
        )}
      </div>
      <ErrorApiVista error={lista.error} />
      <div className="tabla-marco">
        {lista.cargando && !lista.datos ? (
          <Cargando />
        ) : lista.datos?.items.length === 0 ? (
          <Vacio>No hay alertas con estos filtros.</Vacio>
        ) : (
          <table className="tabla tabla--clic">
            <thead>
              <tr>
                <th>#</th>
                <th>Fecha y hora</th>
                <th>Causa</th>
                <th>Dispositivo</th>
                <th>Descripción</th>
                <th>Bitácora</th>
                <th>Ubicación</th>
              </tr>
            </thead>
            <tbody>
              {lista.datos?.items.map((a) => (
                <tr
                  key={a.id_alerta}
                  onClick={() => navegar(`/alertas/${a.id_alerta}`)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && navegar(`/alertas/${a.id_alerta}`)}
                  className={mias != null && a.id_operador === mias ? 'fila-mia' : ''}
                >
                  <td className="mono">{a.id_alerta}</td>
                  <td className="mono">{fechaHora(a.fecha_hora, true)}</td>
                  <td>
                    <Causa valor={a.causa} />
                  </td>
                  <td>
                    <Serie id={a.id_dispositivo} serie={a.numero_serie} />
                  </td>
                  <td>{a.descripcion}</td>
                  <td>
                    {a.id_bitacora ? (
                      <Link to={`/bitacoras/${a.id_bitacora}`} className="mono" onClick={(e) => e.stopPropagation()}>
                        #{a.id_bitacora}
                      </Link>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="mono tenue">
                    {coordenada(a.latitud)}, {coordenada(a.longitud)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {lista.datos && <Paginacion total={lista.datos.total} limite={lista.datos.limite} desplazamiento={desp} onCambio={setDesp} />}
    </Pagina>
  );
}

export function AlertaDetalle() {
  const { id } = useParams();
  const { ubicaciones } = useMonitoreo();
  const { puede } = useSesion();
  const a = useCarga(() => api.alerta(id!), [id]);

  if (a.cargando && !a.datos) return <Cargando />;
  if (a.error)
    return (
      <Pagina codigo="RF11" titulo="Alerta">
        <ErrorApiVista error={a.error} />
      </Pagina>
    );
  const x = a.datos!;

  return (
    <Pagina
      codigo={`RF11 · Alerta #${x.id_alerta}`}
      titulo={x.descripcion}
      subtitulo={
        <span className="fila-gap">
          <Causa valor={x.causa} />
          <span className="mono">{fechaHora(x.fecha_hora, true)}</span>
        </span>
      }
      acciones={
        <>
          {puede('monitoreo') && (
            <Link className="boton" to={`/monitoreo?d=${x.id_dispositivo}`}>
              Ver en el mapa
            </Link>
          )}
          <Link className="boton boton--fantasma" to="/alertas">
            ← Alertas
          </Link>
        </>
      }
    >
      <div className="rejilla-2 rejilla-2--mapa">
        <Panel codigo="01" titulo="Lugar de la alerta" cuerpo={false}>
          {x.latitud != null && x.longitud != null ? (
            <MapaPunto latitud={x.latitud} longitud={x.longitud} ubicaciones={ubicaciones} />
          ) : (
            <Vacio>La alerta no trae ubicación.</Vacio>
          )}
        </Panel>
        <Panel codigo="02" titulo="Datos">
          <dl className="datos">
            <Dato etiqueta="Tipo">{texto('tipoAlerta', x.tipo)}</Dato>
            <Dato etiqueta="Causa">{texto('causaAlerta', x.causa)}</Dato>
            <Dato etiqueta="Dispositivo">
              <Serie id={x.id_dispositivo} serie={x.numero_serie} />
            </Dato>
            <Dato etiqueta="Bitácora">
              {x.id_bitacora ? (
                <Link to={`/bitacoras/${x.id_bitacora}`} className="mono">
                  #{x.id_bitacora}
                </Link>
              ) : (
                '—'
              )}
            </Dato>
            <Dato etiqueta="Incidencia" mono>
              {x.id_incidencia ? `#${x.id_incidencia}` : '—'}
            </Dato>
            <Dato etiqueta="Ubicación" mono>
              {coordenada(x.latitud)}, {coordenada(x.longitud)}
            </Dato>
            <Dato etiqueta="Fecha y hora" mono>
              {fechaHora(x.fecha_hora, true)}
            </Dato>
          </dl>
        </Panel>
      </div>
    </Pagina>
  );
}
