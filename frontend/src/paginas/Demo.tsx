import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ErrorApi } from '../api/cliente';
import { api } from '../api/servicios';
import type { TipoServicio, Ubicacion } from '../api/tipos';
import { useAvisos } from '../componentes/Avisos';
import { Bateria, Campo, ErrorApiVista, Estado, Glifo, Pagina, Panel, Segmentos, Sensores, Vacio, useCarga } from '../componentes/ui';
import { MapaMonitoreo } from '../mapa/MapaMonitoreo';
import { useMonitoreo } from '../tiempoReal/MonitoreoContext';
import { fecha, hoyBogota, horaBogota, texto } from '../utils/formato';

const TAREAS = [
  { nombre: 'iniciar-reservas', titulo: 'Iniciar reservas', texto: 'Arranca las reservas cuya hora ya llegó.' },
  { nombre: 'monitoreo', titulo: 'Ciclo de monitoreo', texto: 'Lee ya todos los dispositivos y evalúa las alertas.' },
  { nombre: 'reintento-subidas', titulo: 'Reintentar subidas', texto: 'Sube los videos que quedaron pendientes.' },
];

function porNombre(ubic: Ubicacion[], prefijo: string) {
  return ubic.find((u) => u.nombre.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '').startsWith(prefijo));
}

/** Origen y destino sugeridos para la demo: Cafetería → Rectoría (robot) o Base → Cancha (drone). */
function puntosSugeridos(ubic: Ubicacion[], tipo: string): [string, string] {
  const otros = ubic.filter((u) => !u.es_base);
  const base = ubic.find((u) => u.es_base);
  const o = tipo === 'DRONE' ? base ?? otros[0] : porNombre(ubic, 'cafeter') ?? otros[0];
  const d = tipo === 'DRONE' ? porNombre(ubic, 'cancha') ?? otros[0] : porNombre(ubic, 'rector') ?? otros[1];
  return [String(o?.id_ubicacion ?? ''), String(d?.id_ubicacion ?? '')];
}

export function Demo() {
  const m = useMonitoreo();
  const { avisar } = useAvisos();
  const [ocupado, setOcupado] = useState<string | null>(null);

  // ------------------------------------------------ Reserva rápida
  const operadores = useCarga(() => api.usuarios({ rol: 'OPERADOR', estado: 'ACTIVO', limite: 200 }), []);
  const [idDisp, setIdDisp] = useState<number | null>(null);
  const [servicioRobot, setServicioRobot] = useState<TipoServicio>('PEDIDO_CAFETERIA');
  const [duracion, setDuracion] = useState('3');
  const [operador, setOperador] = useState('');
  const [origen, setOrigen] = useState('');
  const [destino, setDestino] = useState('');
  const [iniciarYa, setIniciarYa] = useState(true);
  const [errorReserva, setErrorReserva] = useState<ErrorApi | null>(null);

  const elegible = useMemo(() => m.dispositivos.filter((d) => d.estado !== 'FUERA_DE_SERVICIO'), [m.dispositivos]);
  const dispReserva = m.dispositivos.find((d) => d.id_dispositivo === idDisp) ?? null;

  // Valores por defecto en cuanto llegan los datos: el primer robot libre y sin fallas.
  useEffect(() => {
    if (idDisp != null || elegible.length === 0) return;
    const libre = elegible.find(
      (d) => d.tipo === 'ROBOT' && d.estado === 'DISPONIBLE' && !d.servicio && (d.telemetria?.nivel_bateria ?? 100) >= 30 && !d.telemetria?.sensores.some((s) => s.estado === 'FALLA'),
    );
    setIdDisp((libre ?? elegible[0]).id_dispositivo);
  }, [elegible, idDisp]);
  useEffect(() => {
    if (!operador && operadores.datos?.items.length) setOperador(String(operadores.datos.items[0].id_usuario));
  }, [operadores.datos, operador]);
  useEffect(() => {
    if (!dispReserva || m.ubicaciones.length === 0) return;
    const [o, d] = puntosSugeridos(m.ubicaciones, dispReserva.tipo);
    setOrigen(o);
    setDestino(d);
  }, [dispReserva?.tipo, m.ubicaciones]); // eslint-disable-line react-hooks/exhaustive-deps

  const programadas = useCarga(() => api.reservas({ estado: 'PROGRAMADA', limite: 12 }), [m.registro.length]);

  const iniciarReserva = async (idReserva: number, serie: string) => {
    setOcupado(`iniciar-${idReserva}`);
    try {
      const r = await api.demoIniciar(idReserva);
      m.anotar('comando', `Iniciar reserva #${idReserva} (${serie}) → bitácora #${r.id_bitacora ?? '—'}`);
      m.recargar();
    } catch (e) {
      const r = await api.reserva(idReserva).catch(() => null);
      if (r?.estado === 'EN_CURSO') m.anotar('comando', `Reserva #${idReserva} ya estaba en curso (inicio automático).`);
      else if (e instanceof ErrorApi) {
        m.anotar('error', `Iniciar reserva #${idReserva}: ${e.mensaje}`);
        avisar({ tipo: 'error', rotulo: e.codigo, titulo: `No se inició la reserva #${idReserva}`, texto: e.mensaje });
      }
    } finally {
      setOcupado(null);
      programadas.recargar();
    }
  };

  const crearReserva = async (e: FormEvent) => {
    e.preventDefault();
    if (!dispReserva) return;
    setErrorReserva(null);
    setOcupado('reserva');
    const servicio: TipoServicio = dispReserva.tipo === 'DRONE' ? 'GRABACION_EVENTO' : servicioRobot;
    try {
      const r = await api.crearReserva({
        tipo_servicio: servicio,
        fecha: hoyBogota(),
        hora_inicio: horaBogota(),
        duracion_estimada_min: Number(duracion),
        id_origen: Number(origen),
        id_destino: Number(destino),
        id_dispositivo: dispReserva.id_dispositivo,
        id_operador: Number(operador),
      });
      m.anotar('comando', `Reserva #${r.id_reserva} creada · ${r.dispositivo.numero_serie} · ${r.hora_inicio}–${r.hora_fin}${r.codigo_entrega ? ` · código ${r.codigo_entrega}` : ''}`);
      setOcupado(null);
      if (iniciarYa) await iniciarReserva(r.id_reserva, r.dispositivo.numero_serie);
      else programadas.recargar();
    } catch (err) {
      if (err instanceof ErrorApi) {
        setErrorReserva(err);
        m.anotar('error', `Crear reserva: ${err.mensaje}`);
      }
    } finally {
      setOcupado(null);
    }
  };

  // ------------------------------------------------ Eventos del dispositivo
  const [idEvento, setIdEvento] = useState<number | null>(null);
  const [nivel, setNivel] = useState('19');
  const [sensor, setSensor] = useState('');
  const objetivo = m.dispositivos.find((d) => d.id_dispositivo === idEvento) ?? null;
  const sensores = objetivo?.telemetria?.sensores ?? [];

  useEffect(() => {
    if (idEvento != null || m.dispositivos.length === 0) return;
    const enServicio = m.dispositivos.find((d) => d.servicio);
    setIdEvento((enServicio ?? m.dispositivos[0]).id_dispositivo);
  }, [m.dispositivos, idEvento]);
  useEffect(() => {
    if (sensores.length && !sensores.some((s) => s.nombre === sensor)) {
      setSensor((sensores.find((s) => s.nombre === 'LIDAR') ?? sensores[sensores.length - 1]).nombre);
    }
  }, [sensores, sensor]);

  const evento = async (cuerpo: Parameters<typeof api.demoEvento>[1], etiqueta: string) => {
    if (!objetivo) return;
    setOcupado(etiqueta);
    try {
      const r = await api.demoEvento(objetivo.id_dispositivo, cuerpo);
      m.anotar('comando', `${r.numero_serie} · ${etiqueta} → ${r.mensaje}`);
    } catch (e) {
      if (e instanceof ErrorApi) {
        m.anotar('error', `${objetivo.numero_serie} · ${etiqueta}: ${e.mensaje}`);
        avisar({ tipo: 'error', rotulo: e.codigo, titulo: etiqueta, texto: e.mensaje });
      }
    } finally {
      setOcupado(null);
    }
  };

  const tarea = async (nombre: string, titulo: string) => {
    setOcupado(nombre);
    try {
      const r = await api.demoTarea(nombre);
      m.anotar('comando', `Tarea ${titulo} → ${typeof r.resultado === 'string' ? r.resultado : JSON.stringify(r.resultado)}`);
    } catch (e) {
      if (e instanceof ErrorApi) m.anotar('error', `Tarea ${titulo}: ${e.mensaje}`);
    } finally {
      setOcupado(null);
    }
  };

  const t = objetivo?.telemetria;

  return (
    <Pagina
      ancho="completo"
      codigo="Controles de demo · MODO_DEMO"
      titulo="Panel de demo"
      subtitulo="Para mostrar las reglas sin esperar: iniciar servicios y provocar eventos en los dispositivos simulados."
      acciones={
        <Link className="boton" to="/monitoreo">
          Abrir monitoreo
        </Link>
      }
    >
      <div className="demo">
        <div className="demo-col">
          <Panel codigo="01" titulo="Reserva rápida para ahora">
            <form className="formulario formulario--columna" onSubmit={crearReserva}>
              <Campo etiqueta="Dispositivo" grupo>
                <div className="chips">
                  {elegible.map((d) => (
                    <button
                      type="button"
                      key={d.id_dispositivo}
                      className={`chip ${idDisp === d.id_dispositivo ? 'activo' : ''} ${d.servicio ? 'chip--servicio' : ''}`}
                      onClick={() => setIdDisp(d.id_dispositivo)}
                      aria-pressed={idDisp === d.id_dispositivo}
                      title={`${d.modelo} · ${texto('estadoDispositivo', d.estado)}`}
                    >
                      <Glifo tipo={d.tipo} />
                      <span className="mono">{d.numero_serie}</span>
                    </button>
                  ))}
                </div>
              </Campo>
              {dispReserva?.tipo === 'ROBOT' ? (
                <Campo etiqueta="Servicio" grupo>
                  <Segmentos
                    nombre="Servicio"
                    valor={servicioRobot}
                    onCambio={setServicioRobot}
                    opciones={[
                      { valor: 'PEDIDO_CAFETERIA', texto: 'Cafetería' },
                      { valor: 'ENTREGA_DOCUMENTOS', texto: 'Documentos' },
                    ]}
                  />
                </Campo>
              ) : (
                <Campo etiqueta="Servicio">
                  <input value="Grabación de evento" readOnly />
                </Campo>
              )}
              <div className="formulario formulario--2">
                <Campo etiqueta="Origen">
                  <select value={origen} onChange={(e) => setOrigen(e.target.value)}>
                    {m.ubicaciones.map((u) => (
                      <option key={u.id_ubicacion} value={u.id_ubicacion}>
                        {u.nombre}
                      </option>
                    ))}
                  </select>
                </Campo>
                <Campo etiqueta="Destino">
                  <select value={destino} onChange={(e) => setDestino(e.target.value)}>
                    {m.ubicaciones.map((u) => (
                      <option key={u.id_ubicacion} value={u.id_ubicacion}>
                        {u.nombre}
                      </option>
                    ))}
                  </select>
                </Campo>
                <Campo etiqueta="Operador">
                  <select value={operador} onChange={(e) => setOperador(e.target.value)}>
                    {operadores.datos?.items.map((u) => (
                      <option key={u.id_usuario} value={u.id_usuario}>
                        {u.nombre}
                      </option>
                    ))}
                  </select>
                </Campo>
                <Campo etiqueta="Duración (min)">
                  <input type="number" min={1} max={480} value={duracion} onChange={(e) => setDuracion(e.target.value)} />
                </Campo>
              </div>
              <label className="casilla">
                <input type="checkbox" checked={iniciarYa} onChange={(e) => setIniciarYa(e.target.checked)} />
                Iniciar el servicio en cuanto se cree
              </label>
              <ErrorApiVista error={errorReserva} />
              <button className="boton boton--acento boton--grande" disabled={!dispReserva || ocupado === 'reserva'}>
                {ocupado === 'reserva' ? 'Creando…' : `Reservar ${dispReserva?.numero_serie ?? ''} a las ${horaBogota()}`}
              </button>
            </form>
          </Panel>

          <Panel codigo="02" titulo="Reservas programadas" acciones={<Link to="/reservas?estado=PROGRAMADA" className="mono">Todas →</Link>}>
            {programadas.datos?.items.length ? (
              <ul className="programadas">
                {programadas.datos.items.map((r) => (
                  <li key={r.id_reserva}>
                    <div>
                      <span className="mono">#{r.id_reserva}</span> <Glifo tipo={r.dispositivo.tipo} />{' '}
                      <span className="mono">{r.dispositivo.numero_serie}</span>
                      <div className="tenue">
                        <span className="mono">
                          {r.fecha === hoyBogota() ? 'Hoy' : fecha(r.fecha)} {r.hora_inicio}–{r.hora_fin}
                        </span>{' '}
                        · {texto('tipoServicio', r.tipo_servicio)}
                      </div>
                    </div>
                    <button
                      className="boton boton--chico"
                      onClick={() => iniciarReserva(r.id_reserva, r.dispositivo.numero_serie)}
                      disabled={ocupado === `iniciar-${r.id_reserva}`}
                    >
                      Iniciar ahora
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <Vacio>No hay reservas programadas.</Vacio>
            )}
          </Panel>
        </div>

        <div className="demo-col">
          <Panel codigo="03" titulo="Provocar eventos en un dispositivo">
            <div className="chips">
              {m.dispositivos.map((d) => (
                <button
                  key={d.id_dispositivo}
                  className={`chip ${idEvento === d.id_dispositivo ? 'activo' : ''} ${d.servicio ? 'chip--servicio' : ''}`}
                  onClick={() => setIdEvento(d.id_dispositivo)}
                  aria-pressed={idEvento === d.id_dispositivo}
                >
                  <Glifo tipo={d.tipo} />
                  <span className="mono">{d.numero_serie}</span>
                </button>
              ))}
            </div>
            {objetivo && (
              <div className="demo-objetivo">
                <div className="demo-objetivo-cab">
                  <span className="mono serie">{objetivo.numero_serie}</span>
                  <Estado grupo="estadoDispositivo" valor={objetivo.estado} />
                  <span className="tenue">{t ? texto('faseServicio', t.estado_servicio) : 'Sin lectura'}</span>
                  {!objetivo.servicio && <span className="tenue">· las alertas solo se generan en servicio</span>}
                </div>
                <div className="demo-objetivo-lectura">
                  <Bateria nivel={t?.nivel_bateria} />
                  {t && <Sensores sensores={t.sensores} />}
                </div>
              </div>
            )}

            <div className="controles">
              <div className="control">
                <div className="control-titulo">
                  <span className="mono">BATERIA</span> Fijar nivel de batería
                </div>
                <div className="entrada-con-boton">
                  <input type="number" min={0} max={100} value={nivel} onChange={(e) => setNivel(e.target.value)} aria-label="Nivel de batería" />
                  {[19, 28, 80].map((n) => (
                    <button key={n} type="button" className={`boton boton--fantasma ${nivel === String(n) ? 'activo' : ''}`} onClick={() => setNivel(String(n))}>
                      {n}%
                    </button>
                  ))}
                  <button className="boton boton--primario" disabled={!objetivo || !!ocupado} onClick={() => evento({ tipo: 'BATERIA', nivel: Number(nivel) }, `Batería ${nivel} %`)}>
                    Aplicar
                  </button>
                </div>
              </div>

              <div className="control">
                <div className="control-titulo">
                  <span className="mono">FALLA_SENSOR · REPARAR_SENSOR</span> Sensores
                </div>
                <div className="entrada-con-boton">
                  <select value={sensor} onChange={(e) => setSensor(e.target.value)} aria-label="Sensor">
                    {sensores.map((s) => (
                      <option key={s.nombre} value={s.nombre}>
                        {s.nombre} · {texto('estadoSensor', s.estado)}
                      </option>
                    ))}
                  </select>
                  <button className="boton boton--acento" disabled={!objetivo || !sensor || !!ocupado} onClick={() => evento({ tipo: 'FALLA_SENSOR', sensor }, `Falla de ${sensor}`)}>
                    Provocar falla
                  </button>
                  <button className="boton" disabled={!objetivo || !sensor || !!ocupado} onClick={() => evento({ tipo: 'REPARAR_SENSOR', sensor }, `Reparar ${sensor}`)}>
                    Reparar
                  </button>
                </div>
              </div>

              <div className="control">
                <div className="control-titulo">
                  <span className="mono">PAUSAR · REANUDAR</span> Movimiento (para mostrar el retraso)
                </div>
                <div className="entrada-con-boton">
                  <button className="boton" disabled={!objetivo || !!ocupado} onClick={() => evento({ tipo: 'PAUSAR' }, 'Pausar')}>
                    Pausar
                  </button>
                  <button className="boton" disabled={!objetivo || !!ocupado} onClick={() => evento({ tipo: 'REANUDAR' }, 'Reanudar')}>
                    Reanudar
                  </button>
                </div>
              </div>
            </div>
            <p className="tenue nota-pie">El efecto se ve en el siguiente ciclo de monitoreo (≤ {m.intervaloSeg} s).</p>
          </Panel>

          <Panel codigo="04" titulo="Ejecutar tareas ahora">
            <ul className="tareas">
              {TAREAS.map((x) => (
                <li key={x.nombre}>
                  <div>
                    <strong>{x.titulo}</strong>
                    <div className="tenue">{x.texto}</div>
                  </div>
                  <button className="boton boton--chico" disabled={ocupado === x.nombre} onClick={() => tarea(x.nombre, x.titulo)}>
                    Ejecutar
                  </button>
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        <div className="demo-col demo-col--vivo">
          <Panel codigo="EN VIVO" titulo="Mapa" cuerpo={false} className="demo-mapa">
            <MapaMonitoreo
              compacto
              dispositivos={m.dispositivos}
              estelas={m.estelas}
              alertas={m.alertas}
              ubicaciones={m.ubicaciones}
              seleccionado={idEvento}
              onSeleccionar={(id) => id != null && setIdEvento(id)}
            />
          </Panel>
          <Panel codigo="LOG" titulo="Consola" cuerpo={false} className="demo-consola">
            {m.registro.length === 0 ? (
              <Vacio>Los comandos y los eventos del servidor aparecen aquí.</Vacio>
            ) : (
              <ol className="consola">
                {m.registro.map((r) => (
                  <li key={r.id} className={`reg reg--${r.clase}`}>
                    <span className="mono">{r.hora}</span>
                    <span className="reg-clase">{r.clase === 'comando' ? '→' : r.clase === 'error' ? '×' : '←'}</span>
                    <span>{r.texto}</span>
                  </li>
                ))}
              </ol>
            )}
          </Panel>
        </div>
      </div>
    </Pagina>
  );
}
