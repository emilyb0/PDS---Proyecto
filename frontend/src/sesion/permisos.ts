import type { Sesion } from '../api/tipos';

// Cada pantalla se muestra solo si TODOS sus RF están en requisitos_activos y su función está en funciones
// (docs/guia-frontend.md, secciones 0 y 3). Cuando lleguen los módulos de la entrega 2, se agregan aquí.

export type Pantalla =
  | 'monitoreo'
  | 'inventario'
  | 'dispositivoNuevo'
  | 'reservas'
  | 'reservaNueva'
  | 'bitacoras'
  | 'alertas'
  | 'usuarios'
  | 'desactivarUsuario'
  | 'auditoria'
  | 'demo';

export const PANTALLAS: Record<Pantalla, { rf: string[]; funcion: string }> = {
  monitoreo: { rf: ['RF09', 'RF10'], funcion: 'monitoreo.ver' },
  inventario: { rf: ['RF04'], funcion: 'inventario.ver' },
  dispositivoNuevo: { rf: ['RF01'], funcion: 'inventario.gestionar' },
  reservas: { rf: ['RF05'], funcion: 'reservas.ver' },
  reservaNueva: { rf: ['RF05'], funcion: 'reservas.gestionar' },
  bitacoras: { rf: ['RF08'], funcion: 'bitacoras.ver' },
  alertas: { rf: ['RF11'], funcion: 'alertas.ver' },
  usuarios: { rf: ['RF18'], funcion: 'usuarios.gestionar' },
  // RF19 (fuera del alcance): el botón solo aparecería si el backend activara RF19; hoy queda oculto.
  desactivarUsuario: { rf: ['RF18', 'RF19'], funcion: 'usuarios.gestionar' },
  // RNF09 no es un RF: depende solo de la función.
  auditoria: { rf: [], funcion: 'auditoria.ver' },
  demo: { rf: [], funcion: 'demo.usar' },
};

export function permitido(sesion: Sesion | null, pantalla: Pantalla): boolean {
  if (!sesion) return false;
  const p = PANTALLAS[pantalla];
  return sesion.funciones.includes(p.funcion) && p.rf.every((rf) => sesion.requisitos_activos.includes(rf));
}

export interface EntradaMenu {
  pantalla: Pantalla;
  ruta: string;
  codigo: string;
  etiqueta: string;
  grupo: 'operacion' | 'registro' | 'administracion';
}

export const MENU: EntradaMenu[] = [
  { pantalla: 'monitoreo', ruta: '/monitoreo', codigo: 'MON', etiqueta: 'Monitoreo', grupo: 'operacion' },
  { pantalla: 'alertas', ruta: '/alertas', codigo: 'ALR', etiqueta: 'Alertas', grupo: 'operacion' },
  { pantalla: 'reservas', ruta: '/reservas', codigo: 'RSV', etiqueta: 'Reservas', grupo: 'operacion' },
  { pantalla: 'inventario', ruta: '/inventario', codigo: 'INV', etiqueta: 'Inventario', grupo: 'registro' },
  { pantalla: 'bitacoras', ruta: '/bitacoras', codigo: 'BIT', etiqueta: 'Bitácoras', grupo: 'registro' },
  { pantalla: 'usuarios', ruta: '/usuarios', codigo: 'USR', etiqueta: 'Usuarios', grupo: 'administracion' },
  { pantalla: 'auditoria', ruta: '/auditoria', codigo: 'AUD', etiqueta: 'Auditoría', grupo: 'administracion' },
  { pantalla: 'demo', ruta: '/demo', codigo: 'DEM', etiqueta: 'Panel de demo', grupo: 'administracion' },
];
