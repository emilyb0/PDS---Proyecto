import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ErrorApi } from '../api/cliente';
import { api } from '../api/servicios';
import type { DispositivoCrear, EstadoDispositivo, TipoDispositivo } from '../api/tipos';
import { useAvisos } from '../componentes/Avisos';
import { Campo, ErrorApiVista, Glifo, Pagina, Panel, Segmentos } from '../componentes/ui';
import { TEXTOS } from '../utils/formato';

const ESTADOS_INICIALES: EstadoDispositivo[] = ['DISPONIBLE', 'EN_CARGA', 'FUERA_DE_SERVICIO'];
const CAMPOS = ['tipo', 'numero_serie', 'modelo', 'capacidad_carga_kg', 'autonomia_vuelo_min', 'estado', 'sensores'];

export function DispositivoNuevo() {
  const navegar = useNavigate();
  const { avisar } = useAvisos();
  const [tipo, setTipo] = useState<TipoDispositivo>('ROBOT');
  const [serie, setSerie] = useState('');
  const [modelo, setModelo] = useState('');
  const [capacidad, setCapacidad] = useState('');
  const [autonomia, setAutonomia] = useState('');
  const [estado, setEstado] = useState<EstadoDispositivo>('DISPONIBLE');
  const [sensores, setSensores] = useState('');
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [error, setError] = useState<ErrorApi | null>(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    const locales: Record<string, string> = {};
    if (!serie.trim()) locales.numero_serie = 'Escriba el número de serie.';
    if (!modelo.trim()) locales.modelo = 'Escriba el modelo.';
    if (tipo === 'ROBOT' && !(Number(capacidad) > 0)) locales.capacidad_carga_kg = 'La capacidad debe ser mayor que 0.';
    if (tipo === 'DRONE' && !(Number(autonomia) > 0 && Number.isInteger(Number(autonomia))))
      locales.autonomia_vuelo_min = 'La autonomía debe ser un número entero de minutos mayor que 0.';
    setErrores(locales);
    setError(null);
    if (Object.keys(locales).length) return;

    const cuerpo: DispositivoCrear = {
      tipo,
      numero_serie: serie.trim(),
      modelo: modelo.trim(),
      estado,
      ...(tipo === 'ROBOT' ? { capacidad_carga_kg: Number(capacidad) } : { autonomia_vuelo_min: Number(autonomia) }),
    };
    const lista = sensores
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (lista.length) cuerpo.sensores = lista;

    setEnviando(true);
    try {
      const d = await api.crearDispositivo(cuerpo);
      avisar({ tipo: 'exito', rotulo: 'RF01 · Registrado', titulo: `${d.numero_serie} · ${d.modelo}`, texto: `Se creó con ${d.sensores.length} sensores.` });
      navegar(`/inventario/${d.id_dispositivo}`);
    } catch (err) {
      if (err instanceof ErrorApi) {
        setError(err);
        const c = err.campos;
        if (err.codigo === 'DUPLICADO') c.numero_serie = err.mensaje;
        setErrores(c);
      }
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Pagina
      codigo="RF01 · Inventario"
      titulo="Registrar dispositivo"
      acciones={
        <Link className="boton boton--fantasma" to="/inventario">
          ← Inventario
        </Link>
      }
    >
      <form className="rejilla-2" onSubmit={enviar} noValidate>
        <Panel codigo="01" titulo="Datos del dispositivo">
          <div className="formulario">
            <Campo etiqueta="Tipo" grupo ancho="completo">
              <Segmentos
                nombre="Tipo"
                valor={tipo}
                onCambio={setTipo}
                opciones={[
                  { valor: 'ROBOT', texto: <><Glifo tipo="ROBOT" /> Robot</> },
                  { valor: 'DRONE', texto: <><Glifo tipo="DRONE" /> Drone</> },
                ]}
              />
            </Campo>
            <Campo etiqueta="Número de serie" error={errores.numero_serie} ayuda="Se guarda en mayúsculas.">
              <input className="mono" value={serie} onChange={(e) => setSerie(e.target.value.toUpperCase())} placeholder={tipo === 'ROBOT' ? 'R-010' : 'D-010'} maxLength={50} />
            </Campo>
            <Campo etiqueta="Modelo" error={errores.modelo}>
              <input value={modelo} onChange={(e) => setModelo(e.target.value)} placeholder={tipo === 'ROBOT' ? 'Rover Mk3' : 'Halcón X4'} maxLength={80} />
            </Campo>
            {tipo === 'ROBOT' ? (
              <Campo etiqueta="Capacidad de carga (kg)" error={errores.capacidad_carga_kg}>
                <input type="number" min="0.1" step="0.1" value={capacidad} onChange={(e) => setCapacidad(e.target.value)} />
              </Campo>
            ) : (
              <Campo etiqueta="Autonomía de vuelo (min)" error={errores.autonomia_vuelo_min}>
                <input type="number" min="1" step="1" value={autonomia} onChange={(e) => setAutonomia(e.target.value)} />
              </Campo>
            )}
            <Campo etiqueta="Estado inicial" error={errores.estado}>
              <select value={estado} onChange={(e) => setEstado(e.target.value as EstadoDispositivo)}>
                {ESTADOS_INICIALES.map((s) => (
                  <option key={s} value={s}>
                    {TEXTOS.estadoDispositivo[s]}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo
              etiqueta="Sensores (opcional)"
              error={errores.sensores}
              ancho="completo"
              ayuda="Separados por coma. Si lo deja vacío se crean los sensores del tipo."
            >
              <input value={sensores} onChange={(e) => setSensores(e.target.value)} placeholder={tipo === 'ROBOT' ? 'GPS, Cámara, LIDAR, Ultrasonido' : 'GPS, Cámara, IMU, Barómetro'} />
            </Campo>
          </div>
          <ErrorApiVista error={error} camposVisibles={CAMPOS} />
          <div className="formulario-acciones">
            <button className="boton boton--primario" disabled={enviando}>
              {enviando ? 'Registrando…' : 'Registrar'}
            </button>
            <Link className="boton boton--fantasma" to="/inventario">
              Cancelar
            </Link>
          </div>
        </Panel>
        <Panel codigo="02" titulo="Vista previa" className="panel--previa">
          <div className="previa">
            <Glifo tipo={tipo} className="glifo--grande" />
            <div className="previa-serie mono">{serie || (tipo === 'ROBOT' ? 'R-___' : 'D-___')}</div>
            <div className="tenue">{modelo || 'Modelo'}</div>
            <dl className="ficha-datos">
              <div>
                <dt>Tipo</dt>
                <dd>{TEXTOS.tipoDispositivo[tipo]}</dd>
              </div>
              <div>
                <dt>{tipo === 'ROBOT' ? 'Capacidad' : 'Autonomía'}</dt>
                <dd className="mono">{tipo === 'ROBOT' ? `${capacidad || '—'} kg` : `${autonomia || '—'} min`}</dd>
              </div>
              <div>
                <dt>Estado inicial</dt>
                <dd>{TEXTOS.estadoDispositivo[estado]}</dd>
              </div>
            </dl>
            <p className="tenue previa-nota">
              Al registrarlo aparece en el inventario y, en el siguiente ciclo, en el monitoreo.
            </p>
          </div>
        </Panel>
      </form>
    </Pagina>
  );
}
