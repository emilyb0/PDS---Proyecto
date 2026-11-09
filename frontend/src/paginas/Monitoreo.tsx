import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import type { Alerta, DispositivoMonitoreo } from '../api/tipos';
import { Bateria, Causa, Estado, Glifo, Sensores } from '../componentes/ui';
import { MapaMonitoreo } from '../mapa/MapaMonitoreo';
import { useSesion } from '../sesion/SesionContext';
import { enAlerta, useMonitoreo } from '../tiempoReal/MonitoreoContext';
import { aFecha, coordenada, fechaHora, haceCuanto, hora, texto } from '../utils/formato';

function useAhora() {
  const [ahora, setAhora] = useState(Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setAhora(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  return ahora;
}

/** Avance del servicio entre la salida y el fin estimado; marca el retraso en minutos. */
function Avance({ salida, fin, ahora }: { salida: string; fin: string; ahora: number }) {
  const a = aFecha(salida)?.getTime();
  const b = aFecha(fin)?.getTime();
  if (!a || !b || b <= a) return null;
  const k = Math.max(0, Math.min(1, (ahora - a) / (b - a)));
  const retraso = Math.floor((ahora - b) / 60000);
  return (
    <div className={`avance ${retraso > 0 ? 'avance--retraso' : ''}`}>
      <div className="avance-barra">
        <span style={{ width: `${k * 100}%` }} />
      </div>
      <div className="avance-texto mono">
        <span>{hora(salida, false)}</span>
        <span>{retraso > 0 ? `+${retraso} min sobre el fin` : `${Math.round(k * 100)} %`}</span>
        <span>{hora(fin, false)}</span>
      </div>
    </div>
  );
}

function FilaDispositivo({ d, pulso, recibido, ahora, seleccionado, alerta, onElegir }: {
  d: DispositivoMonitoreo;
  pulso: number;
  recibido?: number;
  ahora: number;
  seleccionado: boolean;
  alerta: boolean;
  onElegir: () => void;
}) {
  const t = d.telemetria;
  const s = d.servicio;
  return (
    <li className={`flota-fila ${seleccionado ? 'flota-fila--sel' : ''} ${alerta ? 'flota-fila--alerta' : ''} ${s ? 'flota-fila--servicio' : ''}`}>
      <button className="flota-boton" onClick={onElegir} aria-expanded={seleccionado}>
        {pulso > 0 && <span key={pulso} className="destello" aria-hidden />}
        <Glifo tipo={d.tipo} className={s ? 'glifo--activo' : ''} />
        <span className="flota-id">
          <span className="mono flota-serie">{d.numero_serie}</span>
          <span className="flota-modelo">{d.modelo}</span>
        </span>
        <Estado grupo="estadoDispositivo" valor={d.estado} />
        <span className="flota-linea">
          <Bateria nivel={t?.nivel_bateria} compacta />
          <span className="flota-fase">
            {t ? texto('faseServicio', t.estado_servicio) : 'Sin lectura'}
            {s && (
              <>
                {' '}
                <span className="tenue">→</span> {t?.estado_servicio === 'RETORNANDO' ? 'Base' : s.destino.nombre}
              </>
            )}
          </span>
          <span className="flota-hace mono">{recibido ? haceCuanto(recibido, ahora) : t ? hora(t.fecha_hora) : '—'}</span>
        </span>
        {t && t.sensores.some((x) => x.estado === 'FALLA') && !seleccionado && (
          <span className="flota-falla">
            Falla: {t.sensores.filter((x) => x.estado === 'FALLA').map((x) => x.nombre).join(', ')}
          </span>
        )}
      </button>
      {seleccionado && (
        <div className="flota-ficha">
          {t && (
            <dl className="ficha-datos">
              <div>
                <dt>Posición</dt>
                <dd className="mono">
                  {coordenada(t.latitud)}, {coordenada(t.longitud)}
                </dd>
              </div>
              <div>
                <dt>Lectura</dt>
                <dd className="mono">{fechaHora(t.fecha_hora, true)}</dd>
              </div>
              <div className="ficha-ancho">
                <dt>Sensores</dt>
                <dd>
                  <Sensores sensores={t.sensores} />
                </dd>
              </div>
            </dl>
          )}
          {s ? (
            <div className="ficha-servicio">
              <div className="ficha-servicio-cab">
                <span>{texto('tipoServicio', s.tipo_servicio)}</span>
                <Estado grupo="estadoBitacora" valor={s.estado} />
              </div>
              <dl className="ficha-datos">
                <div>
                  <dt>Destino</dt>
                  <dd>{s.destino.nombre}</dd>
                </div>
                <div>
                  <dt>Operador</dt>
                  <dd>{s.operador.nombre}</dd>
                </div>
              </dl>
              <Avance salida={s.hora_salida} fin={s.fin_estimado} ahora={ahora} />
              <div className="ficha-enlaces">
                <Link to={`/bitacoras/${s.id_bitacora}`}>Bitácora #{s.id_bitacora}</Link>
                <Link to={`/reservas/${s.id_reserva}`}>Reserva #{s.id_reserva}</Link>
                <Link to={`/inventario/${d.id_dispositivo}`}>Ficha del dispositivo</Link>
              </div>
            </div>
          ) : (
            <div className="ficha-enlaces">
              <span className="tenue">Sin servicio asignado.</span>
              <Link to={`/inventario/${d.id_dispositivo}`}>Ficha del dispositivo</Link>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

function ItemAlerta({ a, mia, onElegir }: { a: Alerta; mia: boolean; onElegir: () => void }) {
  return (
    <li className={`alerta-item ${mia ? 'alerta-item--mia' : ''}`}>
      <button onClick={onElegir} className="alerta-boton">
        <span className="alerta-item-cab">
          <Causa valor={a.causa} />
          <span className="mono">{a.numero_serie}</span>
          {mia && <span className="etiqueta-mia">A su cargo</span>}
          <span className="mono tenue alerta-item-hora">{fechaHora(a.fecha_hora)}</span>
        </span>
        <span className="alerta-item-texto">{a.descripcion}</span>
      </button>
      <Link to={`/alertas/${a.id_alerta}`} className="alerta-item-detalle" aria-label={`Detalle de la alerta ${a.id_alerta}`}>
        #{a.id_alerta}
      </Link>
    </li>
  );
}

export function Monitoreo() {
  const m = useMonitoreo();
  const { sesion } = useSesion();
  const ahora = useAhora();
  const [params, setParams] = useSearchParams();
  const seleccionado = params.get('d') ? Number(params.get('d')) : null;

  const elegir = (id: number | null) => {
    const p = new URLSearchParams(params);
    if (id == null || id === seleccionado) p.delete('d');
    else p.set('d', String(id));
    setParams(p, { replace: true });
  };

  const resumen = useMemo(() => {
    const c = { total: m.dispositivos.length, servicio: 0, disponibles: 0, carga: 0, fuera: 0 };
    for (const d of m.dispositivos) {
      if (d.servicio) c.servicio++;
      if (d.estado === 'DISPONIBLE') c.disponibles++;
      if (d.estado === 'EN_CARGA') c.carga++;
      if (d.estado === 'FUERA_DE_SERVICIO' || d.estado === 'EN_MANTENIMIENTO') c.fuera++;
    }
    return c;
  }, [m.dispositivos]);

  const alertas = useMemo(
    () => [...m.alertas].sort((a, b) => (aFecha(b.fecha_hora)?.getTime() ?? 0) - (aFecha(a.fecha_hora)?.getTime() ?? 0)),
    [m.alertas],
  );
  const mias = sesion?.usuario.rol === 'OPERADOR' ? sesion.usuario.id_usuario : null;

  return (
    <div className="monitoreo">
      <div className="mon-kpis">
        <div className="kpi">
          <span className="kpi-etiqueta">Flota</span>
          <span className="kpi-valor">{resumen.total}</span>
        </div>
        <div className={`kpi ${resumen.servicio > 0 ? 'kpi--activo' : ''}`}>
          <span className="kpi-etiqueta">En servicio</span>
          <span className="kpi-valor">
            {resumen.servicio}
            <small>/{resumen.total}</small>
          </span>
        </div>
        <div className="kpi">
          <span className="kpi-etiqueta">Disponibles</span>
          <span className="kpi-valor">{resumen.disponibles}</span>
        </div>
        <div className="kpi">
          <span className="kpi-etiqueta">En carga</span>
          <span className="kpi-valor">{resumen.carga}</span>
        </div>
        <div className={`kpi ${alertas.length > 0 ? 'kpi--alerta' : ''}`}>
          <span className="kpi-etiqueta">Alertas sin atender</span>
          <span className="kpi-valor" key={alertas.length}>
            {alertas.length}
          </span>
        </div>
        <div className="kpi kpi--texto">
          <span className="kpi-etiqueta">Ciclo de lectura</span>
          <span className="kpi-valor">
            {m.intervaloSeg}
            <small> s</small>
          </span>
        </div>
        <div className="mon-titulo">
          <span className="pagina-codigo">RF09 · RF10 · RF11</span>
          <h1>Monitoreo en tiempo real</h1>
        </div>
      </div>

      <div className="mon-cuerpo">
        <div className="mon-mapa">
          <MapaMonitoreo
            dispositivos={m.dispositivos}
            estelas={m.estelas}
            alertas={m.alertas}
            ubicaciones={m.ubicaciones}
            seleccionado={seleccionado}
            onSeleccionar={elegir}
          />
          <div className="mon-leyenda" aria-label="Leyenda del mapa">
            <span>
              <Glifo tipo="ROBOT" /> Robot
            </span>
            <span>
              <Glifo tipo="DRONE" /> Drone
            </span>
            <span>
              <i className="ley-servicio" /> En servicio
            </span>
            <span>
              <i className="ley-alerta" /> Alerta
            </span>
            <span>
              <i className="ley-estela" /> Recorrido
            </span>
            <span>
              <i className="ley-destino" /> Hacia destino
            </span>
          </div>
          <div className="mon-registro" aria-live="off">
            <div className="mon-registro-cab">Registro en vivo</div>
            {m.registro.length === 0 ? (
              <div className="mon-registro-vacio">Esperando eventos del servidor…</div>
            ) : (
              <ol>
                {m.registro.slice(0, 5).map((r) => (
                  <li key={r.id} className={`reg reg--${r.clase}`}>
                    <span className="mono">{r.hora}</span> {r.texto}
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>

        <aside className="mon-lateral">
          <section className="mon-seccion mon-flota">
            <header className="mon-seccion-cab">
              <h2>Flota</h2>
              <span className="mono tenue">{m.dispositivos.length} dispositivos</span>
            </header>
            {m.dispositivos.length === 0 ? (
              <div className="vacio">Cargando la foto inicial…</div>
            ) : (
              <ul className="flota">
                {m.dispositivos.map((d) => (
                  <FilaDispositivo
                    key={d.id_dispositivo}
                    d={d}
                    pulso={m.pulsos[d.id_dispositivo] ?? 0}
                    recibido={m.recibido[d.id_dispositivo]}
                    ahora={ahora}
                    seleccionado={seleccionado === d.id_dispositivo}
                    alerta={enAlerta(d, m.alertas)}
                    onElegir={() => elegir(d.id_dispositivo)}
                  />
                ))}
              </ul>
            )}
          </section>
          <section className="mon-seccion mon-alertas">
            <header className="mon-seccion-cab">
              <h2>Alertas sin atender</h2>
              <Link to="/alertas" className="mono">
                Historial →
              </Link>
            </header>
            {alertas.length === 0 ? (
              <div className="vacio">Sin alertas.</div>
            ) : (
              <ul className="alertas-lista">
                {alertas.slice(0, 12).map((a) => (
                  <ItemAlerta
                    key={a.id_alerta}
                    a={a}
                    mia={mias != null && a.id_operador === mias}
                    onElegir={() => elegir(a.id_dispositivo)}
                  />
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
