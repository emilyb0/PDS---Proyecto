import { useMemo, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ErrorApi } from '../api/cliente';
import { api } from '../api/servicios';
import type { Dispositivo, Reserva, TipoServicio } from '../api/tipos';
import { useAvisos } from '../componentes/Avisos';
import {
  Advertencias,
  Bateria,
  Campo,
  ErrorApiVista,
  Estado,
  Glifo,
  Pagina,
  Panel,
  Segmentos,
  Vacio,
  useCarga,
} from '../componentes/ui';
import { useSesion } from '../sesion/SesionContext';
import { fecha as fmtFecha, hoyBogota, horaBogota, TEXTOS, texto, tipoPara } from '../utils/formato';

const CAMPOS = ['tipo_servicio', 'fecha', 'hora_inicio', 'duracion_estimada_min', 'id_origen', 'id_destino', 'id_dispositivo', 'id_operador'];

function aMinutos(h: string) {
  const [a, b] = h.split(':').map(Number);
  return a * 60 + (b || 0);
}

function aHora(min: number) {
  const m = ((min % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}

/** Motivos por los que el dispositivo probablemente no sea apto (el backend decide con datos en vivo, RF07). */
export function avisosDeAptitud(d: Dispositivo): string[] {
  const m: string[] = [];
  if (d.dado_de_baja) m.push('Dado de baja');
  else if (d.estado !== 'DISPONIBLE' && d.estado !== 'EN_SERVICIO') m.push(texto('estadoDispositivo', d.estado));
  if (d.nivel_bateria != null && d.nivel_bateria < 30) m.push(`Batería ${Math.round(d.nivel_bateria)} %`);
  if (d.sensores_en_falla.length) m.push(`${d.sensores_en_falla.join(', ')} en falla`);
  return m;
}

/** Línea del día con las reservas del dispositivo y el horario nuevo (RF06 a la vista antes de confirmar). */
function LineaDia({ reservas, inicio, duracion, conflicto, esHoy }: {
  reservas: Reserva[];
  inicio: string;
  duracion: number;
  conflicto: number | null;
  esHoy: boolean;
}) {
  const ini = inicio ? aMinutos(inicio) : null;
  const fin = ini != null ? ini + (duracion || 0) : null;
  const tramos = reservas.map((r) => [aMinutos(r.hora_inicio), aMinutos(r.hora_fin)] as const);
  const minimo = Math.min(6 * 60, ...(ini != null ? [ini] : []), ...tramos.map((t) => t[0]));
  const maximo = Math.max(22 * 60, ...(fin != null ? [fin] : []), ...tramos.map((t) => t[1]));
  const desde = Math.floor(minimo / 60) * 60;
  const hasta = Math.ceil(maximo / 60) * 60;
  const pos = (m: number) => `${((m - desde) / (hasta - desde)) * 100}%`;
  const ancho = (a: number, b: number) => `${(Math.max(b - a, 4) / (hasta - desde)) * 100}%`;
  const horas: number[] = [];
  for (let h = desde; h <= hasta; h += 120) horas.push(h);
  const ahora = aMinutos(horaBogota());

  return (
    <div className="linea-dia">
      <div className="linea-dia-pista">
        {horas.map((h) => (
          <span key={h} className="linea-dia-marca" style={{ left: pos(h) }}>
            <span className="mono">{aHora(h).slice(0, 2)}</span>
          </span>
        ))}
        {esHoy && ahora >= desde && ahora <= hasta && <span className="linea-dia-ahora" style={{ left: pos(ahora) }} title="Ahora" />}
        {reservas.map((r) => {
          const a = aMinutos(r.hora_inicio);
          const b = aMinutos(r.hora_fin);
          const cruza = ini != null && fin != null && a < fin && ini < b;
          return (
            <Link
              key={r.id_reserva}
              to={`/reservas/${r.id_reserva}`}
              className={`linea-dia-tramo ${cruza || conflicto === r.id_reserva ? 'linea-dia-tramo--cruce' : ''}`}
              style={{ left: pos(a), width: ancho(a, b) }}
              title={`#${r.id_reserva} · ${r.hora_inicio}–${r.hora_fin} · ${texto('tipoServicio', r.tipo_servicio)}`}
            >
              <span className="mono">#{r.id_reserva}</span>
            </Link>
          );
        })}
        {ini != null && fin != null && (
          <span className="linea-dia-nueva" style={{ left: pos(ini), width: ancho(ini, fin) }} title="Horario de la nueva reserva" />
        )}
      </div>
    </div>
  );
}

export function ReservaNueva() {
  const { tiene } = useSesion();
  const { avisar } = useAvisos();
  const navegar = useNavigate();

  const [servicio, setServicio] = useState<TipoServicio>('PEDIDO_CAFETERIA');
  const [fecha, setFecha] = useState(hoyBogota());
  const [hora, setHora] = useState(horaBogota());
  const [duracion, setDuracion] = useState('30');
  const [origen, setOrigen] = useState('');
  const [destino, setDestino] = useState('');
  const [operador, setOperador] = useState('');
  const [dispositivo, setDispositivo] = useState<number | null>(null);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [error, setError] = useState<ErrorApi | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [creada, setCreada] = useState<Reserva | null>(null);
  const [iniciando, setIniciando] = useState(false);

  const tipo = tipoPara(servicio);
  const ubicaciones = useCarga(() => api.ubicaciones(), []);
  const operadores = useCarga(() => api.usuarios({ rol: 'OPERADOR', estado: 'ACTIVO', limite: 200 }), []);
  const dispositivos = useCarga(() => api.dispositivos({ tipo, limite: 200 }), [tipo]);
  const ocupacion = useCarga(
    () => (dispositivo && fecha ? api.reservas({ fecha, id_dispositivo: dispositivo, limite: 200 }) : Promise.resolve(null)),
    [dispositivo, fecha, creada],
  );
  const conflictoId = (error?.detalles?.reserva_en_conflicto as { id_reserva?: number } | undefined)?.id_reserva ?? null;

  const candidatos = useMemo(() => (dispositivos.datos?.items ?? []).filter((d) => !d.dado_de_baja), [dispositivos.datos]);
  const ocupadas = (ocupacion.datos?.items ?? []).filter((r) => r.estado !== 'CANCELADA');

  const cambiarServicio = (s: TipoServicio) => {
    setServicio(s);
    if (tipoPara(s) !== tipo) setDispositivo(null);
  };

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    const locales: Record<string, string> = {};
    if (!fecha) locales.fecha = 'Elija la fecha.';
    if (!hora) locales.hora_inicio = 'Elija la hora de inicio.';
    const dur = Number(duracion);
    if (!Number.isInteger(dur) || dur < 1 || dur > 480) locales.duracion_estimada_min = 'Entre 1 y 480 minutos.';
    if (!origen) locales.id_origen = 'Elija el origen.';
    if (!destino) locales.id_destino = 'Elija el destino.';
    if (origen && destino && origen === destino) locales.id_destino = 'El destino debe ser distinto del origen.';
    if (!operador) locales.id_operador = 'Elija el operador responsable.';
    if (!dispositivo) locales.id_dispositivo = 'Elija un dispositivo.';
    setErrores(locales);
    setError(null);
    if (Object.keys(locales).length) return;

    setEnviando(true);
    try {
      const r = await api.crearReserva({
        tipo_servicio: servicio,
        fecha,
        hora_inicio: hora,
        duracion_estimada_min: dur,
        id_origen: Number(origen),
        id_destino: Number(destino),
        id_dispositivo: dispositivo!,
        id_operador: Number(operador),
      });
      setCreada(r);
      avisar({ tipo: 'exito', rotulo: 'RF05 · Reserva creada', titulo: `Reserva #${r.id_reserva} · ${r.dispositivo.numero_serie}`, texto: `${fmtFecha(r.fecha)} · ${r.hora_inicio}–${r.hora_fin}` });
    } catch (err) {
      if (err instanceof ErrorApi) {
        setError(err);
        const c = err.campos;
        if (['CRUCE_HORARIO', 'DISPOSITIVO_NO_APTO', 'TIPO_DISPOSITIVO_INCORRECTO'].includes(err.codigo)) c.id_dispositivo = err.mensaje;
        if (err.codigo === 'CRUCE_HORARIO') c.hora_inicio = 'Se cruza con otra reserva del dispositivo.';
        setErrores(c);
      }
    } finally {
      setEnviando(false);
    }
  };

  const iniciarAhora = async () => {
    if (!creada) return;
    setIniciando(true);
    try {
      await api.demoIniciar(creada.id_reserva);
      avisar({ tipo: 'info', rotulo: 'Demo', titulo: `Reserva #${creada.id_reserva} iniciada`, texto: 'Siga el recorrido en el monitoreo.' });
      navegar(`/monitoreo?d=${creada.dispositivo.id_dispositivo}`);
    } catch (err) {
      // La reserva pudo arrancar sola (inicio automático): si ya está en curso, seguir igual.
      const r = await api.reserva(creada.id_reserva).catch(() => null);
      if (r?.estado === 'EN_CURSO') navegar(`/monitoreo?d=${creada.dispositivo.id_dispositivo}`);
      else if (err instanceof ErrorApi) avisar({ tipo: 'error', rotulo: err.codigo, titulo: 'No se pudo iniciar', texto: err.mensaje });
    } finally {
      setIniciando(false);
    }
  };

  const reiniciar = () => {
    setCreada(null);
    setError(null);
    setErrores({});
    setDispositivo(null);
    setHora(horaBogota());
  };

  if (creada) {
    return (
      <Pagina codigo="RF05 · Reservas" titulo={`Reserva #${creada.id_reserva} creada`}>
        <div className="rejilla-2">
          <Panel codigo="OK" titulo="Confirmación" className="panel--confirmacion">
            <dl className="datos">
              <div className="dato">
                <dt>Servicio</dt>
                <dd>{texto('tipoServicio', creada.tipo_servicio)}</dd>
              </div>
              <div className="dato">
                <dt>Horario</dt>
                <dd className="mono">
                  {fmtFecha(creada.fecha)} · {creada.hora_inicio}–{creada.hora_fin}
                </dd>
              </div>
              <div className="dato">
                <dt>Dispositivo</dt>
                <dd>
                  <Glifo tipo={creada.dispositivo.tipo} /> <span className="mono">{creada.dispositivo.numero_serie}</span> · {creada.dispositivo.modelo}
                </dd>
              </div>
              <div className="dato">
                <dt>Recorrido</dt>
                <dd>
                  {creada.origen.nombre} → {creada.destino.nombre}
                </dd>
              </div>
              <div className="dato">
                <dt>Operador</dt>
                <dd>{creada.operador.nombre}</dd>
              </div>
              <div className="dato">
                <dt>Estado</dt>
                <dd>
                  <Estado grupo="estadoReserva" valor={creada.estado} />
                </dd>
              </div>
            </dl>
            <Advertencias lista={creada.advertencias} />
            <div className="formulario-acciones">
              {tiene('demo.usar') && creada.estado === 'PROGRAMADA' && (
                <button className="boton boton--acento" onClick={iniciarAhora} disabled={iniciando}>
                  {iniciando ? 'Iniciando…' : 'Iniciar ahora (demo)'}
                </button>
              )}
              <Link className="boton" to={`/reservas/${creada.id_reserva}`}>
                Ver reserva
              </Link>
              <button className="boton boton--fantasma" onClick={reiniciar}>
                Crear otra
              </button>
            </div>
          </Panel>
          {creada.codigo_entrega && (
            <Panel codigo="RF05" titulo="Código de entrega">
              <div className="codigo-entrega" aria-label={`Código ${creada.codigo_entrega}`}>
                {creada.codigo_entrega.split('').map((c, i) => (
                  <span key={i}>{c}</span>
                ))}
              </div>
              <p className="tenue">Quien recibe el pedido usará este código de 4 dígitos para confirmar la entrega.</p>
            </Panel>
          )}
        </div>
      </Pagina>
    );
  }

  const ubic = ubicaciones.datos ?? [];

  return (
    <Pagina
      codigo="RF05 · RF06 · RF07"
      titulo="Nueva reserva"
      subtitulo="Al confirmar, el sistema valida el cruce de horario, la batería y los sensores del dispositivo."
      acciones={
        <Link className="boton boton--fantasma" to="/reservas">
          ← Reservas
        </Link>
      }
    >
      <form className="reserva-form" onSubmit={enviar} noValidate>
        <Panel codigo="01" titulo="Servicio y horario">
          <div className="formulario">
            <Campo etiqueta="Tipo de servicio" grupo ancho="completo" error={errores.tipo_servicio}>
              <Segmentos
                nombre="Tipo de servicio"
                valor={servicio}
                onCambio={cambiarServicio}
                opciones={(Object.keys(TEXTOS.tipoServicio) as TipoServicio[]).map((s) => ({
                  valor: s,
                  texto: (
                    <>
                      <Glifo tipo={tipoPara(s)} /> {TEXTOS.tipoServicio[s]}
                    </>
                  ),
                }))}
              />
            </Campo>
            <Campo etiqueta="Fecha" error={errores.fecha}>
              <input type="date" value={fecha} min={hoyBogota()} onChange={(e) => setFecha(e.target.value)} />
            </Campo>
            <Campo etiqueta="Hora de inicio" error={errores.hora_inicio}>
              <div className="entrada-con-boton">
                <input type="time" value={hora} onChange={(e) => setHora(e.target.value)} />
                <button type="button" className="boton boton--fantasma" onClick={() => { setFecha(hoyBogota()); setHora(horaBogota()); }}>
                  Ahora
                </button>
              </div>
            </Campo>
            <Campo etiqueta="Duración estimada (min)" error={errores.duracion_estimada_min}>
              <div className="entrada-con-boton">
                <input type="number" min={1} max={480} value={duracion} onChange={(e) => setDuracion(e.target.value)} />
                {[3, 15, 30].map((n) => (
                  <button key={n} type="button" className={`boton boton--fantasma ${duracion === String(n) ? 'activo' : ''}`} onClick={() => setDuracion(String(n))}>
                    {n}
                  </button>
                ))}
              </div>
            </Campo>
            <Campo etiqueta="Operador responsable" error={errores.id_operador}>
              <select value={operador} onChange={(e) => setOperador(e.target.value)}>
                <option value="">Elegir…</option>
                {operadores.datos?.items.map((u) => (
                  <option key={u.id_usuario} value={u.id_usuario}>
                    {u.nombre}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo etiqueta="Origen" error={errores.id_origen}>
              <select value={origen} onChange={(e) => setOrigen(e.target.value)}>
                <option value="">Elegir…</option>
                {ubic.map((u) => (
                  <option key={u.id_ubicacion} value={u.id_ubicacion}>
                    {u.nombre}
                    {u.es_base ? ' (base)' : ''}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo etiqueta="Destino" error={errores.id_destino}>
              <select value={destino} onChange={(e) => setDestino(e.target.value)}>
                <option value="">Elegir…</option>
                {ubic.map((u) => (
                  <option key={u.id_ubicacion} value={u.id_ubicacion} disabled={String(u.id_ubicacion) === origen}>
                    {u.nombre}
                    {u.es_base ? ' (base)' : ''}
                  </option>
                ))}
              </select>
            </Campo>
          </div>
        </Panel>

        <Panel
          codigo="02"
          titulo={`Dispositivo · ${tipo === 'ROBOT' ? 'robots' : 'drones'}`}
          acciones={<span className="tenue">Las entregas van con robot; la grabación, con drone.</span>}
        >
          <Campo etiqueta="Elija el dispositivo" grupo ancho="completo" error={errores.id_dispositivo}>
            {candidatos.length === 0 ? (
              <Vacio>{dispositivos.cargando ? 'Cargando…' : 'No hay dispositivos de este tipo.'}</Vacio>
            ) : (
              <div className="tarjetas-dispositivo">
                {candidatos.map((d) => {
                  const avisos = avisosDeAptitud(d);
                  return (
                    <button
                      type="button"
                      key={d.id_dispositivo}
                      aria-pressed={dispositivo === d.id_dispositivo}
                      className={`tarjeta-dispositivo ${dispositivo === d.id_dispositivo ? 'activo' : ''} ${avisos.length ? 'tarjeta-dispositivo--aviso' : ''}`}
                      onClick={() => setDispositivo(d.id_dispositivo)}
                    >
                      <span className="tarjeta-cab">
                        <Glifo tipo={d.tipo} />
                        <span className="mono serie">{d.numero_serie}</span>
                        <Estado grupo="estadoDispositivo" valor={d.estado} />
                      </span>
                      <span className="tenue">{d.modelo}</span>
                      <Bateria nivel={d.nivel_bateria} />
                      <span className="tarjeta-aviso">{avisos.length ? avisos.join(' · ') : 'Sin observaciones'}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </Campo>

          <div className="ocupacion">
            <div className="ocupacion-cab">
              <span className="campo-etiqueta">Ocupación del dispositivo · {fmtFecha(fecha, true)}</span>
              <span className="tenue">
                {dispositivo ? `${ocupadas.length} reserva${ocupadas.length === 1 ? '' : 's'} ese día` : 'Elija un dispositivo para ver su agenda'}
              </span>
            </div>
            {dispositivo && (
              <LineaDia reservas={ocupadas} inicio={hora} duracion={Number(duracion)} conflicto={conflictoId} esHoy={fecha === hoyBogota()} />
            )}
          </div>

          <ErrorApiVista error={error} camposVisibles={CAMPOS} />
          <div className="formulario-acciones">
            <button className="boton boton--primario boton--grande" disabled={enviando}>
              {enviando ? 'Validando…' : 'Confirmar reserva'}
            </button>
          </div>
        </Panel>
      </form>
    </Pagina>
  );
}
