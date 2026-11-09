import { useState, type FormEvent } from 'react';
import { ErrorApi } from '../api/cliente';
import { api } from '../api/servicios';
import type { Rol, Usuario } from '../api/tipos';
import { useAvisos } from '../componentes/Avisos';
import { Campo, Cargando, ErrorApiVista, Estado, LIMITE, Pagina, Paginacion, Panel, Segmentos, Vacio, useCarga } from '../componentes/ui';
import { useSesion } from '../sesion/SesionContext';
import { fechaHora, TEXTOS } from '../utils/formato';

const CAMPOS = ['nombre', 'correo_institucional', 'contrasena', 'rol'];

function FormularioNuevo({ alCrear }: { alCrear: () => void }) {
  const { avisar } = useAvisos();
  const [nombre, setNombre] = useState('');
  const [correo, setCorreo] = useState('');
  const [contrasena, setContrasena] = useState('');
  const [rol, setRol] = useState<Rol>('OPERADOR');
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [error, setError] = useState<ErrorApi | null>(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    const l: Record<string, string> = {};
    if (!nombre.trim()) l.nombre = 'Escriba el nombre.';
    if (!/^\S+@\S+\.\S+$/.test(correo.trim())) l.correo_institucional = 'Escriba un correo válido.';
    if (contrasena.length < 8) l.contrasena = 'Mínimo 8 caracteres.';
    setErrores(l);
    setError(null);
    if (Object.keys(l).length) return;
    setEnviando(true);
    try {
      const u = await api.crearUsuario({ nombre: nombre.trim(), correo_institucional: correo.trim(), contrasena, rol });
      avisar({ tipo: 'exito', rotulo: 'RF18 · Usuario creado', titulo: u.nombre, texto: `${u.correo_institucional} · ${TEXTOS.rol[u.rol]}` });
      setNombre('');
      setCorreo('');
      setContrasena('');
      setRol('OPERADOR');
      alCrear();
    } catch (err) {
      if (err instanceof ErrorApi) {
        setError(err);
        const c = err.campos;
        if (err.codigo === 'DUPLICADO') c.correo_institucional = err.mensaje;
        setErrores(c);
      }
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Panel codigo="RF18" titulo="Registrar usuario">
      <form className="formulario formulario--columna" onSubmit={enviar} noValidate>
        <Campo etiqueta="Nombre" error={errores.nombre}>
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={100} />
        </Campo>
        <Campo etiqueta="Correo institucional" error={errores.correo_institucional}>
          <input type="email" value={correo} onChange={(e) => setCorreo(e.target.value)} placeholder="nombre@campus.edu.co" maxLength={120} />
        </Campo>
        <Campo etiqueta="Contraseña" error={errores.contrasena} ayuda="Mínimo 8 caracteres. Se guarda cifrada.">
          <input type="password" value={contrasena} onChange={(e) => setContrasena(e.target.value)} autoComplete="new-password" />
        </Campo>
        <Campo etiqueta="Rol" grupo error={errores.rol}>
          <Segmentos
            nombre="Rol"
            valor={rol}
            onCambio={setRol}
            opciones={[
              { valor: 'OPERADOR', texto: 'Operador' },
              { valor: 'ADMINISTRADOR', texto: 'Administrador' },
            ]}
          />
        </Campo>
        <ErrorApiVista error={error} camposVisibles={CAMPOS} />
        <div className="formulario-acciones">
          <button className="boton boton--primario" disabled={enviando}>
            {enviando ? 'Registrando…' : 'Registrar usuario'}
          </button>
        </div>
      </form>
    </Panel>
  );
}

function FilaUsuario({ u, propio, puedeDesactivar, alGuardar }: {
  u: Usuario;
  propio: boolean;
  puedeDesactivar: boolean;
  alGuardar: () => void;
}) {
  const { avisar } = useAvisos();
  const [editando, setEditando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [desactivando, setDesactivando] = useState(false);
  const [errorBaja, setErrorBaja] = useState<ErrorApi | null>(null);

  // RF19: el usuario pasa a INACTIVO y no puede volver a entrar; sus reservas, bitácoras y auditoría se conservan.
  const desactivar = async () => {
    setDesactivando(true);
    setErrorBaja(null);
    try {
      await api.desactivarUsuario(u.id_usuario);
      avisar({ tipo: 'exito', rotulo: 'RF19 · Usuario desactivado', titulo: u.nombre, texto: 'Ya no puede iniciar sesión.' });
      setConfirmando(false);
      alGuardar();
    } catch (e) {
      if (e instanceof ErrorApi) setErrorBaja(e);
    } finally {
      setDesactivando(false);
    }
  };
  const [nombre, setNombre] = useState(u.nombre);
  const [rol, setRol] = useState<Rol>(u.rol);
  const [error, setError] = useState<ErrorApi | null>(null);
  const [guardando, setGuardando] = useState(false);

  const guardar = async () => {
    const cambios: { nombre?: string; rol?: Rol } = {};
    if (nombre.trim() && nombre.trim() !== u.nombre) cambios.nombre = nombre.trim();
    if (rol !== u.rol) cambios.rol = rol;
    if (!Object.keys(cambios).length) {
      setEditando(false);
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      await api.editarUsuario(u.id_usuario, cambios);
      avisar({ tipo: 'exito', rotulo: 'Usuario actualizado', titulo: nombre.trim() });
      setEditando(false);
      alGuardar();
    } catch (e) {
      if (e instanceof ErrorApi) setError(e);
    } finally {
      setGuardando(false);
    }
  };

  if (!editando) {
    const desactivable = puedeDesactivar && u.estado === 'ACTIVO' && !propio;
    return (
      <>
        <tr className={confirmando ? 'fila-confirmar' : ''}>
          <td className="mono">{u.id_usuario}</td>
          <td>
            {u.nombre}
            {propio && <span className="tenue"> (usted)</span>}
          </td>
          <td className="mono">{u.correo_institucional}</td>
          <td>{TEXTOS.rol[u.rol]}</td>
          <td>
            <Estado grupo="estadoUsuario" valor={u.estado} />
          </td>
          <td className="mono">{fechaHora(u.fecha_creacion)}</td>
          <td className="num">
            <div className="acciones-fila">
              <button className="boton boton--fantasma boton--chico" onClick={() => setEditando(true)}>
                Editar
              </button>
              {desactivable && !confirmando && (
                <button className="boton boton--fantasma boton--chico boton--peligro" onClick={() => setConfirmando(true)}>
                  Desactivar
                </button>
              )}
            </div>
          </td>
        </tr>
        {confirmando && (
          <tr className="fila-confirmar">
            <td colSpan={7}>
              <div className="confirmar-baja">
                <div>
                  <strong>¿Desactivar a {u.nombre}?</strong>
                  <div className="tenue">
                    No podrá iniciar sesión desde este momento. Sus reservas, bitácoras y el historial de auditoría se conservan.
                  </div>
                </div>
                <div className="acciones-fila">
                  <button className="boton boton--acento boton--chico" onClick={desactivar} disabled={desactivando}>
                    {desactivando ? 'Desactivando…' : 'Sí, desactivar'}
                  </button>
                  <button
                    className="boton boton--fantasma boton--chico"
                    onClick={() => {
                      setConfirmando(false);
                      setErrorBaja(null);
                    }}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
              <ErrorApiVista error={errorBaja} />
            </td>
          </tr>
        )}
      </>
    );
  }
  return (
    <>
      <tr className="fila-edicion">
        <td className="mono">{u.id_usuario}</td>
        <td>
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} aria-label="Nombre" maxLength={100} />
        </td>
        <td className="mono">{u.correo_institucional}</td>
        <td>
          <select value={rol} onChange={(e) => setRol(e.target.value as Rol)} aria-label="Rol">
            <option value="OPERADOR">Operador</option>
            <option value="ADMINISTRADOR">Administrador</option>
          </select>
        </td>
        <td>
          <Estado grupo="estadoUsuario" valor={u.estado} />
        </td>
        <td className="mono">{fechaHora(u.fecha_creacion)}</td>
        <td className="num">
          <div className="acciones-fila">
            <button className="boton boton--primario boton--chico" onClick={guardar} disabled={guardando}>
              Guardar
            </button>
            <button
              className="boton boton--fantasma boton--chico"
              onClick={() => {
                setEditando(false);
                setNombre(u.nombre);
                setRol(u.rol);
                setError(null);
              }}
            >
              Cancelar
            </button>
          </div>
        </td>
      </tr>
      {error && (
        <tr className="fila-edicion">
          <td colSpan={7}>
            <ErrorApiVista error={error} />
          </td>
        </tr>
      )}
    </>
  );
}

export function Usuarios() {
  const { sesion, puede } = useSesion();
  const [rol, setRol] = useState('');
  const [estado, setEstado] = useState('');
  const [desp, setDesp] = useState(0);
  const lista = useCarga(() => api.usuarios({ rol, estado, limite: LIMITE, desplazamiento: desp }), [rol, estado, desp]);

  return (
    <Pagina codigo="RF18 · RNF01 · Usuarios" titulo="Usuarios" subtitulo="Solo el administrador registra usuarios y cambia sus roles.">
      <div className="rejilla-lateral">
        <div>
          <div className="filtros">
            <label className="filtro">
              <span>Rol</span>
              <select
                value={rol}
                onChange={(e) => {
                  setRol(e.target.value);
                  setDesp(0);
                }}
              >
                <option value="">Todos</option>
                <option value="ADMINISTRADOR">Administrador</option>
                <option value="OPERADOR">Operador</option>
              </select>
            </label>
            <label className="filtro">
              <span>Estado</span>
              <select
                value={estado}
                onChange={(e) => {
                  setEstado(e.target.value);
                  setDesp(0);
                }}
              >
                <option value="">Todos</option>
                <option value="ACTIVO">Activo</option>
                <option value="INACTIVO">Inactivo</option>
              </select>
            </label>
          </div>
          <ErrorApiVista error={lista.error} />
          <div className="tabla-marco">
            {lista.cargando && !lista.datos ? (
              <Cargando />
            ) : lista.datos?.items.length === 0 ? (
              <Vacio>No hay usuarios con estos filtros.</Vacio>
            ) : (
              <table className="tabla">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Nombre</th>
                    <th>Correo institucional</th>
                    <th>Rol</th>
                    <th>Estado</th>
                    <th>Creado</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {lista.datos?.items.map((u) => (
                    <FilaUsuario
                      key={`${u.id_usuario}-${u.nombre}-${u.rol}-${u.estado}`}
                      u={u}
                      propio={u.id_usuario === sesion?.usuario.id_usuario}
                      puedeDesactivar={puede('desactivarUsuario')}
                      alGuardar={lista.recargar}
                    />
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {lista.datos && <Paginacion total={lista.datos.total} limite={lista.datos.limite} desplazamiento={desp} onCambio={setDesp} />}
        </div>
        <FormularioNuevo alCrear={lista.recargar} />
      </div>
    </Pagina>
  );
}
