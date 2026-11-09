import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ErrorApi } from '../api/cliente';
import { glifo } from '../mapa/glifos';
import { fecha, hora, texto, type GrupoTexto } from '../utils/formato';

// ------------------------------------------------------------------ Carga de datos

export function useCarga<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [datos, setDatos] = useState<T | null>(null);
  const [error, setError] = useState<ErrorApi | null>(null);
  const [cargando, setCargando] = useState(true);
  const [version, setVersion] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    let vigente = true;
    setCargando(true);
    fnRef
      .current()
      .then((d) => {
        if (!vigente) return;
        setDatos(d);
        setError(null);
      })
      .catch((e) => {
        if (!vigente) return;
        setError(e instanceof ErrorApi ? e : new ErrorApi(0, 'ERROR', String(e?.message ?? e)));
      })
      .finally(() => vigente && setCargando(false));
    return () => {
      vigente = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  const recargar = useCallback(() => setVersion((v) => v + 1), []);
  return { datos, error, cargando, recargar, setDatos };
}

// ------------------------------------------------------------------ Estructura

export function Pagina({ codigo, titulo, subtitulo, acciones, children, ancho }: {
  codigo: string;
  titulo: string;
  subtitulo?: ReactNode;
  acciones?: ReactNode;
  children: ReactNode;
  ancho?: 'completo';
}) {
  return (
    <div className={`pagina ${ancho === 'completo' ? 'pagina--completa' : ''}`}>
      <header className="pagina-cab">
        <div>
          <div className="pagina-codigo">{codigo}</div>
          <h1 className="pagina-titulo">{titulo}</h1>
          {subtitulo && <div className="pagina-sub">{subtitulo}</div>}
        </div>
        {acciones && <div className="pagina-acciones">{acciones}</div>}
      </header>
      {children}
    </div>
  );
}

export function Panel({ titulo, codigo, acciones, children, className = '', cuerpo = true }: {
  titulo: ReactNode;
  codigo?: string;
  acciones?: ReactNode;
  children: ReactNode;
  className?: string;
  cuerpo?: boolean;
}) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-cab">
        {codigo && <span className="panel-codigo">{codigo}</span>}
        <h2 className="panel-titulo">{titulo}</h2>
        {acciones && <div className="panel-acciones">{acciones}</div>}
      </header>
      {cuerpo ? <div className="panel-cuerpo">{children}</div> : children}
    </section>
  );
}

export function Dato({ etiqueta, children, mono }: { etiqueta: string; children: ReactNode; mono?: boolean }) {
  return (
    <div className="dato">
      <dt>{etiqueta}</dt>
      <dd className={mono ? 'mono' : undefined}>{children}</dd>
    </div>
  );
}

// ------------------------------------------------------------------ Estados

export function Estado({ grupo, valor }: { grupo: GrupoTexto; valor: string | null | undefined }) {
  if (!valor) return <span className="tenue">—</span>;
  return <span className={`estado estado--${valor.toLowerCase()}`}>{texto(grupo, valor)}</span>;
}

export function Causa({ valor, grupo = 'causaAlerta' }: { valor: string | null | undefined; grupo?: GrupoTexto }) {
  return <span className="causa">{texto(grupo, valor)}</span>;
}

export function Glifo({ tipo, className = '' }: { tipo: string; className?: string }) {
  return (
    <span
      className={`glifo-en-linea ${className}`}
      title={texto('tipoDispositivo', tipo)}
      dangerouslySetInnerHTML={{ __html: glifo(tipo) }}
    />
  );
}

export function Serie({ id, serie, tipo, enlace = true }: { id?: number; serie: string; tipo?: string; enlace?: boolean }) {
  const contenido = (
    <>
      {tipo && <Glifo tipo={tipo} />}
      <span className="mono serie">{serie}</span>
    </>
  );
  return enlace && id != null ? (
    <Link className="serie-enlace" to={`/inventario/${id}`} onClick={(e) => e.stopPropagation()}>
      {contenido}
    </Link>
  ) : (
    <span className="serie-enlace">{contenido}</span>
  );
}

/** Medidor de batería segmentado: 10 celdas; bajo 30 % pasa al acento y bajo 20 % parpadea la última celda. */
export function Bateria({ nivel, compacta }: { nivel: number | null | undefined; compacta?: boolean }) {
  if (nivel == null) return <span className="tenue mono">—</span>;
  const n = Math.max(0, Math.min(100, Math.round(nivel)));
  const llenas = Math.ceil(n / 10);
  const rango = n < 20 ? 'critica' : n < 30 ? 'baja' : 'ok';
  return (
    <span className={`bateria bateria--${rango} ${compacta ? 'bateria--compacta' : ''}`} title={`Batería ${n} %`}>
      <span className="bateria-celdas" aria-hidden>
        {Array.from({ length: 10 }, (_, i) => (
          <span key={i} className={i < llenas ? 'llena' : ''} />
        ))}
      </span>
      <span className="bateria-valor">{n}%</span>
    </span>
  );
}

export function Sensores({ sensores }: { sensores: { nombre: string; estado: string }[] }) {
  return (
    <span className="sensores">
      {sensores.map((s) => (
        <span key={s.nombre} className={`sensor ${s.estado === 'FALLA' ? 'sensor--falla' : ''}`} title={`${s.nombre}: ${texto('estadoSensor', s.estado)}`}>
          <i />
          {s.nombre}
        </span>
      ))}
    </span>
  );
}

export function HoraReserva({ f, inicio, fin }: { f: string; inicio: string; fin: string }) {
  return (
    <span className="mono">
      {fecha(f)} <span className="tenue">·</span> {inicio}–{fin}
    </span>
  );
}

export function Hora({ iso }: { iso: string | null | undefined }) {
  return <span className="mono">{hora(iso)}</span>;
}

// ------------------------------------------------------------------ Mensajes

export function Cargando({ texto: t = 'Cargando' }: { texto?: string }) {
  return (
    <div className="cargando" role="status">
      <span className="cargando-barra" />
      {t}…
    </div>
  );
}

export function Vacio({ children }: { children: ReactNode }) {
  return <div className="vacio">{children}</div>;
}

/**
 * Muestra un error de la API con el detalle que corresponde a su código: CRUCE_HORARIO (reserva en conflicto),
 * DISPOSITIVO_NO_APTO (motivos) y VALIDACION (campos que no están en el formulario).
 */
export function ErrorApiVista({ error, camposVisibles = [] }: { error: ErrorApi | null; camposVisibles?: string[] }) {
  if (!error) return null;
  const d = error.detalles ?? {};
  const conflicto = d.reserva_en_conflicto as
    | { id_reserva: number; fecha?: string; hora_inicio?: string; hora_fin?: string; tipo_servicio?: string; estado?: string; operador?: { nombre: string } }
    | undefined;
  const motivos = (d.motivos as string[] | undefined) ?? [];
  const otrosCampos = Object.entries(error.campos).filter(([c]) => !camposVisibles.includes(c));
  const titulo: Record<string, string> = {
    CRUCE_HORARIO: 'Cruce de horario',
    DISPOSITIVO_NO_APTO: 'Dispositivo no apto',
    TIPO_DISPOSITIVO_INCORRECTO: 'Tipo de dispositivo incorrecto',
    VALIDACION: 'Revise los datos',
    DUPLICADO: 'Ya existe',
    REGLA_NEGOCIO: 'No se puede completar',
    SIN_PERMISO: 'Sin permiso',
    NO_ENCONTRADO: 'No encontrado',
    SERVICIO_NO_DISPONIBLE: 'Servicio no disponible',
    SIN_CONEXION: 'Sin conexión',
  };
  return (
    <div className="error-api" role="alert">
      <div className="error-api-cab">
        <span className="error-api-codigo">{error.codigo}</span>
        <strong>{titulo[error.codigo] ?? 'Error'}</strong>
      </div>
      <p>{error.mensaje}</p>
      {conflicto && (
        <div className="conflicto">
          <span className="tenue">Reserva en conflicto</span>
          <Link to={`/reservas/${conflicto.id_reserva}`} className="mono">
            #{conflicto.id_reserva}
          </Link>
          {conflicto.fecha && (
            <span className="mono">
              {fecha(conflicto.fecha)} · {conflicto.hora_inicio}–{conflicto.hora_fin}
            </span>
          )}
          {conflicto.tipo_servicio && <span>{texto('tipoServicio', conflicto.tipo_servicio)}</span>}
          {conflicto.operador && <span>{conflicto.operador.nombre}</span>}
          {conflicto.estado && <Estado grupo="estadoReserva" valor={conflicto.estado} />}
        </div>
      )}
      {motivos.length > 0 && (
        <ul className="motivos">
          {motivos.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      )}
      {otrosCampos.length > 0 && (
        <ul className="motivos">
          {otrosCampos.map(([c, m]) => (
            <li key={c}>
              <span className="mono">{c}</span>: {m}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Advertencias({ lista }: { lista?: { codigo: string; mensaje: string }[] }) {
  if (!lista?.length) return null;
  return (
    <div className="advertencias">
      {lista.map((a) => (
        <div key={a.codigo + a.mensaje} className="advertencia">
          <span className="mono">{a.codigo}</span> {a.mensaje}
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ Formularios

export function Campo({ etiqueta, error, children, ayuda, ancho, grupo }: {
  etiqueta: string;
  error?: string;
  children: ReactNode;
  ayuda?: ReactNode;
  ancho?: 'doble' | 'completo';
  /** Para controles con botones dentro (segmentos, tarjetas): se usa un grupo y no un <label>. */
  grupo?: boolean;
}) {
  const clase = `campo ${error ? 'campo--error' : ''} ${ancho ? `campo--${ancho}` : ''}`;
  const contenido = (
    <>
      <span className="campo-etiqueta">{etiqueta}</span>
      {children}
      {error ? <span className="campo-error">{error}</span> : ayuda ? <span className="campo-ayuda">{ayuda}</span> : null}
    </>
  );
  return grupo ? (
    <div className={clase} role="group" aria-label={etiqueta}>
      {contenido}
    </div>
  ) : (
    <label className={clase}>{contenido}</label>
  );
}

export function Segmentos<T extends string>({ opciones, valor, onCambio, nombre }: {
  opciones: { valor: T; texto: ReactNode }[];
  valor: T;
  onCambio: (v: T) => void;
  nombre: string;
}) {
  return (
    <div className="segmentos" role="radiogroup" aria-label={nombre}>
      {opciones.map((o) => (
        <button
          type="button"
          key={o.valor}
          role="radio"
          aria-checked={valor === o.valor}
          className={valor === o.valor ? 'activo' : ''}
          onClick={() => onCambio(o.valor)}
        >
          {o.texto}
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ Paginación

export const LIMITE = 25;

export function Paginacion({ total, limite, desplazamiento, onCambio }: {
  total: number;
  limite: number;
  desplazamiento: number;
  onCambio: (d: number) => void;
}) {
  if (total === 0) return null;
  const desde = desplazamiento + 1;
  const hasta = Math.min(desplazamiento + limite, total);
  return (
    <div className="paginacion">
      <span className="mono">
        {desde}–{hasta} <span className="tenue">de</span> {total}
      </span>
      <div>
        <button className="boton boton--fantasma" disabled={desplazamiento === 0} onClick={() => onCambio(Math.max(0, desplazamiento - limite))}>
          ← Anterior
        </button>
        <button className="boton boton--fantasma" disabled={hasta >= total} onClick={() => onCambio(desplazamiento + limite)}>
          Siguiente →
        </button>
      </div>
    </div>
  );
}
