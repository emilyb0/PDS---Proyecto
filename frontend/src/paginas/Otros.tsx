import { Link } from 'react-router-dom';

export function SinAcceso() {
  return (
    <div className="pagina pagina--mensaje">
      <div className="pagina-codigo">403</div>
      <h1 className="pagina-titulo">Sin acceso</h1>
      <p>Su rol no tiene esta función, o no está disponible en esta versión del sistema.</p>
      <Link className="boton" to="/">
        Volver al inicio
      </Link>
    </div>
  );
}

export function NoEncontrado() {
  return (
    <div className="pagina pagina--mensaje">
      <div className="pagina-codigo">404</div>
      <h1 className="pagina-titulo">Página no encontrada</h1>
      <p>La dirección no corresponde a ninguna pantalla.</p>
      <Link className="boton" to="/">
        Volver al inicio
      </Link>
    </div>
  );
}
