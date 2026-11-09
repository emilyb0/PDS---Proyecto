import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api/servicios';
import type { EstadoBitacora } from '../api/tipos';
import { Cargando, ErrorApiVista, Estado, LIMITE, Pagina, Paginacion, Serie, Vacio, useCarga } from '../componentes/ui';
import { duracion, fechaHora, hora, minutosEntre, TEXTOS, texto } from '../utils/formato';

// En la entrega 1 la bitácora pasa por EN_CURSO → RETORNANDO → FINALIZADO (ENTREGADO llega con RF24).
const ESTADOS: EstadoBitacora[] = ['EN_CURSO', 'RETORNANDO', 'FINALIZADO'];

export function Bitacoras() {
  const navegar = useNavigate();
  const [params, setParams] = useSearchParams();
  const [desp, setDesp] = useState(0);
  const f = {
    desde: params.get('desde') ?? '',
    hasta: params.get('hasta') ?? '',
    id_dispositivo: params.get('id_dispositivo') ?? '',
    estado: params.get('estado') ?? '',
  };
  const fijar = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v);
    else p.delete(k);
    setParams(p, { replace: true });
    setDesp(0);
  };

  const lista = useCarga(() => api.bitacoras({ ...f, limite: LIMITE, desplazamiento: desp }), [f.desde, f.hasta, f.id_dispositivo, f.estado, desp]);
  const dispositivos = useCarga(() => api.dispositivos({ limite: 200 }), []);

  return (
    <Pagina codigo="RF08 · RF12 · Bitácoras" titulo="Bitácoras de servicio" subtitulo="De la más reciente a la más antigua. Cada servicio guarda su ruta, sus incidencias y su video.">
      <div className="filtros">
        <label className="filtro">
          <span>Desde</span>
          <input type="date" value={f.desde} onChange={(e) => fijar('desde', e.target.value)} />
        </label>
        <label className="filtro">
          <span>Hasta</span>
          <input type="date" value={f.hasta} onChange={(e) => fijar('hasta', e.target.value)} />
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
        <label className="filtro">
          <span>Estado</span>
          <select value={f.estado} onChange={(e) => fijar('estado', e.target.value)}>
            <option value="">Todos</option>
            {ESTADOS.map((e) => (
              <option key={e} value={e}>
                {TEXTOS.estadoBitacora[e]}
              </option>
            ))}
          </select>
        </label>
        {(f.desde || f.hasta || f.id_dispositivo || f.estado) && (
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
          <Vacio>No hay bitácoras con estos filtros.</Vacio>
        ) : (
          <table className="tabla tabla--clic">
            <thead>
              <tr>
                <th>#</th>
                <th>Dispositivo</th>
                <th>Servicio</th>
                <th>Salida</th>
                <th>Regreso</th>
                <th className="num">Duración</th>
                <th>Operador</th>
                <th className="num">Incidencias</th>
                <th>Video</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {lista.datos?.items.map((b) => (
                <tr
                  key={b.id_bitacora}
                  onClick={() => navegar(`/bitacoras/${b.id_bitacora}`)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && navegar(`/bitacoras/${b.id_bitacora}`)}
                  className={b.estado !== 'FINALIZADO' ? 'fila-activa' : ''}
                >
                  <td className="mono">{b.id_bitacora}</td>
                  <td>
                    <Serie id={b.dispositivo.id_dispositivo} serie={b.dispositivo.numero_serie} tipo={b.dispositivo.tipo} />
                  </td>
                  <td>{texto('tipoServicio', b.tipo_servicio)}</td>
                  <td className="mono">{fechaHora(b.hora_salida)}</td>
                  <td className="mono">{b.hora_regreso ? hora(b.hora_regreso, false) : '—'}</td>
                  <td className="num mono">{b.hora_regreso ? duracion(minutosEntre(b.hora_salida, b.hora_regreso)) : '—'}</td>
                  <td>{b.operador.nombre}</td>
                  <td className={`num mono ${b.numero_incidencias > 0 ? 'texto-acento' : 'tenue'}`}>{b.numero_incidencias}</td>
                  <td>{b.tiene_video ? <span className="mono">MP4</span> : <span className="tenue">—</span>}</td>
                  <td>
                    <Estado grupo="estadoBitacora" valor={b.estado} />
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
