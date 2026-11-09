import L from 'leaflet';
import { useEffect, useRef } from 'react';
import type { Incidencia, PuntoRuta, Ubicacion } from '../api/tipos';
import { esc, fechaHora, texto } from '../utils/formato';
import { capaUbicaciones, iconoDispositivo, iconoMarca, limites, useMapa } from './mapa';

interface Props {
  puntos: PuntoRuta[];
  indice: number;
  incidencias: Incidencia[];
  ubicaciones: Ubicacion[];
  resaltar: number[];
  tipo: string;
  etiqueta: string;
  incidenciaActiva?: number | null;
}

/** Ruta recorrida de una bitácora (RF08), con la parte ya reproducida resaltada. */
export function MapaRuta(p: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapa = useMapa(ref);
  const completa = useRef<L.Polyline | null>(null);
  const recorrida = useRef<L.Polyline | null>(null);
  const marcador = useRef<L.Marker | null>(null);
  const extremos = useRef<L.LayerGroup | null>(null);
  const incid = useRef(new Map<number, L.Marker>());
  const ajustado = useRef(false);

  useEffect(() => {
    if (!mapa || p.ubicaciones.length === 0) return;
    const capa = capaUbicaciones(p.ubicaciones, p.resaltar).addTo(mapa);
    return () => {
      capa.remove();
    };
  }, [mapa, p.ubicaciones, p.resaltar]);

  // Trazado completo, extremos e incidencias.
  useEffect(() => {
    if (!mapa) return;
    const coords = p.puntos.map((x) => [x.latitud, x.longitud] as [number, number]);
    if (!completa.current) {
      completa.current = L.polyline(coords, { className: 'ruta-completa', weight: 2, dashArray: '2 5', interactive: false }).addTo(mapa);
      recorrida.current = L.polyline([], { className: 'ruta-recorrida', weight: 4, lineJoin: 'round', interactive: false }).addTo(mapa);
    } else completa.current.setLatLngs(coords);

    extremos.current?.remove();
    const capa = L.layerGroup();
    if (coords.length > 0) {
      L.marker(coords[0], { icon: iconoMarca('marca-inicio', '<b>S</b>'), interactive: false }).addTo(capa);
      L.marker(coords[coords.length - 1], { icon: iconoMarca('marca-fin', '<b>F</b>'), interactive: false }).addTo(capa);
    }
    capa.addTo(mapa);
    extremos.current = capa;

    for (const m of incid.current.values()) m.remove();
    incid.current.clear();
    for (const i of p.incidencias) {
      if (i.latitud == null || i.longitud == null) continue;
      const m = L.marker([i.latitud, i.longitud], {
        icon: iconoMarca('marca-incidencia', '<span>!</span>'),
        zIndexOffset: 800,
      })
        .bindTooltip(
          `<b>${esc(texto('tipoIncidencia', i.tipo))}</b><br>${esc(i.descripcion)}<br><span class="tip-hora">${esc(fechaHora(i.fecha_hora, true))}</span>`,
          { className: 'tip', direction: 'top', offset: [0, -10] },
        )
        .addTo(mapa);
      incid.current.set(i.id_incidencia, m);
    }

    if (!ajustado.current && coords.length > 1) {
      const b = limites(coords);
      if (b) mapa.fitBounds(b, { padding: [70, 70], maxZoom: 18.5 });
      ajustado.current = true;
    }
  }, [mapa, p.puntos, p.incidencias]);

  // Parte reproducida y posición del dispositivo en el punto elegido.
  useEffect(() => {
    if (!mapa || p.puntos.length === 0) return;
    const i = Math.min(Math.max(p.indice, 0), p.puntos.length - 1);
    const hasta = p.puntos.slice(0, i + 1).map((x) => [x.latitud, x.longitud] as [number, number]);
    recorrida.current?.setLatLngs(hasta);
    const punto = p.puntos[i];
    const enFalla = punto.sensores.some((s) => s.estado === 'FALLA') || punto.nivel_bateria < 20;
    const clases = `m-servicio m-sel ${enFalla ? 'm-alerta' : ''}`;
    if (!marcador.current) {
      marcador.current = L.marker([punto.latitud, punto.longitud], {
        icon: iconoDispositivo({ tipo: p.tipo, etiqueta: p.etiqueta, clases }),
        zIndexOffset: 1000,
        interactive: false,
      }).addTo(mapa);
    } else {
      marcador.current.setLatLng([punto.latitud, punto.longitud]);
      marcador.current.setIcon(iconoDispositivo({ tipo: p.tipo, etiqueta: p.etiqueta, clases }));
    }
  }, [mapa, p.puntos, p.indice, p.tipo, p.etiqueta]);

  // Incidencia elegida en la lista: centrarla y abrir su descripción.
  useEffect(() => {
    if (!mapa || p.incidenciaActiva == null) return;
    const m = incid.current.get(p.incidenciaActiva);
    if (!m) return;
    mapa.flyTo(m.getLatLng(), Math.max(mapa.getZoom(), 18), { duration: 0.5 });
    m.openTooltip();
  }, [mapa, p.incidenciaActiva]);

  return (
    <div className="mapa">
      <div className="mapa-lienzo" ref={ref} />
    </div>
  );
}
