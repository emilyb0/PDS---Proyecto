import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { obtenerToken } from '../api/cliente';
import { api } from '../api/servicios';
import type {
  Alerta,
  DispositivoMonitoreo,
  EventoEspera,
  EventoServicio,
  Telemetria,
  Ubicacion,
} from '../api/tipos';
import { useAvisos } from '../componentes/Avisos';
import { useSesion } from '../sesion/SesionContext';
import { horaBogota, texto } from '../utils/formato';

// Un único EventSource para toda la aplicación (RF10): la foto inicial sale de GET /api/monitoreo y luego se
// actualiza con los eventos telemetria, alerta, servicio, servicio_en_espera y servicio_no_iniciado.

export type EstadoEnlace = 'apagado' | 'conectando' | 'en_vivo' | 'reconectando';

export interface EventoRegistro {
  id: number;
  hora: string;
  clase: 'alerta' | 'servicio' | 'aviso' | 'comando' | 'error';
  texto: string;
}

interface ValorMonitoreo {
  dispositivos: DispositivoMonitoreo[];
  alertas: Alerta[];
  estelas: Record<number, [number, number][]>;
  /** Cuenta de lecturas recibidas por dispositivo: cambia con cada telemetría (para los destellos). */
  pulsos: Record<number, number>;
  /** Momento (ms) de la última telemetría de cada dispositivo. */
  recibido: Record<number, number>;
  enlace: EstadoEnlace;
  ultimaSenal: number | null;
  intervaloSeg: number;
  ubicaciones: Ubicacion[];
  registro: EventoRegistro[];
  anotar: (clase: EventoRegistro['clase'], texto: string) => void;
  recargar: () => void;
}

const Contexto = createContext<ValorMonitoreo | null>(null);

const MAX_ESTELA = 400;

export function ProveedorMonitoreo({ children }: { children: ReactNode }) {
  const { sesion, puede } = useSesion();
  const { avisar } = useAvisos();
  const activo = !!sesion && puede('monitoreo');

  const [dispositivos, setDispositivos] = useState<Record<number, DispositivoMonitoreo>>({});
  const [alertas, setAlertas] = useState<Alerta[]>([]);
  const [estelas, setEstelas] = useState<Record<number, [number, number][]>>({});
  const [pulsos, setPulsos] = useState<Record<number, number>>({});
  const [recibido, setRecibido] = useState<Record<number, number>>({});
  const [enlace, setEnlace] = useState<EstadoEnlace>('apagado');
  const [ultimaSenal, setUltimaSenal] = useState<number | null>(null);
  const [intervaloSeg, setIntervaloSeg] = useState(5);
  const [ubicaciones, setUbicaciones] = useState<Ubicacion[]>([]);
  const [registro, setRegistro] = useState<EventoRegistro[]>([]);

  const idsConocidos = useRef<Set<number>>(new Set());
  const fotoLista = useRef(false);
  const seriePorId = useRef<Record<number, string>>({});
  const siguienteRegistro = useRef(1);
  const avisarRef = useRef(avisar);
  avisarRef.current = avisar;

  const anotar = useCallback((clase: EventoRegistro['clase'], t: string) => {
    setRegistro((l) => [{ id: siguienteRegistro.current++, hora: horaBogota(true), clase, texto: t }, ...l].slice(0, 60));
  }, []);

  const cargarFoto = useCallback(async () => {
    const m = await api.monitoreo();
    const mapa: Record<number, DispositivoMonitoreo> = {};
    for (const d of m.dispositivos) {
      mapa[d.id_dispositivo] = d;
      seriePorId.current[d.id_dispositivo] = d.numero_serie;
    }
    idsConocidos.current = new Set(Object.keys(mapa).map(Number));
    fotoLista.current = true;
    setDispositivos(mapa);
    setAlertas(m.alertas_abiertas);
    setIntervaloSeg(m.intervalo_seg);
    // Estela de los servicios en curso: la ruta que ya recorrieron.
    for (const d of m.dispositivos) {
      if (!d.servicio) continue;
      api
        .ruta(d.servicio.id_bitacora)
        .then((r) =>
          setEstelas((e) => ({
            ...e,
            [d.id_dispositivo]: r.puntos.map((p) => [p.latitud, p.longitud] as [number, number]).slice(-MAX_ESTELA),
          })),
        )
        .catch(() => undefined);
    }
  }, []);

  const recargar = useCallback(() => {
    cargarFoto().catch(() => undefined);
  }, [cargarFoto]);

  useEffect(() => {
    if (!activo) {
      setEnlace('apagado');
      return;
    }
    let cerrado = false;
    let fuente: EventSource | null = null;
    let reintento: number | undefined;
    let abiertoAntes = false;

    api.ubicaciones().then(setUbicaciones).catch(() => undefined);
    recargar();

    const serie = (id: number) => seriePorId.current[id] ?? `#${id}`;

    const alTelemetria = (t: Telemetria) => {
      const ahora = Date.now();
      seriePorId.current[t.id_dispositivo] = t.numero_serie;
      if (!idsConocidos.current.has(t.id_dispositivo)) {
        // Dispositivo nuevo (RNF10): aparece en el siguiente ciclo; se recarga la foto para traer sus datos.
        if (!fotoLista.current) return;
        idsConocidos.current.add(t.id_dispositivo);
        recargar();
        return;
      }
      setDispositivos((prev) => {
        const d = prev[t.id_dispositivo];
        if (!d) return prev;
        return { ...prev, [t.id_dispositivo]: { ...d, estado: t.estado_dispositivo, telemetria: t } };
      });
      setEstelas((prev) => {
        const actual = prev[t.id_dispositivo];
        if (t.id_bitacora == null) {
          if (!actual) return prev;
          const { [t.id_dispositivo]: _, ...resto } = prev;
          return resto;
        }
        const lista = actual ?? [];
        const ultimo = lista[lista.length - 1];
        if (ultimo && ultimo[0] === t.latitud && ultimo[1] === t.longitud) return prev;
        return { ...prev, [t.id_dispositivo]: [...lista, [t.latitud, t.longitud] as [number, number]].slice(-MAX_ESTELA) };
      });
      setPulsos((p) => ({ ...p, [t.id_dispositivo]: (p[t.id_dispositivo] ?? 0) + 1 }));
      setRecibido((r) => ({ ...r, [t.id_dispositivo]: ahora }));
      setUltimaSenal(ahora);
    };

    const alAlerta = (a: Alerta) => {
      setAlertas((l) => [a, ...l.filter((x) => x.id_alerta !== a.id_alerta)]);
      anotar('alerta', `${a.numero_serie} · ${texto('causaAlerta', a.causa)} — ${a.descripcion}`);
      avisarRef.current({
        tipo: 'alerta',
        rotulo: `Alerta · ${texto('causaAlerta', a.causa)}`,
        titulo: a.descripcion,
        texto: a.id_bitacora ? `Servicio en bitácora #${a.id_bitacora}` : undefined,
        enlace: { a: `/monitoreo?d=${a.id_dispositivo}`, texto: 'Ver en el mapa' },
      });
    };

    const alServicio = (s: EventoServicio) => {
      const iniciado = s.evento === 'INICIADO';
      if (iniciado) setEstelas((e) => ({ ...e, [s.id_dispositivo]: [] }));
      anotar('servicio', `${serie(s.id_dispositivo)} · servicio ${iniciado ? 'iniciado' : 'finalizado'} (reserva #${s.id_reserva})`);
      avisarRef.current({
        tipo: iniciado ? 'info' : 'exito',
        rotulo: iniciado ? 'Servicio iniciado' : 'Servicio finalizado',
        titulo: `${serie(s.id_dispositivo)} · reserva #${s.id_reserva}`,
        texto: iniciado ? 'El dispositivo salió de la base.' : 'Volvió a la base. La bitácora quedó cerrada.',
        enlace: { a: `/bitacoras/${s.id_bitacora}`, texto: `Bitácora #${s.id_bitacora}` },
      });
      recargar();
    };

    const alEspera = (e: EventoEspera) => {
      anotar('aviso', `${serie(e.id_dispositivo)} · reserva #${e.id_reserva} en espera: ${e.motivo}`);
      avisarRef.current({
        tipo: 'info',
        rotulo: 'Servicio en espera',
        titulo: `Reserva #${e.id_reserva} · ${serie(e.id_dispositivo)}`,
        texto: e.motivo,
      });
    };

    const alNoIniciado = (e: EventoEspera) => {
      anotar('error', `${serie(e.id_dispositivo)} · reserva #${e.id_reserva} no iniciada: ${e.motivo}`);
      avisarRef.current({
        tipo: 'error',
        rotulo: e.cancelada ? 'Reserva cancelada' : 'Servicio no iniciado',
        titulo: `Reserva #${e.id_reserva} · ${serie(e.id_dispositivo)}`,
        texto: e.cancelada ? `${e.motivo} La ventana terminó y la reserva se canceló.` : e.motivo,
        enlace: { a: `/reservas/${e.id_reserva}`, texto: 'Ver reserva' },
      });
    };

    const leer =
      <T,>(fn: (d: T) => void) =>
      (ev: Event) => {
        try {
          fn(JSON.parse((ev as MessageEvent).data) as T);
        } catch {
          /* evento mal formado: se ignora */
        }
      };

    const abrir = () => {
      const token = obtenerToken();
      if (!token || cerrado) return;
      setEnlace(abiertoAntes ? 'reconectando' : 'conectando');
      const f = new EventSource(api.urlStream(token));
      fuente = f;
      f.onopen = () => {
        setEnlace('en_vivo');
        if (abiertoAntes) recargar();
        abiertoAntes = true;
      };
      f.onerror = () => {
        if (cerrado) return;
        setEnlace('reconectando');
        if (f.readyState === EventSource.CLOSED) {
          // El servidor rechazó el flujo (p. ej. 401). /auth/yo confirma: si el token venció, el cliente cierra la sesión.
          api
            .yo()
            .then(() => {
              if (!cerrado) reintento = window.setTimeout(abrir, 3000);
            })
            .catch((e) => {
              if (!cerrado && e?.estado !== 401) reintento = window.setTimeout(abrir, 5000);
            });
        }
      };
      f.addEventListener('telemetria', leer<Telemetria>(alTelemetria));
      f.addEventListener('alerta', leer<Alerta>(alAlerta));
      f.addEventListener('servicio', leer<EventoServicio>(alServicio));
      f.addEventListener('servicio_en_espera', leer<EventoEspera>(alEspera));
      f.addEventListener('servicio_no_iniciado', leer<EventoEspera>(alNoIniciado));
    };

    abrir();
    return () => {
      cerrado = true;
      fuente?.close();
      window.clearTimeout(reintento);
    };
  }, [activo, recargar, anotar]);

  const lista = useMemo(
    () => Object.values(dispositivos).sort((a, b) => a.numero_serie.localeCompare(b.numero_serie)),
    [dispositivos],
  );

  const valor = useMemo<ValorMonitoreo>(
    () => ({
      dispositivos: lista,
      alertas,
      estelas,
      pulsos,
      recibido,
      enlace,
      ultimaSenal,
      intervaloSeg,
      ubicaciones,
      registro,
      anotar,
      recargar,
    }),
    [lista, alertas, estelas, pulsos, recibido, enlace, ultimaSenal, intervaloSeg, ubicaciones, registro, anotar, recargar],
  );

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useMonitoreo() {
  const v = useContext(Contexto);
  if (!v) throw new Error('useMonitoreo fuera de ProveedorMonitoreo');
  return v;
}

/** Alertas abiertas que pertenecen al servicio en curso del dispositivo (o batería crítica en vivo). */
export function enAlerta(d: DispositivoMonitoreo, alertas: Alerta[]): boolean {
  if (!d.servicio) return false;
  return alertas.some((a) => a.id_dispositivo === d.id_dispositivo && a.id_bitacora === d.servicio!.id_bitacora);
}
