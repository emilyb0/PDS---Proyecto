import { construirUrl, pedir } from './cliente';
import type {
  Alerta,
  Bitacora,
  BitacoraDetalle,
  Dispositivo,
  DispositivoCrear,
  DispositivoDetalle,
  EventoDemo,
  LoginRespuesta,
  Monitoreo,
  Pagina,
  RegistroAuditoria,
  Reserva,
  ReservaCrear,
  Rol,
  Ruta,
  Salud,
  Sesion,
  Ubicacion,
  Usuario,
} from './tipos';

type Filtros = Record<string, string | number | boolean | null | undefined>;

export const api = {
  // Sesión (RF20)
  login: (correo: string, contrasena: string) =>
    pedir<LoginRespuesta>('/api/auth/login', { metodo: 'POST', cuerpo: { correo, contrasena }, publico: true }),
  yo: () => pedir<Sesion>('/api/auth/yo'),
  salud: () => pedir<Salud>('/health', { publico: true }),

  // Usuarios (RF18)
  usuarios: (f?: Filtros) => pedir<Pagina<Usuario>>('/api/usuarios', { params: f }),
  crearUsuario: (c: { nombre: string; correo_institucional: string; contrasena: string; rol: Rol }) =>
    pedir<Usuario>('/api/usuarios', { metodo: 'POST', cuerpo: c }),
  editarUsuario: (id: number, c: { nombre?: string; rol?: Rol }) =>
    pedir<Usuario>(`/api/usuarios/${id}`, { metodo: 'PATCH', cuerpo: c }),
  // RF19 (pendiente en el backend): docs/especificacion-backend.md, secciones 7.1 y 8.
  desactivarUsuario: (id: number) => pedir<Usuario>(`/api/usuarios/${id}/desactivar`, { metodo: 'POST' }),

  // Inventario (RF01, RF04)
  dispositivos: (f?: Filtros) => pedir<Pagina<Dispositivo>>('/api/dispositivos', { params: f }),
  dispositivo: (id: number | string) => pedir<DispositivoDetalle>(`/api/dispositivos/${id}`),
  crearDispositivo: (c: DispositivoCrear) =>
    pedir<DispositivoDetalle>('/api/dispositivos', { metodo: 'POST', cuerpo: c }),

  // Reservas (RF05–RF07)
  ubicaciones: () => pedir<Ubicacion[]>('/api/ubicaciones'),
  reservas: (f?: Filtros) => pedir<Pagina<Reserva>>('/api/reservas', { params: f }),
  reserva: (id: number | string) => pedir<Reserva>(`/api/reservas/${id}`),
  crearReserva: (c: ReservaCrear) => pedir<Reserva>('/api/reservas', { metodo: 'POST', cuerpo: c }),

  // Bitácoras (RF08, RF12)
  bitacoras: (f?: Filtros) => pedir<Pagina<Bitacora>>('/api/bitacoras', { params: f }),
  bitacora: (id: number | string) => pedir<BitacoraDetalle>(`/api/bitacoras/${id}`),
  ruta: (id: number | string) => pedir<Ruta>(`/api/bitacoras/${id}/ruta`),

  // Monitoreo y alertas (RF09–RF11)
  monitoreo: () => pedir<Monitoreo>('/api/monitoreo'),
  urlStream: (token: string) => construirUrl('/api/monitoreo/stream', { token }),
  alertas: (f?: Filtros) => pedir<Pagina<Alerta>>('/api/alertas', { params: f }),
  alerta: (id: number | string) => pedir<Alerta>(`/api/alertas/${id}`),

  // Auditoría (RNF09)
  auditoria: (f?: Filtros) => pedir<Pagina<RegistroAuditoria>>('/api/auditoria', { params: f }),

  // Controles de demo (MODO_DEMO=true)
  demoIniciar: (idReserva: number) =>
    pedir<{ resultado: string; id_reserva: number; id_bitacora: number | null }>(
      `/api/demo/reservas/${idReserva}/iniciar`,
      { metodo: 'POST' },
    ),
  demoEvento: (idDispositivo: number, evento: EventoDemo) =>
    pedir<{ id_dispositivo: number; numero_serie: string; tipo: string; mensaje: string }>(
      `/api/demo/dispositivos/${idDispositivo}/eventos`,
      { metodo: 'POST', cuerpo: evento },
    ),
  demoTarea: (nombre: string) =>
    pedir<{ tarea: string; resultado: unknown }>(`/api/demo/tareas/${nombre}/ejecutar`, { metodo: 'POST' }),
};
