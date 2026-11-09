import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ErrorApi } from '../api/cliente';
import { api } from '../api/servicios';
import { useAvisos } from '../componentes/Avisos';
import { Advertencias, Cargando, Dato, ErrorApiVista, Estado, Glifo, Pagina, Panel, useCarga } from '../componentes/ui';
import { useSesion } from '../sesion/SesionContext';
import { duracion, fecha, fechaHora, texto } from '../utils/formato';

export function ReservaDetalle() {
  const { id } = useParams();
  const { tiene, puede } = useSesion();
  const { avisar } = useAvisos();
  const navegar = useNavigate();
  const r = useCarga(() => api.reserva(id!), [id]);
  const [error, setError] = useState<ErrorApi | null>(null);
  const [iniciando, setIniciando] = useState(false);

  if (r.cargando && !r.datos) return <Cargando />;
  if (r.error)
    return (
      <Pagina codigo="RF05" titulo="Reserva">
        <ErrorApiVista error={r.error} />
      </Pagina>
    );
  const x = r.datos!;

  const iniciar = async () => {
    setIniciando(true);
    setError(null);
    try {
      const s = await api.demoIniciar(x.id_reserva);
      avisar({ tipo: 'info', rotulo: 'Demo', titulo: `Reserva #${x.id_reserva} iniciada`, texto: s.id_bitacora ? `Bitácora #${s.id_bitacora}` : undefined });
      navegar(`/monitoreo?d=${x.dispositivo.id_dispositivo}`);
    } catch (e) {
      if (e instanceof ErrorApi) setError(e);
      r.recargar();
    } finally {
      setIniciando(false);
    }
  };

  return (
    <Pagina
      codigo={`RF05 · Reserva #${x.id_reserva}`}
      titulo={texto('tipoServicio', x.tipo_servicio)}
      subtitulo={
        <span className="fila-gap">
          <Estado grupo="estadoReserva" valor={x.estado} />
          <span className="mono">
            {fecha(x.fecha, true)} · {x.hora_inicio}–{x.hora_fin}
          </span>
        </span>
      }
      acciones={
        <>
          {tiene('demo.usar') && x.estado === 'PROGRAMADA' && (
            <button className="boton boton--acento" onClick={iniciar} disabled={iniciando}>
              {iniciando ? 'Iniciando…' : 'Iniciar ahora (demo)'}
            </button>
          )}
          {x.id_bitacora && puede('bitacoras') && (
            <Link className="boton" to={`/bitacoras/${x.id_bitacora}`}>
              Bitácora #{x.id_bitacora}
            </Link>
          )}
          <Link className="boton boton--fantasma" to="/reservas">
            ← Reservas
          </Link>
        </>
      }
    >
      <ErrorApiVista error={error} />
      <Advertencias lista={x.advertencias} />
      <div className="rejilla-3">
        <Panel codigo="01" titulo="Servicio">
          <dl className="datos">
            <Dato etiqueta="Tipo">{texto('tipoServicio', x.tipo_servicio)}</Dato>
            <Dato etiqueta="Inicio" mono>
              {fechaHora(x.inicio)}
            </Dato>
            <Dato etiqueta="Fin estimado" mono>
              {fechaHora(x.fin)}
            </Dato>
            <Dato etiqueta="Duración estimada" mono>
              {duracion(x.duracion_estimada_min)}
            </Dato>
            <Dato etiqueta="Origen">{x.origen.nombre}</Dato>
            <Dato etiqueta="Destino">{x.destino.nombre}</Dato>
          </dl>
        </Panel>
        <Panel codigo="02" titulo="Asignación">
          <dl className="datos">
            <Dato etiqueta="Dispositivo">
              <Link to={`/inventario/${x.dispositivo.id_dispositivo}`} className="serie-enlace">
                <Glifo tipo={x.dispositivo.tipo} /> <span className="mono">{x.dispositivo.numero_serie}</span>
              </Link>{' '}
              · {x.dispositivo.modelo}
            </Dato>
            <Dato etiqueta="Operador responsable">{x.operador.nombre}</Dato>
            <Dato etiqueta="Creada por">{x.administrador?.nombre ?? '—'}</Dato>
            <Dato etiqueta="Creada" mono>
              {fechaHora(x.fecha_creacion)}
            </Dato>
            {x.motivo_cambio && <Dato etiqueta="Motivo de cambio">{x.motivo_cambio}</Dato>}
          </dl>
        </Panel>
        <Panel codigo="03" titulo="Código de entrega">
          {x.codigo_entrega ? (
            <>
              <div className="codigo-entrega">
                {x.codigo_entrega.split('').map((c, i) => (
                  <span key={i}>{c}</span>
                ))}
              </div>
              <p className="tenue">Código de 4 dígitos generado al crear la reserva del robot.</p>
            </>
          ) : (
            <p className="tenue">
              {x.dispositivo.tipo === 'DRONE' ? 'Las grabaciones con drone no llevan código de entrega.' : 'Solo el administrador ve el código de entrega.'}
            </p>
          )}
        </Panel>
      </div>
    </Pagina>
  );
}
