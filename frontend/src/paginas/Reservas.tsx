import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api/servicios';
import type { EstadoReserva } from '../api/tipos';
import {
  Cargando,
  ErrorApiVista,
  Estado,
  LIMITE,
  Pagina,
  Paginacion,
  Serie,
  Vacio,
  useCarga,
} from '../componentes/ui';
import { useSesion } from '../sesion/SesionContext';
import { fecha, hoyBogota, TEXTOS, texto } from '../utils/formato';

const ESTADOS = Object.keys(TEXTOS.estadoReserva) as EstadoReserva[];

export function Reservas() {
  const { puede, sesion } = useSesion();
  const esAdmin = sesion?.usuario.rol === 'ADMINISTRADOR';
  const navegar = useNavigate();
  const [params, setParams] = useSearchParams();
  const [desp, setDesp] = useState(0);
  const f = {
    fecha: params.get('fecha') ?? '',
    estado: params.get('estado') ?? '',
    id_dispositivo: params.get('id_dispositivo') ?? '',
  };

  const fijar = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v);
    else p.delete(k);
    setParams(p, { replace: true });
    setDesp(0);
  };

  const lista = useCarga(() => api.reservas({ ...f, limite: LIMITE, desplazamiento: desp }), [f.fecha, f.estado, f.id_dispositivo, desp]);
  const dispositivos = useCarga(() => api.dispositivos({ limite: 200 }), []);

  return (
    <Pagina
      codigo="RF05 · Reservas"
      titulo="Reservas"
      subtitulo="Ordenadas por hora de inicio."
      acciones={
        puede('reservaNueva') && (
          <Link className="boton boton--primario" to="/reservas/nueva">
            + Nueva reserva
          </Link>
        )
      }
    >
      <div className="filtros">
        <div className="segmentos">
          <button className={f.fecha === hoyBogota() ? 'activo' : ''} onClick={() => fijar('fecha', f.fecha === hoyBogota() ? '' : hoyBogota())}>
            Hoy
          </button>
          <button className={f.fecha === hoyBogota(1) ? 'activo' : ''} onClick={() => fijar('fecha', f.fecha === hoyBogota(1) ? '' : hoyBogota(1))}>
            Mañana
          </button>
        </div>
        <label className="filtro">
          <span>Fecha</span>
          <input type="date" value={f.fecha} onChange={(e) => fijar('fecha', e.target.value)} />
        </label>
        <label className="filtro">
          <span>Estado</span>
          <select value={f.estado} onChange={(e) => fijar('estado', e.target.value)}>
            <option value="">Todos</option>
            {ESTADOS.map((e) => (
              <option key={e} value={e}>
                {TEXTOS.estadoReserva[e]}
              </option>
            ))}
          </select>
        </label>
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
        {(f.fecha || f.estado || f.id_dispositivo) && (
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
          <Vacio>No hay reservas con estos filtros.</Vacio>
        ) : (
          <table className="tabla tabla--clic">
            <thead>
              <tr>
                <th>#</th>
                <th>Fecha</th>
                <th>Horario</th>
                <th>Servicio</th>
                <th>Dispositivo</th>
                <th>Origen → destino</th>
                <th>Operador</th>
                <th>Estado</th>
                {esAdmin && <th>Código</th>}
                <th>Bitácora</th>
              </tr>
            </thead>
            <tbody>
              {lista.datos?.items.map((r) => (
                <tr
                  key={r.id_reserva}
                  onClick={() => navegar(`/reservas/${r.id_reserva}`)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && navegar(`/reservas/${r.id_reserva}`)}
                  className={r.estado === 'EN_CURSO' ? 'fila-activa' : r.estado === 'CANCELADA' ? 'fila-tenue' : ''}
                >
                  <td className="mono">{r.id_reserva}</td>
                  <td className="mono">{fecha(r.fecha)}</td>
                  <td className="mono">
                    {r.hora_inicio}–{r.hora_fin}
                  </td>
                  <td>{texto('tipoServicio', r.tipo_servicio)}</td>
                  <td>
                    <Serie id={r.dispositivo.id_dispositivo} serie={r.dispositivo.numero_serie} tipo={r.dispositivo.tipo} />
                  </td>
                  <td>
                    {r.origen.nombre} <span className="tenue">→</span> {r.destino.nombre}
                  </td>
                  <td>{r.operador.nombre}</td>
                  <td>
                    <Estado grupo="estadoReserva" valor={r.estado} />
                  </td>
                  {esAdmin && <td className="mono">{r.codigo_entrega ?? '—'}</td>}
                  <td>
                    {r.id_bitacora ? (
                      <Link to={`/bitacoras/${r.id_bitacora}`} className="mono" onClick={(e) => e.stopPropagation()}>
                        #{r.id_bitacora}
                      </Link>
                    ) : (
                      <span className="tenue">—</span>
                    )}
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
