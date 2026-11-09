import L from 'leaflet';
import { useEffect, useRef } from 'react';
import type { Ubicacion } from '../api/tipos';
import { capaUbicaciones, iconoDispositivo, iconoMarca, useMapa } from './mapa';

interface Props {
  latitud: number;
  longitud: number;
  /** Si viene, dibuja el glifo del dispositivo; si no, una marca de alerta. */
  tipo?: string;
  etiqueta?: string;
  clases?: string;
  ubicaciones?: Ubicacion[];
}

/** Mapa pequeño con un solo punto: última posición de un dispositivo o lugar de una alerta. */
export function MapaPunto(p: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapa = useMapa(ref, { zoom: 17.5 });
  const marca = useRef<L.Marker | null>(null);

  useEffect(() => {
    if (!mapa || !p.ubicaciones?.length) return;
    const capa = capaUbicaciones(p.ubicaciones).addTo(mapa);
    return () => {
      capa.remove();
    };
  }, [mapa, p.ubicaciones]);

  useEffect(() => {
    if (!mapa) return;
    const icono = p.tipo
      ? iconoDispositivo({ tipo: p.tipo, etiqueta: p.etiqueta ?? '', clases: p.clases })
      : iconoMarca('marca-incidencia marca-incidencia--grande', '<span>!</span>');
    marca.current?.remove();
    marca.current = L.marker([p.latitud, p.longitud], { icon: icono, interactive: false, zIndexOffset: 1000 }).addTo(mapa);
    mapa.setView([p.latitud, p.longitud], mapa.getZoom(), { animate: false });
  }, [mapa, p.latitud, p.longitud, p.tipo, p.etiqueta, p.clases]);

  return (
    <div className="mapa mapa--punto">
      <div className="mapa-lienzo" ref={ref} />
    </div>
  );
}
