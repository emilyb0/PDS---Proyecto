// Fechas en hora de Bogotá y textos de las enumeraciones (docs/guia-frontend.md, secciones 1 y 4).

export const ZONA = 'America/Bogota';
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const DIAS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];

/**
 * Convierte un ISO del backend a Date. Si viene sin desfase se asume Bogotá (-05:00), como dice la guía.
 * Recorta las fracciones de segundo a milisegundos para que todos los navegadores lo lean igual.
 */
export function aFecha(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  let s = iso.trim().replace(/(\.\d{3})\d+/, '$1');
  if (!/T/.test(s)) s = `${s}T00:00:00`;
  if (!/([zZ]|[+-]\d{2}:?\d{2})$/.test(s)) s = `${s}-05:00`;
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
}

const partesFmt = new Intl.DateTimeFormat('en-CA', {
  timeZone: ZONA,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  weekday: 'short',
  hourCycle: 'h23',
});

const DIA_SEMANA: Record<string, number> = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };

function partes(d: Date) {
  const p: Record<string, string> = {};
  for (const x of partesFmt.formatToParts(d)) p[x.type] = x.value;
  return {
    anio: p.year,
    mes: Number(p.month),
    dia: p.day,
    hora: p.hour === '24' ? '00' : p.hour,
    minuto: p.minute,
    segundo: p.second,
    semana: DIA_SEMANA[p.weekday] ?? 0,
  };
}

/** "09 nov 2026 · 10:30" */
export function fechaHora(iso: string | null | undefined, conSegundos = false): string {
  const d = aFecha(iso);
  if (!d) return '—';
  const p = partes(d);
  return `${p.dia} ${MESES[p.mes - 1]} ${p.anio} · ${p.hora}:${p.minuto}${conSegundos ? `:${p.segundo}` : ''}`;
}

/** "10:30:05" o "10:30" */
export function hora(iso: string | null | undefined, conSegundos = true): string {
  const d = aFecha(iso);
  if (!d) return '—';
  const p = partes(d);
  return conSegundos ? `${p.hora}:${p.minuto}:${p.segundo}` : `${p.hora}:${p.minuto}`;
}

/** Fecha sola "2026-11-09" → "lun 09 nov 2026" */
export function fecha(f: string | null | undefined, conDia = false): string {
  if (!f) return '—';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(f);
  if (!m) return f;
  const [, a, mm, dd] = m;
  const base = `${dd} ${MESES[Number(mm) - 1]} ${a}`;
  if (!conDia) return base;
  const dia = new Date(Date.UTC(Number(a), Number(mm) - 1, Number(dd))).getUTCDay();
  return `${DIAS[dia]} ${base}`;
}

/** Fecha de hoy en Bogotá "YYYY-MM-DD". */
export function hoyBogota(desplazarDias = 0): string {
  const p = partes(new Date(Date.now() + desplazarDias * 86400000));
  return `${p.anio}-${String(p.mes).padStart(2, '0')}-${p.dia}`;
}

/** Hora actual en Bogotá "HH:MM" (o con segundos). */
export function horaBogota(conSegundos = false): string {
  const p = partes(new Date());
  return conSegundos ? `${p.hora}:${p.minuto}:${p.segundo}` : `${p.hora}:${p.minuto}`;
}

/** "hace 3 s", "hace 2 min" */
export function haceCuanto(ms: number | null | undefined, ahora = Date.now()): string {
  if (ms == null) return '—';
  const s = Math.max(0, Math.round((ahora - ms) / 1000));
  if (s < 60) return `hace ${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `hace ${m} min`;
  const h = Math.floor(m / 60);
  return `hace ${h} h`;
}

/** 95 → "1 h 35 min" */
export function duracion(min: number | null | undefined): string {
  if (min == null) return '—';
  const total = Math.round(min);
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${m} min`;
}

export function minutosEntre(a: string | null | undefined, b: string | null | undefined): number | null {
  const x = aFecha(a);
  const y = aFecha(b);
  if (!x || !y) return null;
  return (y.getTime() - x.getTime()) / 60000;
}

export function numero(n: number | null | undefined, decimales = 0): string {
  if (n == null) return '—';
  return n.toLocaleString('es-CO', { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
}

export function coordenada(n: number | null | undefined): string {
  return n == null ? '—' : n.toFixed(5);
}

// ------------------------------------------------------------------ Textos de las enumeraciones

export const TEXTOS = {
  rol: { ADMINISTRADOR: 'Administrador', OPERADOR: 'Operador' },
  estadoUsuario: { ACTIVO: 'Activo', INACTIVO: 'Inactivo' },
  tipoDispositivo: { ROBOT: 'Robot', DRONE: 'Drone' },
  estadoDispositivo: {
    DISPONIBLE: 'Disponible',
    EN_SERVICIO: 'En servicio',
    EN_CARGA: 'En carga',
    EN_MANTENIMIENTO: 'En mantenimiento',
    FUERA_DE_SERVICIO: 'Fuera de servicio',
  },
  estadoSensor: { OK: 'OK', FALLA: 'En falla' },
  tipoServicio: {
    ENTREGA_DOCUMENTOS: 'Entrega de documentos',
    PEDIDO_CAFETERIA: 'Pedido de cafetería',
    GRABACION_EVENTO: 'Grabación de evento',
  },
  estadoReserva: {
    PROGRAMADA: 'Programada',
    EN_CURSO: 'En curso',
    FINALIZADA: 'Finalizada',
    CANCELADA: 'Cancelada',
  },
  estadoBitacora: {
    EN_CURSO: 'En curso',
    ENTREGADO: 'Entregado',
    RETORNANDO: 'Retornando',
    FINALIZADO: 'Finalizado',
  },
  faseServicio: {
    EN_BASE: 'En base',
    EN_RUTA: 'En ruta',
    EN_DESTINO: 'En destino',
    ESPERANDO_CODIGO: 'Esperando código',
    RETORNANDO: 'Retornando',
    DETENIDO: 'Detenido',
  },
  tipoIncidencia: {
    BATERIA_BAJA: 'Batería baja',
    SENSOR_EN_FALLA: 'Sensor en falla',
    RETRASO: 'Retraso',
    SALIDA_DE_ZONA: 'Fuera de zona',
    ORDEN_RETORNO: 'Orden de retorno',
    PARADA_EMERGENCIA: 'Parada de emergencia',
    ENTREGA_NO_CONFIRMADA: 'Entrega no confirmada',
  },
  causaAlerta: {
    BATERIA_BAJA: 'Batería baja',
    SENSOR_EN_FALLA: 'Sensor en falla',
    RETRASO: 'Retraso',
    SALIDA_DE_ZONA: 'Fuera de zona',
  },
  tipoAlerta: { SERVICIO: 'Servicio', MANTENIMIENTO: 'Mantenimiento' },
  accion: { CREAR: 'Creación', EDITAR: 'Edición', BAJA: 'Baja' },
} as const;

export type GrupoTexto = keyof typeof TEXTOS;

export function texto(grupo: GrupoTexto, valor: string | null | undefined): string {
  if (!valor) return '—';
  return (TEXTOS[grupo] as Record<string, string>)[valor] ?? valor;
}

/** Tipo de dispositivo que exige cada servicio (guía, sección 4). */
export function tipoPara(servicio: string): 'ROBOT' | 'DRONE' {
  return servicio === 'GRABACION_EVENTO' ? 'DRONE' : 'ROBOT';
}

export function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
}
