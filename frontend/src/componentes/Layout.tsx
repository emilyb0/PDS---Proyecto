import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import { api } from '../api/servicios';
import type { Salud } from '../api/tipos';
import { MENU, type EntradaMenu } from '../sesion/permisos';
import { useSesion } from '../sesion/SesionContext';
import { useMonitoreo, type EstadoEnlace } from '../tiempoReal/MonitoreoContext';
import { haceCuanto, horaBogota, texto } from '../utils/formato';
import { BotonTema } from './Tema';

export function Logo({ tamano = 26 }: { tamano?: number }) {
  return (
    <svg className="logo" width={tamano} height={tamano} viewBox="0 0 32 32" aria-hidden>
      <rect className="logo-fondo" x="1" y="1" width="30" height="30" />
      <circle className="logo-trazo" cx="16" cy="16" r="8" fill="none" />
      <path className="logo-trazo" d="M16 3v7M16 22v7M3 16h7M22 16h7" />
      <rect className="logo-punto" x="14" y="14" width="4" height="4" />
    </svg>
  );
}

function useAhora(ms = 1000) {
  const [ahora, setAhora] = useState(Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setAhora(Date.now()), ms);
    return () => window.clearInterval(t);
  }, [ms]);
  return ahora;
}

const TEXTO_ENLACE: Record<EstadoEnlace, string> = {
  apagado: 'Sin enlace',
  conectando: 'Conectando',
  en_vivo: 'En vivo',
  reconectando: 'Reconectando',
};

function Enlace({ estado, ultima, ahora }: { estado: EstadoEnlace; ultima: number | null; ahora: number }) {
  return (
    <div className={`enlace enlace--${estado}`} title="Conexión de tiempo real con el monitoreo (SSE)">
      <span className="enlace-luz" />
      <span className="enlace-texto">{TEXTO_ENLACE[estado]}</span>
      {estado === 'en_vivo' && ultima && <span className="enlace-ultima mono">señal {haceCuanto(ultima, ahora)}</span>}
    </div>
  );
}

const GRUPOS: { id: EntradaMenu['grupo']; titulo: string }[] = [
  { id: 'operacion', titulo: 'Operación' },
  { id: 'registro', titulo: 'Registro' },
  { id: 'administracion', titulo: 'Administración' },
];

export function Layout() {
  const { sesion, cerrar, puede } = useSesion();
  const { enlace, alertas, ultimaSenal } = useMonitoreo();
  const ahora = useAhora();
  const [salud, setSalud] = useState<Salud | null>(null);
  const [saludFalla, setSaludFalla] = useState(false);

  useEffect(() => {
    const consultar = () =>
      api
        .salud()
        .then((s) => {
          setSalud(s);
          setSaludFalla(false);
        })
        .catch(() => setSaludFalla(true));
    consultar();
    const t = window.setInterval(consultar, 30000);
    return () => window.clearInterval(t);
  }, []);

  if (!sesion) return null;
  const visibles = MENU.filter((m) => puede(m.pantalla));
  const abiertas = alertas.length;

  return (
    <div className="marco">
      <header className="barra">
        <Link to="/" className="marca-app" aria-label="Inicio">
          <Logo />
          <span className="marca-texto">
            <b>Torre de control</b>
            <small>Robots y drones · campus</small>
          </span>
        </Link>
        <div className="barra-centro">
          {puede('monitoreo') && <Enlace estado={enlace} ultima={ultimaSenal} ahora={ahora} />}
        </div>
        <div className="barra-reloj mono" title="Hora de Bogotá">
          <span className="tenue">BOG</span> {horaBogota(true)}
        </div>
        <div className="barra-usuario">
          <span className="barra-nombre">{sesion.usuario.nombre}</span>
          <span className="barra-rol">{texto('rol', sesion.usuario.rol)}</span>
        </div>
        <BotonTema />
        <button className="barra-boton" onClick={() => cerrar()}>
          Salir
        </button>
      </header>

      <nav className="riel" aria-label="Menú principal">
        {GRUPOS.map((g) => {
          const items = visibles.filter((m) => m.grupo === g.id);
          if (items.length === 0) return null;
          return (
            <div className="riel-grupo" key={g.id}>
              <div className="riel-titulo">{g.titulo}</div>
              {items.map((m) => (
                <NavLink key={m.ruta} to={m.ruta} className={({ isActive }) => `riel-item ${isActive ? 'activo' : ''}`}>
                  <span className="riel-codigo">{m.codigo}</span>
                  <span className="riel-etiqueta">{m.etiqueta}</span>
                  {m.pantalla === 'alertas' && abiertas > 0 && (
                    <span key={abiertas} className="riel-cuenta" title={`${abiertas} alertas sin atender`}>
                      {abiertas}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          );
        })}
        <div className="riel-pie">
          <div className="riel-titulo">Sistema</div>
          {saludFalla && !salud ? (
            <div className="salud salud--falla">API sin respuesta</div>
          ) : salud ? (
            <dl className="salud">
              {(
                [
                  ['API', salud.estado],
                  ['Base de datos', salud.base_datos],
                  ['Almacenamiento', salud.almacenamiento],
                  ['Simulador', salud.simulador],
                ] as const
              ).map(([k, v]) => (
                <div key={k} className={v === 'ok' ? '' : 'salud--falla'}>
                  <dt>{k}</dt>
                  <dd className="mono">{v === 'ok' ? 'OK' : v}</dd>
                </div>
              ))}
              <div>
                <dt>Versión</dt>
                <dd className="mono">{salud.version}</dd>
              </div>
            </dl>
          ) : null}
        </div>
      </nav>

      <main className="contenido">
        <Outlet />
      </main>
    </div>
  );
}
