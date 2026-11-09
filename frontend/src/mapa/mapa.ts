import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useEffect, useRef, useState, type RefObject } from 'react';
import type { Ubicacion } from '../api/tipos';
import { esc } from '../utils/formato';
import { glifo } from './glifos';

// Base de operaciones de la semilla; el mapa se ajusta luego a las ubicaciones reales.
export const CENTRO: L.LatLngTuple = [4.6388, -74.0838];

/** Crea un mapa Leaflet en el contenedor y lo destruye al desmontar. */
export function useMapa(ref: RefObject<HTMLDivElement>, opciones: { zoom?: number; interactivo?: boolean } = {}) {
  const [mapa, setMapa] = useState<L.Map | null>(null);
  const opcionesRef = useRef(opciones);

  useEffect(() => {
    if (!ref.current) return;
    const o = opcionesRef.current;
    const interactivo = o.interactivo ?? true;
    const m = L.map(ref.current, {
      center: CENTRO,
      zoom: o.zoom ?? 17,
      zoomSnap: 0.25,
      zoomControl: false,
      attributionControl: true,
      dragging: interactivo,
      scrollWheelZoom: interactivo,
      doubleClickZoom: interactivo,
      touchZoom: interactivo,
      keyboard: interactivo,
    });
    m.attributionControl.setPrefix(false);
    if (interactivo) L.control.zoom({ position: 'bottomright', zoomInTitle: 'Acercar', zoomOutTitle: 'Alejar' }).addTo(m);
    // Teselas neutras: el CSS las pasa a escala de grises (claro) o las invierte (oscuro).
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxNativeZoom: 19,
      maxZoom: 20,
      className: 'teselas',
      attribution: '© OpenStreetMap',
    }).addTo(m);
    const obs = new ResizeObserver(() => m.invalidateSize());
    obs.observe(ref.current);
    setMapa(m);
    return () => {
      obs.disconnect();
      m.remove();
      setMapa(null);
    };
  }, [ref]);

  return mapa;
}

export function iconoDispositivo(o: {
  tipo: string;
  etiqueta: string;
  clases?: string;
  desplazamiento?: [number, number];
  tamano?: number;
}): L.DivIcon {
  const t = o.tamano ?? 34;
  const [dx, dy] = o.desplazamiento ?? [0, 0];
  return L.divIcon({
    className: `marcador ${o.clases ?? ''}`,
    html: `<span class="marcador-anillo"></span><span class="marcador-glifo">${glifo(o.tipo)}</span><span class="marcador-etiqueta">${esc(o.etiqueta)}</span>`,
    iconSize: [t, t],
    iconAnchor: [t / 2 - dx, t / 2 - dy],
  });
}

export function iconoUbicacion(u: Pick<Ubicacion, 'nombre' | 'es_base'>, clase = ''): L.DivIcon {
  return L.divIcon({
    className: `punto-ubicacion ${u.es_base ? 'punto-ubicacion--base' : ''} ${clase}`,
    html: `<span class="punto-cruz"></span><span class="punto-nombre">${esc(u.es_base ? `${u.nombre} · base` : u.nombre)}</span>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
}

export function iconoMarca(clase: string, contenido = ''): L.DivIcon {
  return L.divIcon({ className: `marca ${clase}`, html: contenido, iconSize: [18, 18], iconAnchor: [9, 9] });
}

/** Dibuja las ubicaciones del campus en una capa y devuelve sus límites. */
export function capaUbicaciones(ubicaciones: Ubicacion[], resaltar: number[] = []): L.LayerGroup {
  const capa = L.layerGroup();
  for (const u of ubicaciones) {
    L.marker([u.latitud, u.longitud], {
      icon: iconoUbicacion(u, resaltar.includes(u.id_ubicacion) ? 'punto-ubicacion--resaltada' : ''),
      interactive: false,
      keyboard: false,
      zIndexOffset: -1000,
    }).addTo(capa);
  }
  return capa;
}

export function limites(puntos: [number, number][]): L.LatLngBounds | null {
  if (puntos.length === 0) return null;
  return L.latLngBounds(puntos.map((p) => L.latLng(p[0], p[1])));
}

const animaciones = new WeakMap<L.Marker, number>();

/** Mueve el marcador con una interpolación suave en vez de saltar (transición al llegar telemetría). */
export function moverSuave(m: L.Marker, destino: L.LatLngExpression, ms = 1200) {
  const ini = m.getLatLng();
  const fin = L.latLng(destino);
  const previa = animaciones.get(m);
  if (previa) cancelAnimationFrame(previa);
  if (ini.distanceTo(fin) < 0.2 || document.hidden) {
    m.setLatLng(fin);
    return;
  }
  const t0 = performance.now();
  const paso = (t: number) => {
    const k = Math.min(1, (t - t0) / ms);
    const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
    m.setLatLng([ini.lat + (fin.lat - ini.lat) * e, ini.lng + (fin.lng - ini.lng) * e]);
    if (k < 1) animaciones.set(m, requestAnimationFrame(paso));
    else animaciones.delete(m);
  };
  animaciones.set(m, requestAnimationFrame(paso));
}
