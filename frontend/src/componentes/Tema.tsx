import { useEffect, useState } from 'react';

type Tema = 'claro' | 'oscuro';

function temaActual(): Tema {
  return document.documentElement.dataset.theme === 'oscuro' ? 'oscuro' : 'claro';
}

export function BotonTema() {
  const [tema, setTema] = useState<Tema>(temaActual);

  useEffect(() => {
    document.documentElement.dataset.theme = tema;
    try {
      localStorage.setItem('torre.tema', tema);
    } catch {
      /* sin almacenamiento: el tema dura la sesión */
    }
  }, [tema]);

  const otro: Tema = tema === 'claro' ? 'oscuro' : 'claro';
  return (
    <button
      className="barra-boton"
      onClick={() => setTema(otro)}
      title={`Cambiar a modo ${otro}`}
      aria-label={`Cambiar a modo ${otro}`}
    >
      <span className={`interruptor interruptor--${tema}`} aria-hidden />
      {tema === 'claro' ? 'Claro' : 'Oscuro'}
    </button>
  );
}
