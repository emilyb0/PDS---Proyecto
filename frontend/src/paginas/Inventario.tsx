import { useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api/servicios';
import type { EstadoDispositivo, TipoDispositivo } from '../api/tipos';
import {
  Bateria,
  Cargando,
  ErrorApiVista,
  Estado,
  Glifo,
  LIMITE,
  Pagina,
  Paginacion,
  Segmentos,
  Vacio,
  useCarga,
} from '../componentes/ui';
import { useSesion } from '../sesion/SesionContext';
import { fecha, numero, TEXTOS } from '../utils/formato';

const ESTADOS = Object.keys(TEXTOS.estadoDispositivo) as EstadoDispositivo[];

export function Inventario() {
  const { puede } = useSesion();
  const navegar = useNavigate();
  const [params, setParams] = useSearchParams();
  const tipo = (params.get('tipo') ?? '') as TipoDispositivo | '';
  const estado = (params.get('estado') ?? '') as EstadoDispositivo | '';
  const [desp, setDesp] = useState(0);

  const fijar = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v);
    else p.delete(k);
    setParams(p, { replace: true });
    setDesp(0);
  };

  const lista = useCarga(() => api.dispositivos({ tipo, estado, limite: LIMITE, desplazamiento: desp }), [tipo, estado, desp]);
  // Resumen de la flota completa, sin filtros (RF04: estado actual de todos).
  const todos = useCarga(() => api.dispositivos({ limite: 200 }), []);

  const resumen = useMemo(() => {
    const c: Record<string, number> = {};
    for (const d of todos.datos?.items ?? []) c[d.estado] = (c[d.estado] ?? 0) + 1;
    return c;
  }, [todos.datos]);

  return (
    <Pagina
      codigo="RF04 · Inventario"
      titulo="Inventario de dispositivos"
      subtitulo="Robots de transporte y drones de grabación, con su estado actual."
      acciones={
        puede('dispositivoNuevo') && (
          <Link className="boton boton--primario" to="/inventario/nuevo">
            + Registrar dispositivo
          </Link>
        )
      }
    >
      <div className="tira-resumen">
        <button className={`tira-item ${!estado ? 'activo' : ''}`} onClick={() => fijar('estado', '')}>
          <span className="tira-valor">{todos.datos?.total ?? '—'}</span>
          <span className="tira-etiqueta">Todos</span>
        </button>
        {ESTADOS.map((e) => (
          <button key={e} className={`tira-item ${estado === e ? 'activo' : ''}`} onClick={() => fijar('estado', estado === e ? '' : e)}>
            <span className="tira-valor">{resumen[e] ?? 0}</span>
            <span className="tira-etiqueta">
              <Estado grupo="estadoDispositivo" valor={e} />
            </span>
          </button>
        ))}
      </div>

      <div className="filtros">
        <Segmentos
          nombre="Tipo"
          valor={tipo}
          onCambio={(v) => fijar('tipo', v)}
          opciones={[
            { valor: '', texto: 'Todos' },
            { valor: 'ROBOT', texto: <><Glifo tipo="ROBOT" /> Robots</> },
            { valor: 'DRONE', texto: <><Glifo tipo="DRONE" /> Drones</> },
          ]}
        />
        <label className="filtro">
          <span>Estado</span>
          <select value={estado} onChange={(e) => fijar('estado', e.target.value)}>
            <option value="">Todos</option>
            {ESTADOS.map((e) => (
              <option key={e} value={e}>
                {TEXTOS.estadoDispositivo[e]}
              </option>
            ))}
          </select>
        </label>
        {(tipo || estado) && (
          <button className="boton boton--fantasma" onClick={() => setParams({}, { replace: true })}>
            Limpiar filtros
          </button>
        )}
      </div>

      <ErrorApiVista error={lista.error} />
      <div className="tabla-marco">
        {lista.cargando && !lista.datos ? (
          <Cargando />
        ) : lista.datos && lista.datos.items.length === 0 ? (
          <Vacio>No hay dispositivos con estos filtros.</Vacio>
        ) : (
          <table className="tabla tabla--clic">
            <thead>
              <tr>
                <th>Serie</th>
                <th>Tipo</th>
                <th>Modelo</th>
                <th>Estado</th>
                <th>Batería</th>
                <th className="num">Horas desde mant.</th>
                <th className="num">Capacidad / autonomía</th>
                <th>Sensores</th>
                <th>Registro</th>
              </tr>
            </thead>
            <tbody>
              {lista.datos?.items.map((d) => (
                <tr
                  key={d.id_dispositivo}
                  onClick={() => navegar(`/inventario/${d.id_dispositivo}`)}
                  className={d.dado_de_baja ? 'fila-tenue' : ''}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && navegar(`/inventario/${d.id_dispositivo}`)}
                >
                  <td>
                    <span className="mono serie">{d.numero_serie}</span>
                  </td>
                  <td>
                    <span className="tipo-celda">
                      <Glifo tipo={d.tipo} />
                      {TEXTOS.tipoDispositivo[d.tipo]}
                    </span>
                  </td>
                  <td>{d.modelo}</td>
                  <td>
                    <Estado grupo="estadoDispositivo" valor={d.estado} />
                    {d.dado_de_baja && <span className="tenue"> · dado de baja</span>}
                  </td>
                  <td>
                    <Bateria nivel={d.nivel_bateria} />
                  </td>
                  <td className="num mono">{numero(d.horas_uso_desde_mant, 1)} h</td>
                  <td className="num mono">
                    {d.tipo === 'ROBOT' ? `${numero(d.capacidad_carga_kg, 1)} kg` : `${numero(d.autonomia_vuelo_min)} min`}
                  </td>
                  <td>
                    {d.sensores_en_falla.length === 0 ? (
                      <span className="tenue">Todos OK</span>
                    ) : (
                      <span className="texto-acento">{d.sensores_en_falla.join(', ')} en falla</span>
                    )}
                  </td>
                  <td className="mono">{fecha(d.fecha_registro)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {lista.datos && (
        <Paginacion total={lista.datos.total} limite={lista.datos.limite} desplazamiento={desp} onCambio={setDesp} />
      )}
    </Pagina>
  );
}
