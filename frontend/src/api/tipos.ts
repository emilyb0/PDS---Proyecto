// Tipos del contrato de la API (docs/guia-frontend.md). Los nombres siguen los del backend.

export type Rol = 'ADMINISTRADOR' | 'OPERADOR';
export type EstadoUsuario = 'ACTIVO' | 'INACTIVO';
export type TipoDispositivo = 'ROBOT' | 'DRONE';
export type EstadoDispositivo =
  | 'DISPONIBLE'
  | 'EN_SERVICIO'
  | 'EN_CARGA'
  | 'EN_MANTENIMIENTO'
  | 'FUERA_DE_SERVICIO';
export type EstadoSensor = 'OK' | 'FALLA';
export type TipoServicio = 'ENTREGA_DOCUMENTOS' | 'PEDIDO_CAFETERIA' | 'GRABACION_EVENTO';
export type EstadoReserva = 'PROGRAMADA' | 'EN_CURSO' | 'FINALIZADA' | 'CANCELADA';
export type EstadoBitacora = 'EN_CURSO' | 'ENTREGADO' | 'RETORNANDO' | 'FINALIZADO';
export type FaseServicio =
  | 'EN_BASE'
  | 'EN_RUTA'
  | 'EN_DESTINO'
  | 'ESPERANDO_CODIGO'
  | 'RETORNANDO'
  | 'DETENIDO';
export type AccionAuditoria = 'CREAR' | 'EDITAR' | 'BAJA';

export interface Pagina<T> {
  items: T[];
  total: number;
  limite: number;
  desplazamiento: number;
}

export interface Advertencia {
  codigo: string;
  mensaje: string;
  detalles: unknown;
}

export interface UsuarioResumen {
  id_usuario: number;
  nombre: string;
}

export interface Usuario extends UsuarioResumen {
  correo_institucional: string;
  rol: Rol;
  estado: EstadoUsuario;
  fecha_creacion: string;
}

export interface Sesion {
  usuario: Usuario;
  funciones: string[];
  requisitos_activos: string[];
}

export interface LoginRespuesta extends Sesion {
  token: string;
  tipo: string;
  expira: string;
}

export interface Dispositivo {
  id_dispositivo: number;
  tipo: TipoDispositivo;
  numero_serie: string;
  modelo: string;
  estado: EstadoDispositivo;
  nivel_bateria: number | null;
  horas_uso_desde_mant: number | null;
  capacidad_carga_kg: number | null;
  autonomia_vuelo_min: number | null;
  fecha_registro: string;
  dado_de_baja: boolean;
  fecha_baja: string | null;
  motivo_baja: string | null;
  sensores_en_falla: string[];
}

export interface Sensor {
  id_sensor: number;
  nombre: string;
  estado: EstadoSensor;
}

export interface DispositivoDetalle extends Dispositivo {
  sensores: Sensor[];
  servicio_activo: { id_bitacora: number; id_reserva: number; estado: EstadoBitacora } | null;
  ultima_telemetria: {
    fecha_hora: string;
    latitud: number;
    longitud: number;
    nivel_bateria: number;
    estado_servicio: FaseServicio;
  } | null;
  advertencias: Advertencia[];
}

export interface DispositivoCrear {
  tipo: TipoDispositivo;
  numero_serie: string;
  modelo: string;
  capacidad_carga_kg?: number | null;
  autonomia_vuelo_min?: number | null;
  estado?: EstadoDispositivo;
  sensores?: string[];
}

export interface DispositivoResumen {
  id_dispositivo: number;
  numero_serie: string;
  tipo: TipoDispositivo;
  modelo: string;
}

export interface Ubicacion {
  id_ubicacion: number;
  nombre: string;
  latitud: number;
  longitud: number;
  es_base: boolean;
}

export interface UbicacionResumen {
  id_ubicacion: number;
  nombre: string;
}

export interface Reserva {
  id_reserva: number;
  tipo_servicio: TipoServicio;
  estado: EstadoReserva;
  fecha: string;
  hora_inicio: string;
  hora_fin: string;
  duracion_estimada_min: number;
  inicio: string;
  fin: string;
  origen: UbicacionResumen;
  destino: UbicacionResumen;
  dispositivo: DispositivoResumen;
  operador: UsuarioResumen;
  administrador: UsuarioResumen | null;
  codigo_entrega: string | null;
  motivo_cambio: string | null;
  fecha_creacion: string;
  id_bitacora: number | null;
  advertencias?: Advertencia[];
}

export interface ReservaCrear {
  tipo_servicio: TipoServicio;
  fecha: string;
  hora_inicio: string;
  duracion_estimada_min: number;
  id_origen: number;
  id_destino: number;
  id_dispositivo: number;
  id_operador: number;
}

export interface Incidencia {
  id_incidencia: number;
  fecha_hora: string;
  tipo: string;
  descripcion: string;
  latitud: number | null;
  longitud: number | null;
  id_alerta: number | null;
}

export interface Video {
  id_video: number;
  fecha_grabacion: string;
  duracion_seg: number | null;
  eliminado: boolean;
  fecha_eliminacion: string | null;
}

export interface Bitacora {
  id_bitacora: number;
  id_reserva: number;
  estado: EstadoBitacora;
  tipo_servicio: TipoServicio;
  hora_salida: string;
  hora_regreso: string | null;
  hora_entrega: string | null;
  entregado: boolean;
  dispositivo: DispositivoResumen;
  operador: UsuarioResumen;
  numero_incidencias: number;
  tiene_video: boolean;
}

export interface BitacoraDetalle extends Bitacora {
  reserva: Reserva;
  horas_uso: number | null;
  incidencias: Incidencia[];
  video: Video | null;
}

export interface LecturaSensor {
  id_sensor?: number;
  nombre: string;
  estado: EstadoSensor;
}

export interface PuntoRuta {
  fecha_hora: string;
  latitud: number;
  longitud: number;
  nivel_bateria: number;
  estado_servicio: FaseServicio;
  sensores: LecturaSensor[];
}

export interface Ruta {
  id_bitacora: number;
  puntos: PuntoRuta[];
}

export interface Telemetria {
  id_dispositivo: number;
  numero_serie: string;
  tipo: TipoDispositivo;
  id_bitacora: number | null;
  fecha_hora: string;
  latitud: number;
  longitud: number;
  nivel_bateria: number;
  sensores: LecturaSensor[];
  estado_servicio: FaseServicio;
  estado_dispositivo: EstadoDispositivo;
  fuera_de_zona: boolean | null;
}

export interface ServicioMonitoreo {
  id_bitacora: number;
  id_reserva: number;
  tipo_servicio: TipoServicio;
  estado: EstadoBitacora;
  hora_salida: string;
  fin_estimado: string;
  destino: UbicacionResumen;
  operador: UsuarioResumen;
}

export interface DispositivoMonitoreo {
  id_dispositivo: number;
  numero_serie: string;
  tipo: TipoDispositivo;
  modelo: string;
  estado: EstadoDispositivo;
  telemetria: Telemetria | null;
  servicio: ServicioMonitoreo | null;
}

export interface Alerta {
  id_alerta: number;
  tipo: 'SERVICIO' | 'MANTENIMIENTO';
  causa: string | null;
  descripcion: string;
  fecha_hora: string;
  id_dispositivo: number;
  numero_serie: string;
  id_bitacora: number | null;
  id_incidencia: number | null;
  id_operador: number | null;
  latitud: number | null;
  longitud: number | null;
  atendida: boolean | null;
  atencion: unknown;
  dias_desde_ultimo: number | null;
  horas_desde_ultimo: number | null;
}

export interface Monitoreo {
  generado: string;
  intervalo_seg: number;
  dispositivos: DispositivoMonitoreo[];
  alertas_abiertas: Alerta[];
}

export interface RegistroAuditoria {
  id_auditoria: number;
  fecha_hora: string;
  accion: AccionAuditoria;
  entidad: string;
  id_entidad: number;
  usuario: UsuarioResumen;
}

export interface EventoServicio {
  id_bitacora: number;
  id_reserva: number;
  id_dispositivo: number;
  evento: 'INICIADO' | 'FINALIZADO';
  fecha_hora: string;
}

export interface EventoEspera {
  id_reserva: number;
  id_dispositivo: number;
  motivo: string;
  fecha_hora: string;
  cancelada?: boolean;
}

export interface Salud {
  estado: string;
  base_datos: string;
  almacenamiento: string;
  simulador: string;
  version: string;
}

export interface EventoDemo {
  tipo: 'BATERIA' | 'FALLA_SENSOR' | 'REPARAR_SENSOR' | 'PAUSAR' | 'REANUDAR';
  nivel?: number;
  sensor?: string;
}
