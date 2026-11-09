import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { horaBogota } from '../utils/formato';

export type TipoAviso = 'alerta' | 'info' | 'exito' | 'error';

export interface Aviso {
  id: number;
  tipo: TipoAviso;
  rotulo: string;
  titulo: string;
  texto?: string;
  enlace?: { a: string; texto: string };
  hora: string;
  duracion: number;
}

type NuevoAviso = Omit<Aviso, 'id' | 'hora' | 'duracion'> & { duracion?: number };

interface ValorAvisos {
  avisar: (a: NuevoAviso) => void;
}

const Contexto = createContext<ValorAvisos | null>(null);

const DURACION: Record<TipoAviso, number> = { alerta: 14000, error: 9000, info: 6000, exito: 5000 };

export function ProveedorAvisos({ children }: { children: ReactNode }) {
  const [avisos, setAvisos] = useState<Aviso[]>([]);
  const siguiente = useRef(1);

  const quitar = useCallback((id: number) => setAvisos((l) => l.filter((a) => a.id !== id)), []);

  const avisar = useCallback(
    (a: NuevoAviso) => {
      const id = siguiente.current++;
      const duracion = a.duracion ?? DURACION[a.tipo];
      setAvisos((l) => [{ ...a, id, hora: horaBogota(true), duracion }, ...l].slice(0, 5));
      window.setTimeout(() => quitar(id), duracion);
    },
    [quitar],
  );

  const valor = useMemo(() => ({ avisar }), [avisar]);

  return (
    <Contexto.Provider value={valor}>
      {children}
      <div className="pila-avisos" role="region" aria-live="polite" aria-label="Avisos">
        {avisos.map((a) => (
          <div key={a.id} className={`aviso aviso--${a.tipo}`} role={a.tipo === 'alerta' ? 'alert' : 'status'}>
            <div className="aviso-cab">
              <span className="aviso-rotulo">{a.rotulo}</span>
              <span className="aviso-hora">{a.hora}</span>
              <button className="aviso-cerrar" onClick={() => quitar(a.id)} aria-label="Cerrar aviso">
                ×
              </button>
            </div>
            <div className="aviso-titulo">{a.titulo}</div>
            {a.texto && <div className="aviso-texto">{a.texto}</div>}
            {a.enlace && (
              <Link className="aviso-enlace" to={a.enlace.a} onClick={() => quitar(a.id)}>
                {a.enlace.texto} →
              </Link>
            )}
            <span className="aviso-tiempo" style={{ animationDuration: `${a.duracion}ms` }} />
          </div>
        ))}
      </div>
    </Contexto.Provider>
  );
}

export function useAvisos() {
  const v = useContext(Contexto);
  if (!v) throw new Error('useAvisos fuera de ProveedorAvisos');
  return v;
}
