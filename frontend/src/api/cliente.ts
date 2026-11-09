// Cliente HTTP: agrega el token, traduce el formato de error {error:{codigo,mensaje,detalles}} y cierra la
// sesión ante cualquier 401 (docs/guia-frontend.md, secciones 2 y 3).

const CLAVE_TOKEN = 'torre.token';
const CLAVE_EXPIRA = 'torre.expira';

/** Base de la API. Vacía = mismo origen (el proxy de Vite reenvía /api y /health al backend). */
export const API_BASE: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? '';

function leer(clave: string): string | null {
  try {
    return sessionStorage.getItem(clave);
  } catch {
    return null;
  }
}

function escribir(clave: string, valor: string | null) {
  try {
    if (valor) sessionStorage.setItem(clave, valor);
    else sessionStorage.removeItem(clave);
  } catch {
    /* almacenamiento bloqueado: la sesión dura lo que dure la pestaña */
  }
}

let token: string | null = leer(CLAVE_TOKEN);
let expira: string | null = leer(CLAVE_EXPIRA);
let alPerderSesion: (() => void) | null = null;

export function obtenerToken() {
  return token;
}

export function obtenerExpiracion() {
  return expira;
}

export function fijarToken(nuevo: string | null, vence: string | null = null) {
  token = nuevo;
  expira = nuevo ? vence : null;
  escribir(CLAVE_TOKEN, token);
  escribir(CLAVE_EXPIRA, expira);
}

/** Registra qué hacer cuando la API responde 401 (token ausente, vencido o usuario desactivado). */
export function registrarPerdidaDeSesion(fn: () => void) {
  alPerderSesion = fn;
}

export interface CampoInvalido {
  campo: string;
  mensaje: string;
}

export class ErrorApi extends Error {
  constructor(
    public estado: number,
    public codigo: string,
    mensaje: string,
    public detalles: Record<string, unknown> | null = null,
  ) {
    super(mensaje);
    this.name = 'ErrorApi';
  }

  /** El `mensaje` de la API, en español y listo para mostrar. */
  get mensaje(): string {
    return this.message;
  }

  /** Errores de VALIDACION indexados por nombre de campo. */
  get campos(): Record<string, string> {
    const lista = (this.detalles?.campos as CampoInvalido[] | undefined) ?? [];
    const salida: Record<string, string> = {};
    for (const c of lista) {
      const nombre = String(c.campo).split('.').pop() ?? String(c.campo);
      salida[nombre] = salida[nombre] ? `${salida[nombre]} ${c.mensaje}` : c.mensaje;
    }
    return salida;
  }
}

const MENSAJES_HTTP: Record<number, string> = {
  401: 'Su sesión no es válida. Ingrese de nuevo.',
  403: 'Su rol no tiene permiso para esta acción.',
  404: 'No se encontró lo que buscaba.',
  500: 'Ocurrió un error en el servidor. Intente de nuevo.',
  502: 'El servidor no responde.',
  503: 'Un servicio del sistema no está disponible en este momento.',
};

type Valor = string | number | boolean | null | undefined;

export interface Opciones {
  metodo?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  cuerpo?: unknown;
  params?: Record<string, Valor>;
  /** No envía el token ni cierra la sesión ante un 401 (login, /health). */
  publico?: boolean;
  signal?: AbortSignal;
}

export function construirUrl(ruta: string, params?: Record<string, Valor>) {
  const qs = new URLSearchParams();
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') qs.set(k, String(v));
    }
  }
  const q = qs.toString();
  return `${API_BASE}${ruta}${q ? `?${q}` : ''}`;
}

export async function pedir<T>(ruta: string, op: Opciones = {}): Promise<T> {
  const cabeceras: Record<string, string> = { Accept: 'application/json' };
  if (op.cuerpo !== undefined) cabeceras['Content-Type'] = 'application/json';
  if (token && !op.publico) cabeceras.Authorization = `Bearer ${token}`;

  let resp: Response;
  try {
    resp = await fetch(construirUrl(ruta, op.params), {
      method: op.metodo ?? 'GET',
      headers: cabeceras,
      body: op.cuerpo !== undefined ? JSON.stringify(op.cuerpo) : undefined,
      signal: op.signal,
    });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ErrorApi(
      0,
      'SIN_CONEXION',
      'No hay conexión con el servidor. Revise que el backend esté encendido (docker compose up -d).',
    );
  }

  const texto = await resp.text();
  let datos: unknown = null;
  if (texto) {
    try {
      datos = JSON.parse(texto);
    } catch {
      datos = null;
    }
  }

  if (!resp.ok) {
    const e = (datos as { error?: { codigo?: string; mensaje?: string; detalles?: Record<string, unknown> } })?.error;
    const error = new ErrorApi(
      resp.status,
      e?.codigo ?? `HTTP_${resp.status}`,
      e?.mensaje ?? MENSAJES_HTTP[resp.status] ?? `Error ${resp.status}`,
      e?.detalles ?? null,
    );
    if (resp.status === 401 && !op.publico) {
      fijarToken(null);
      alPerderSesion?.();
    }
    throw error;
  }
  return datos as T;
}
