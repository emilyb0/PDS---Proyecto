import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { fijarToken, obtenerExpiracion, obtenerToken, registrarPerdidaDeSesion } from '../api/cliente';
import { api } from '../api/servicios';
import type { Sesion } from '../api/tipos';
import { aFecha } from '../utils/formato';
import { permitido, type Pantalla } from './permisos';

interface ValorSesion {
  sesion: Sesion | null;
  cargando: boolean;
  /** Motivo del último cierre forzado (401 o vencimiento), para mostrarlo en el login. */
  motivoCierre: string | null;
  iniciar: (correo: string, contrasena: string) => Promise<void>;
  cerrar: (motivo?: string) => void;
  puede: (p: Pantalla) => boolean;
  tiene: (funcion: string) => boolean;
}

const Contexto = createContext<ValorSesion | null>(null);

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<Sesion | null>(null);
  const [cargando, setCargando] = useState<boolean>(() => !!obtenerToken());
  const [motivoCierre, setMotivoCierre] = useState<string | null>(null);

  const cerrar = useCallback((motivo?: string) => {
    fijarToken(null);
    setSesion(null);
    setMotivoCierre(motivo ?? null);
  }, []);

  // Ante cualquier 401 de la API: cerrar la sesión y volver al login.
  useEffect(() => {
    registrarPerdidaDeSesion(() => {
      setSesion(null);
      setMotivoCierre('Su sesión venció o dejó de ser válida. Ingrese de nuevo.');
    });
  }, []);

  // Al recargar la página: recuperar el usuario con GET /api/auth/yo.
  useEffect(() => {
    if (!obtenerToken()) return;
    api
      .yo()
      .then((s) => setSesion(s))
      .catch(() => fijarToken(null))
      .finally(() => setCargando(false));
  }, []);

  // El token dura 8 h: cerrar la sesión cuando venza aunque nadie llame a la API.
  useEffect(() => {
    if (!sesion) return;
    const vence = aFecha(obtenerExpiracion());
    if (!vence) return;
    const falta = vence.getTime() - Date.now();
    if (falta > 2 ** 31 - 1) return;
    const t = window.setTimeout(() => cerrar('La sesión venció (dura 8 horas). Ingrese de nuevo.'), Math.max(0, falta));
    return () => window.clearTimeout(t);
  }, [sesion, cerrar]);

  const iniciar = useCallback(async (correo: string, contrasena: string) => {
    const r = await api.login(correo, contrasena);
    fijarToken(r.token, r.expira);
    setMotivoCierre(null);
    setSesion({ usuario: r.usuario, funciones: r.funciones, requisitos_activos: r.requisitos_activos });
  }, []);

  const valor = useMemo<ValorSesion>(
    () => ({
      sesion,
      cargando,
      motivoCierre,
      iniciar,
      cerrar,
      puede: (p) => permitido(sesion, p),
      tiene: (f) => !!sesion?.funciones.includes(f),
    }),
    [sesion, cargando, motivoCierre, iniciar, cerrar],
  );

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useSesion() {
  const v = useContext(Contexto);
  if (!v) throw new Error('useSesion fuera de ProveedorSesion');
  return v;
}
