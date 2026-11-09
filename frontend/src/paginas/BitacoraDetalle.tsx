import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/servicios';
import { Bateria, Cargando, Causa, Dato, ErrorApiVista, Estado, Glifo, Pagina, Panel, Sensores, Vacio, useCarga } from '../componentes/ui';
import { MapaRuta } from '../mapa/MapaRuta';
import { useMonitoreo } from '../tiempoReal/MonitoreoContext';
import { duracion, fechaHora, hora, minutosEntre, numero, texto } from '../utils/formato';

export function BitacoraDetalle() {
  const { id } = useParams();
  const { ubicaciones } = useMonitoreo();
  const det = useCarga(() => api.bitacora(id!), [id]);
  const ruta = useCarga(() => api.ruta(id!), [id]);
  const [indice, setIndice] = useState<number | null>(null);
  const [reproduciendo, setReproduciendo] = useState(false);
  const [incidenciaActiva, setIncidenciaActiva] = useState<number | null>(null);
  const reloj = useRef<number>();

  const abierta = det.datos && det.datos.estado !== 'FINALIZADO';
  const puntos = ruta.datos?.puntos ?? [];
  const ultimo = Math.max(0, puntos.length - 1);
  const i = indice == null ? ultimo : Math.min(indice, ultimo);

  // Mientras el servicio siga abierto, la ruta y la bitácora se refrescan con el ciclo de monitoreo (5 s).
  useEffect(() => {
    if (!abierta) return;
    const t = window.setInterval(() => {
      ruta.recargar();
      det.recargar();
    }, 5000);
    return () => window.clearInterval(t);
  }, [abierta, ruta.recargar, det.recargar]);

  // Reproducción del recorrido punto a punto.
  useEffect(() => {
    if (!reproduciendo) return;
    reloj.current = window.setInterval(() => {
      setIndice((x) => {
        const sig = (x ?? 0) + 1;
        if (sig >= ultimo) {
          setReproduciendo(false);
          return ultimo;
        }
        return sig;
      });
    }, 160);
    return () => window.clearInterval(reloj.current);
  }, [reproduciendo, ultimo]);

  if (det.cargando && !det.datos) return <Cargando />;
  if (det.error)
    return (
      <Pagina codigo="RF08" titulo="Bitácora">
        <ErrorApiVista error={det.error} />
      </Pagina>
    );
  const b = det.datos!;
  const punto = puntos[i];
  const resaltar = [b.reserva.origen.id_ubicacion, b.reserva.destino.id_ubicacion];

  const alternar = () => {
    if (reproduciendo) setReproduciendo(false);
    else {
      if (i >= ultimo) setIndice(0);
      setReproduciendo(true);
    }
  };

  return (
    <Pagina
      ancho="completo"
      codigo={`RF08 · Bitácora #${b.id_bitacora}`}
      titulo={`${b.dispositivo.numero_serie} · ${texto('tipoServicio', b.tipo_servicio)}`}
      subtitulo={
        <span className="fila-gap">
          <Estado grupo="estadoBitacora" valor={b.estado} />
          <span className="mono">
            {fechaHora(b.hora_salida)} → {b.hora_regreso ? hora(b.hora_regreso, false) : 'en curso'}
          </span>
          <span>
            {b.reserva.origen.nombre} → {b.reserva.destino.nombre}
          </span>
        </span>
      }
      acciones={
        <>
          {abierta && (
            <Link className="boton" to={`/monitoreo?d=${b.dispositivo.id_dispositivo}`}>
              Ver en vivo
            </Link>
          )}
          <Link className="boton boton--fantasma" to="/bitacoras">
            ← Bitácoras
          </Link>
        </>
      }
    >
      <div className="bitacora">
        <section className="bitacora-mapa panel">
          <header className="panel-cab">
            <span className="panel-codigo">Ruta</span>
            <h2 className="panel-titulo">Recorrido · {puntos.length} puntos</h2>
            <div className="panel-acciones">
              {abierta && <span className="estado estado--en_curso">Actualizando</span>}
            </div>
          </header>
          {puntos.length === 0 ? (
            <Vacio>{ruta.cargando ? 'Cargando ruta…' : 'Todavía no hay puntos registrados.'}</Vacio>
          ) : (
            <>
              <MapaRuta
                puntos={puntos}
                indice={i}
                incidencias={b.incidencias}
                ubicaciones={ubicaciones}
                resaltar={resaltar}
                tipo={b.dispositivo.tipo}
                etiqueta={b.dispositivo.numero_serie}
                incidenciaActiva={incidenciaActiva}
              />
              <div className="reproductor">
                <button className="boton boton--primario" onClick={alternar} aria-label={reproduciendo ? 'Pausar' : 'Reproducir recorrido'}>
                  {reproduciendo ? 'Pausa' : 'Reproducir'}
                </button>
                <input
                  type="range"
                  min={0}
                  max={ultimo}
                  value={i}
                  onChange={(e) => {
                    setReproduciendo(false);
                    setIndice(Number(e.target.value));
                  }}
                  aria-label="Punto del recorrido"
                />
                <span className="mono reproductor-pos">
                  {String(i + 1).padStart(3, '0')}/{String(puntos.length).padStart(3, '0')}
                </span>
              </div>
              {punto && (
                <dl className="lectura">
                  <div>
                    <dt>Hora</dt>
                    <dd className="mono">{hora(punto.fecha_hora)}</dd>
                  </div>
                  <div>
                    <dt>Fase</dt>
                    <dd>{texto('faseServicio', punto.estado_servicio)}</dd>
                  </div>
                  <div>
                    <dt>Batería</dt>
                    <dd>
                      <Bateria nivel={punto.nivel_bateria} compacta />
                    </dd>
                  </div>
                  <div>
                    <dt>Posición</dt>
                    <dd className="mono">
                      {punto.latitud.toFixed(5)}, {punto.longitud.toFixed(5)}
                    </dd>
                  </div>
                  <div className="lectura-ancha">
                    <dt>Sensores</dt>
                    <dd>
                      <Sensores sensores={punto.sensores} />
                    </dd>
                  </div>
                </dl>
              )}
            </>
          )}
        </section>

        <div className="bitacora-lateral">
          <Panel codigo="01" titulo="Registro del servicio">
            <dl className="datos datos--compactos">
              <Dato etiqueta="Dispositivo">
                <Link to={`/inventario/${b.dispositivo.id_dispositivo}`} className="serie-enlace">
                  <Glifo tipo={b.dispositivo.tipo} /> <span className="mono">{b.dispositivo.numero_serie}</span>
                </Link>{' '}
                · {b.dispositivo.modelo}
              </Dato>
              <Dato etiqueta="Operador responsable">{b.operador.nombre}</Dato>
              <Dato etiqueta="Salida" mono>
                {fechaHora(b.hora_salida, true)}
              </Dato>
              <Dato etiqueta="Regreso" mono>
                {b.hora_regreso ? fechaHora(b.hora_regreso, true) : '—'}
              </Dato>
              <Dato etiqueta="Duración" mono>
                {b.hora_regreso ? duracion(minutosEntre(b.hora_salida, b.hora_regreso)) : '—'}
              </Dato>
              <Dato etiqueta="Horas de uso" mono>
                {b.horas_uso == null ? '—' : `${numero(b.horas_uso, 2)} h`}
              </Dato>
              <Dato etiqueta="Reserva">
                <Link to={`/reservas/${b.id_reserva}`} className="mono">
                  #{b.id_reserva}
                </Link>{' '}
                <span className="mono tenue">
                  {b.reserva.hora_inicio}–{b.reserva.hora_fin}
                </span>
              </Dato>
            </dl>
          </Panel>

          <Panel codigo="02" titulo={`Incidencias · ${b.incidencias.length}`}>
            {b.incidencias.length === 0 ? (
              <Vacio>Servicio sin incidencias.</Vacio>
            ) : (
              <ul className="incidencias">
                {b.incidencias.map((x) => (
                  <li key={x.id_incidencia}>
                    <button className={incidenciaActiva === x.id_incidencia ? 'activo' : ''} onClick={() => setIncidenciaActiva(x.id_incidencia)}>
                      <span className="incidencia-cab">
                        <Causa valor={x.tipo} grupo="tipoIncidencia" />
                        <span className="mono tenue">{hora(x.fecha_hora)}</span>
                      </span>
                      <span>{x.descripcion}</span>
                    </button>
                    {x.id_alerta && (
                      <Link to={`/alertas/${x.id_alerta}`} className="mono incidencia-alerta">
                        Alerta #{x.id_alerta}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel codigo="03" titulo="Video del servicio">
            {b.video ? (
              <div className="video-ficha">
                <div className="video-cinta" aria-hidden>
                  {Array.from({ length: 14 }, (_, k) => (
                    <span key={k} />
                  ))}
                </div>
                <dl className="datos datos--compactos">
                  <Dato etiqueta="Archivo" mono>
                    video-{b.video.id_video}.mp4
                  </Dato>
                  <Dato etiqueta="Grabado" mono>
                    {fechaHora(b.video.fecha_grabacion)}
                  </Dato>
                  <Dato etiqueta="Duración" mono>
                    {b.video.duracion_seg == null ? '—' : duracion(b.video.duracion_seg / 60)}
                  </Dato>
                  <Dato etiqueta="Estado">{b.video.eliminado ? `Eliminado ${fechaHora(b.video.fecha_eliminacion)}` : 'Almacenado en la nube'}</Dato>
                </dl>
              </div>
            ) : (
              <Vacio>{abierta ? 'Se guarda al cerrar el servicio.' : 'El video aún no se ha guardado.'}</Vacio>
            )}
          </Panel>
        </div>
      </div>
    </Pagina>
  );
}
