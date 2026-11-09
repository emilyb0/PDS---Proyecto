// Glifos propios en vista cenital. Los colores salen de CSS (clases g-*), así siguen el tema y el estado.

export const GLIFO_ROBOT = `<svg viewBox="0 0 32 32" class="glifo glifo--robot" aria-hidden="true">
  <rect class="g-rueda" x="3.5" y="6" width="4" height="7.5" rx="1"/>
  <rect class="g-rueda" x="24.5" y="6" width="4" height="7.5" rx="1"/>
  <rect class="g-rueda" x="3.5" y="18.5" width="4" height="7.5" rx="1"/>
  <rect class="g-rueda" x="24.5" y="18.5" width="4" height="7.5" rx="1"/>
  <rect class="g-cuerpo" x="7.5" y="3.5" width="17" height="25" rx="2.5"/>
  <rect class="g-sensor" x="11" y="6.5" width="10" height="3.2" rx="1.2"/>
  <path class="g-linea" d="M11 14.5h10M11 18.5h10M11 22.5h10"/>
</svg>`;

export const GLIFO_DRONE = `<svg viewBox="0 0 32 32" class="glifo glifo--drone" aria-hidden="true">
  <path class="g-brazo" d="M8.5 8.5L23.5 23.5M23.5 8.5L8.5 23.5"/>
  <circle class="g-rotor" cx="7.5" cy="7.5" r="5"/>
  <circle class="g-rotor" cx="24.5" cy="7.5" r="5"/>
  <circle class="g-rotor" cx="7.5" cy="24.5" r="5"/>
  <circle class="g-rotor" cx="24.5" cy="24.5" r="5"/>
  <path class="g-helice" d="M4.5 7.5h6M21.5 7.5h6M4.5 24.5h6M21.5 24.5h6"/>
  <rect class="g-cuerpo" x="11.5" y="11.5" width="9" height="9" rx="2" transform="rotate(45 16 16)"/>
  <circle class="g-sensor" cx="16" cy="16" r="1.9"/>
</svg>`;

export function glifo(tipo: string): string {
  return tipo === 'DRONE' ? GLIFO_DRONE : GLIFO_ROBOT;
}
