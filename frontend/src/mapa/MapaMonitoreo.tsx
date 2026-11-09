import L from 'leaflet';
import { useEffect, useRef, useState } from 'react';
import type { Alerta, DispositivoMonitoreo, Ubicacion } from '../api/tipos';
import { enAlerta } from '../tiempoReal/MonitoreoContext';
import { capaUbicaciones, iconoDispositivo, iconoMarca, limites, moverSuave, useMapa } from './mapa';

interface Props {
  dispositivos: DispositivoMonitoreo[];
  estelas: Record<number, [number, number][]>;
  alertas: Alerta[];
  ubicaciones: Ubicacion[];
  seleccionado: number | null;
  onSeleccionar: (id: number | null) => void;
  compacto?: boolean;
}

const SEPARACION = 50;

/** Clases visuales del marcador según estado, servicio y alertas. */
function clasesDe(d: DispositivoMonitoreo, alertas: Alerta[], seleccionado: number | null) {
  const t = d.telemetria;
  const c = [`m-${d.estado.toLowerCase()}`];
  const enServicio = !!d.servicio;
  if (enServicio) c.push('m-servicio');
  const critico = !!t && (t.nivel_bateria < 20 || t.sensores.some((s) => s.estado === 'FALLA'));
  if (enAlerta(d, alertas) || (enServicio && critico)) c.push('m-alerta');
  else if (critico || (t && t.nivel_bateria < 30)) c.push('m-atencion');
  if (seleccionado === d.id_dispositivo) c.push('m-sel');
  return c.join(' ');
}

export function MapaMonitoreo(p: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapa = useMapa(ref, { zoom: p.compacto ? 16.5 : 17 });
  const marcadores = useRef(new Map<number, { m: L.Marker; firma: string }>());
  const estelas = useRef(new Map<number, L.Polyline>());
  const capaDestinos = useRef<L.LayerGroup | null>(null);
  const ajustado = useRef(false);
  const onSel = useRef(p.onSeleccionar);
  onSel.current = p.onSeleccionar;
  const [cursor, setCursor] = useState<[number, number] | null>(null);

  // Ubicaciones del campus y encuadre inicial (se repite si el contenedor cambia de tamaño
  // mientras el usuario no haya movido el mapa).
  useEffect(() => {
    if (!mapa || p.ubicaciones.length === 0) return;
    const capa = capaUbicaciones(p.ubicaciones).addTo(mapa);
    const b = limites(p.ubicaciones.map((u) => [u.latitud, u.longitud]));
    const encuadrar = () => {
      if (b && !ajustado.current) mapa.fitBounds(b, { padding: p.compacto ? [28, 28] : [90, 90], maxZoom: 18, animate: false });
    };
    const tocar = () => {
      ajustado.current = true;
    };
    encuadrar();
    mapa.on('resize', encuadrar);
    mapa.on('dragstart', tocar);
    const el = mapa.getContainer();
    el.addEventListener('wheel', tocar, { passive: true });
    return () => {
      capa.remove();
      mapa.off('resize', encuadrar);
      mapa.off('dragstart', tocar);
      el.removeEventListener('wheel', tocar);
    };
  }, [mapa, p.ubicaciones, p.compacto]);

  // Lectura de coordenadas bajo el cursor.
  useEffect(() => {
    if (!mapa || p.compacto) return;
    const mover = (e: L.LeafletMouseEvent) => setCursor([e.latlng.lat, e.latlng.lng]);
    const salir = () => setCursor(null);
    mapa.on('mousemove', mover);
    mapa.on('mouseout', salir);
    return () => {
      mapa.off('mousemove', mover);
      mapa.off('mouseout', salir);
    };
  }, [mapa, p.compacto]);

  // Marcadores de los dispositivos.
  useEffect(() => {
    if (!mapa) return;
    const vistos = new Set<number>();
    // Los que comparten punto (todos los que esperan en la base) se despliegan en fila, como un hangar.
    const grupos = new Map<string, number[]>();
    const clave = (lat: number, lng: number) => `${lat.toFixed(5)},${lng.toFixed(5)}`;
    for (const d of p.dispositivos) {
      if (!d.telemetria) continue;
      const k = clave(d.telemetria.latitud, d.telemetria.longitud);
      grupos.set(k, [...(grupos.get(k) ?? []), d.id_dispositivo]);
    }
    for (const d of p.dispositivos) {
      const t = d.telemetria;
      if (!t) continue;
      vistos.add(d.id_dispositivo);
      const g = grupos.get(clave(t.latitud, t.longitud))!;
      const i = g.indexOf(d.id_dispositivo);
      const desp: [number, number] = g.length > 1 ? [(i - (g.length - 1) / 2) * SEPARACION, 34] : [0, 0];
      const clases = clasesDe(d, p.alertas, p.seleccionado);
      const firma = `${d.tipo}|${clases}|${desp.join(',')}`;
      const zIndex = p.seleccionado === d.id_dispositivo ? 1000 : d.servicio ? 500 : 0;
      const existente = marcadores.current.get(d.id_dispositivo);
      if (existente) {
        if (existente.firma !== firma) {
          existente.m.setIcon(iconoDispositivo({ tipo: d.tipo, etiqueta: d.numero_serie, clases, desplazamiento: desp }));
          existente.firma = firma;
        }
        existente.m.setZIndexOffset(zIndex);
        moverSuave(existente.m, [t.latitud, t.longitud]);
      } else {
        const m = L.marker([t.latitud, t.longitud], {
          icon: iconoDispositivo({ tipo: d.tipo, etiqueta: d.numero_serie, clases, desplazamiento: desp }),
          title: `${d.numero_serie} · ${d.modelo}`,
          zIndexOffset: zIndex,
          riseOnHover: true,
        })
          .on('click', () => onSel.current(d.id_dispositivo))
          .addTo(mapa);
        marcadores.current.set(d.id_dispositivo, { m, firma });
      }
    }
    for (const [id, { m }] of marcadores.current) {
      if (!vistos.has(id)) {
        m.remove();
        marcadores.current.delete(id);
      }
    }
  }, [mapa, p.dispositivos, p.alertas, p.seleccionado]);

  // Estelas de los servicios en curso y línea hacia el destino.
  useEffect(() => {
    if (!mapa) return;
    for (const [idTexto, puntos] of Object.entries(p.estelas)) {
      const id = Number(idTexto);
      const linea = estelas.current.get(id);
      if (linea) linea.setLatLngs(puntos);
      else
        estelas.current.set(
          id,
          L.polyline(puntos, { className: 'estela', weight: 3, interactive: false, lineJoin: 'round' }).addTo(mapa),
        );
    }
    for (const [id, linea] of estelas.current) {
      if (!(id in p.estelas)) {
        linea.remove();
        estelas.current.delete(id);
      }
    }

    capaDestinos.current?.remove();
    const capa = L.layerGroup();
    const base = p.ubicaciones.find((u) => u.es_base);
    for (const d of p.dispositivos) {
      if (!d.servicio || !d.telemetria) continue;
      const vuelve = d.telemetria.estado_servicio === 'RETORNANDO';
      const meta = vuelve ? base : p.ubicaciones.find((u) => u.id_ubicacion === d.servicio!.destino.id_ubicacion);
      if (!meta) continue;
      L.polyline(
        [
          [d.telemetria.latitud, d.telemetria.longitud],
          [meta.latitud, meta.longitud],
        ],
        { className: 'linea-destino', weight: 1.5, dashArray: '3 6', interactive: false },
      ).addTo(capa);
      L.marker([meta.latitud, meta.longitud], {
        icon: iconoMarca('marca-destino', '<span></span>'),
        interactive: false,
        keyboard: false,
      }).addTo(capa);
    }
    capa.addTo(mapa);
    capaDestinos.current = capa;
  }, [mapa, p.estelas, p.dispositivos, p.ubicaciones]);

  // Al elegir un dispositivo desde la lista, llevar el mapa hasta él.
  const objetivo = p.dispositivos.find((d) => d.id_dispositivo === p.seleccionado)?.telemetria;
  const hayObjetivo = !!objetivo;
  // Solo al cambiar la selección, no con cada telemetría. En el mapa compacto solo se desplaza si no se ve.
  useEffect(() => {
    if (!mapa || !objetivo) return;
    const punto = L.latLng(objetivo.latitud, objetivo.longitud);
    if (p.compacto) {
      if (!mapa.getBounds().pad(-0.1).contains(punto)) mapa.panTo(punto);
      return;
    }
    ajustado.current = true;
    mapa.flyTo(punto, Math.max(mapa.getZoom(), 17.5), { duration: 0.6 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapa, p.seleccionado, hayObjetivo]);

  return (
    <div className={`mapa ${p.compacto ? 'mapa--compacto' : ''}`}>
      <div className="mapa-lienzo" ref={ref} />
      {!p.compacto && (
        <div className="mapa-cursor" aria-hidden>
          {cursor ? `${cursor[0].toFixed(5)}  ${cursor[1].toFixed(5)}` : 'LAT —  LNG —'}
        </div>
      )}
    </div>
  );
}
