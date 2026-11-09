import { useEffect, useState, type FormEvent } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { ErrorApi } from '../api/cliente';
import { api } from '../api/servicios';
import type { Salud } from '../api/tipos';
import { Logo } from '../componentes/Layout';
import { BotonTema } from '../componentes/Tema';
import { GLIFO_DRONE, GLIFO_ROBOT } from '../mapa/glifos';
import { useSesion } from '../sesion/SesionContext';
import { horaBogota } from '../utils/formato';

const PRUEBA = [
  { correo: 'admin@campus.edu.co', contrasena: 'Admin123*', rol: 'Administrador' },
  { correo: 'operador1@campus.edu.co', contrasena: 'Operador123*', rol: 'Operador' },
];

const interior = (svg: string) => svg.replace(/^<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '');

/** Plano esquemático del campus: decorativo, dibujado a mano en SVG. */
function Plano() {
  const nodos: [number, number, string][] = [
    [120, 300, 'BASE'],
    [250, 210, 'CAFETERÍA'],
    [410, 150, 'RECTORÍA'],
    [330, 360, 'BIBLIOTECA'],
    [455, 300, 'BLOQUE A'],
    [180, 120, 'COLISEO'],
  ];
  return (
    <svg className="plano" viewBox="0 0 560 440" aria-hidden>
      <defs>
        <pattern id="reticula" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M20 0H0V20" className="plano-reticula" />
        </pattern>
      </defs>
      <rect width="560" height="440" fill="url(#reticula)" />
      <circle cx="120" cy="300" r="70" className="plano-radio" />
      <circle cx="120" cy="300" r="140" className="plano-radio" />
      <circle cx="120" cy="300" r="210" className="plano-radio" />
      <path d="M120 300 L250 210 L410 150" className="plano-ruta plano-ruta--activa" />
      <path d="M120 300 L330 360 L455 300" className="plano-ruta" />
      <path d="M120 300 L180 120" className="plano-ruta" />
      {nodos.map(([x, y, n]) => (
        <g key={n} transform={`translate(${x} ${y})`}>
          <path d="M-6 0H6M0 -6V6" className="plano-cruz" />
          <text x="10" y="-8" className="plano-texto">
            {n}
          </text>
        </g>
      ))}
      <svg x="338" y="146" width="40" height="40" viewBox="0 0 32 32" className="plano-glifo plano-glifo--activo" dangerouslySetInnerHTML={{ __html: interior(GLIFO_ROBOT) }} />
      <svg x="128" y="196" width="40" height="40" viewBox="0 0 32 32" className="plano-glifo" dangerouslySetInnerHTML={{ __html: interior(GLIFO_DRONE) }} />
    </svg>
  );
}

export function Login() {
  const { sesion, iniciar, motivoCierre } = useSesion();
  const ubicacion = useLocation();
  const [correo, setCorreo] = useState('');
  const [contrasena, setContrasena] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [salud, setSalud] = useState<Salud | null | 'falla'>(null);
  const [reloj, setReloj] = useState(horaBogota(true));

  useEffect(() => {
    api.salud().then(setSalud).catch(() => setSalud('falla'));
    const t = window.setInterval(() => setReloj(horaBogota(true)), 1000);
    return () => window.clearInterval(t);
  }, []);

  if (sesion) {
    const desde = (ubicacion.state as { desde?: string } | null)?.desde;
    return <Navigate to={desde && desde !== '/login' ? desde : '/'} replace />;
  }

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    if (!correo.trim() || !contrasena) {
      setError('Escriba su correo institucional y su contraseña.');
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      await iniciar(correo.trim(), contrasena);
    } catch (err) {
      setError(err instanceof ErrorApi ? err.mensaje : 'No se pudo iniciar sesión.');
    } finally {
      setEnviando(false);
    }
  };

  const enLinea = salud && salud !== 'falla';

  return (
    <div className="login">
      <section className="login-arte">
        <div className="login-marca">
          <Logo tamano={34} />
          <div>
            <div className="login-sistema">Sistema centralizado</div>
            <div className="login-campus">Transporte interno del campus</div>
          </div>
        </div>
        <h1 className="login-titulo">
          Torre
          <br />
          de control
        </h1>
        <p className="login-lema">Reservas, monitoreo en tiempo real, bitácoras y alertas de los robots y drones de la universidad.</p>
        <Plano />
        <dl className="login-estado mono">
          <div>
            <dt>Hora BOG</dt>
            <dd>{reloj}</dd>
          </div>
          <div>
            <dt>Servidor</dt>
            <dd className={enLinea ? '' : 'acento'}>{salud === null ? '…' : enLinea ? 'En línea' : 'Sin respuesta'}</dd>
          </div>
          <div>
            <dt>Simulador</dt>
            <dd>{enLinea ? (salud as Salud).simulador.toUpperCase() : '—'}</dd>
          </div>
        </dl>
      </section>

      <section className="login-panel">
        <div className="login-tema">
          <BotonTema />
        </div>
        <form className="login-form" onSubmit={enviar} noValidate>
          <div className="pagina-codigo">RF20 · Acceso</div>
          <h2>Iniciar sesión</h2>
          {motivoCierre && !error && <div className="nota">{motivoCierre}</div>}
          <label className="campo">
            <span className="campo-etiqueta">Correo institucional</span>
            <input
              type="email"
              autoComplete="username"
              value={correo}
              onChange={(e) => setCorreo(e.target.value)}
              placeholder="nombre@campus.edu.co"
              autoFocus
            />
          </label>
          <label className="campo">
            <span className="campo-etiqueta">Contraseña</span>
            <input
              type="password"
              autoComplete="current-password"
              value={contrasena}
              onChange={(e) => setContrasena(e.target.value)}
            />
          </label>
          {error && (
            <div className="error-api" role="alert">
              <p>{error}</p>
            </div>
          )}
          <button className="boton boton--primario boton--grande" disabled={enviando}>
            {enviando ? 'Verificando…' : 'Entrar'}
          </button>

          <div className="login-prueba">
            <div className="campo-etiqueta">Usuarios de prueba</div>
            {PRUEBA.map((u) => (
              <button
                type="button"
                key={u.correo}
                className="login-prueba-item"
                onClick={() => {
                  setCorreo(u.correo);
                  setContrasena(u.contrasena);
                  setError(null);
                }}
              >
                <span className="mono">{u.correo}</span>
                <span className="tenue">{u.rol}</span>
              </button>
            ))}
          </div>
        </form>
      </section>
    </div>
  );
}
