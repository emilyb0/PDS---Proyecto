import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/servicios';
import { Cargando, ErrorApiVista, LIMITE, Pagina, Paginacion, Vacio, useCarga } from '../componentes/ui';
import { fechaHora, TEXTOS } from '../utils/formato';

const ENTIDADES = ['usuario', 'dispositivo', 'reserva'];

function enlaceEntidad(entidad: string, id: number) {
  if (entidad === 'dispositivo') return `/inventario/${id}`;
  if (entidad === 'reserva') return `/reservas/${id}`;
  return null;
}

export function Auditoria() {
  const [f, setF] = useState({ id_usuario: '', entidad: '', accion: '', desde: '', hasta: '' });
  const [desp, setDesp] = useState(0);
  const lista = useCarga(() => api.auditoria({ ...f, limite: LIMITE, desplazamiento: desp }), [f, desp]);
  const usuarios = useCarga(() => api.usuarios({ limite: 200 }), []);
  const fijar = (k: keyof typeof f, v: string) => {
    setF((x) => ({ ...x, [k]: v }));
    setDesp(0);
  };

  return (
    <Pagina codigo="RNF09 · Auditoría" titulo="Historial de auditoría" subtitulo="Cada creación, edición o baja, con la fecha, la hora y el usuario responsable.">
      <div className="filtros">
        <label className="filtro">
          <span>Usuario</span>
          <select value={f.id_usuario} onChange={(e) => fijar('id_usuario', e.target.value)}>
            <option value="">Todos</option>
            {usuarios.datos?.items.map((u) => (
              <option key={u.id_usuario} value={u.id_usuario}>
                {u.nombre}
              </option>
            ))}
          </select>
        </label>
        <label className="filtro">
          <span>Entidad</span>
          <select value={f.entidad} onChange={(e) => fijar('entidad', e.target.value)}>
            <option value="">Todas</option>
            {ENTIDADES.map((x) => (
              <option key={x} value={x}>
                {x[0].toUpperCase() + x.slice(1)}
              </option>
            ))}
          </select>
        </label>
        <label className="filtro">
          <span>Acción</span>
          <select value={f.accion} onChange={(e) => fijar('accion', e.target.value)}>
            <option value="">Todas</option>
            {Object.entries(TEXTOS.accion).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
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
      </div>
      <ErrorApiVista error={lista.error} />
      <div className="tabla-marco">
        {lista.cargando && !lista.datos ? (
          <Cargando />
        ) : lista.datos?.items.length === 0 ? (
          <Vacio>Sin registros con estos filtros.</Vacio>
        ) : (
          <table className="tabla">
            <thead>
              <tr>
                <th>#</th>
                <th>Fecha y hora</th>
                <th>Acción</th>
                <th>Entidad</th>
                <th>Registro</th>
                <th>Usuario responsable</th>
              </tr>
            </thead>
            <tbody>
              {lista.datos?.items.map((r) => {
                const a = enlaceEntidad(r.entidad, r.id_entidad);
                return (
                  <tr key={r.id_auditoria}>
                    <td className="mono">{r.id_auditoria}</td>
                    <td className="mono">{fechaHora(r.fecha_hora, true)}</td>
                    <td>
                      <span className={`accion accion--${r.accion.toLowerCase()}`}>{TEXTOS.accion[r.accion] ?? r.accion}</span>
                    </td>
                    <td>{r.entidad}</td>
                    <td className="mono">
                      {a ? <Link to={a}>#{r.id_entidad}</Link> : `#${r.id_entidad}`}
                    </td>
                    <td>{r.usuario.nombre}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      {lista.datos && <Paginacion total={lista.datos.total} limite={lista.datos.limite} desplazamiento={desp} onCambio={setDesp} />}
    </Pagina>
  );
}
