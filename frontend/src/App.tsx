import type { ReactNode } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Layout } from './componentes/Layout';
import { Cargando } from './componentes/ui';
import { Alertas, AlertaDetalle } from './paginas/Alertas';
import { Auditoria } from './paginas/Auditoria';
import { Bitacoras } from './paginas/Bitacoras';
import { BitacoraDetalle } from './paginas/BitacoraDetalle';
import { Demo } from './paginas/Demo';
import { DispositivoDetalle } from './paginas/DispositivoDetalle';
import { DispositivoNuevo } from './paginas/DispositivoNuevo';
import { Inventario } from './paginas/Inventario';
import { Login } from './paginas/Login';
import { Monitoreo } from './paginas/Monitoreo';
import { NoEncontrado, SinAcceso } from './paginas/Otros';
import { ReservaDetalle } from './paginas/ReservaDetalle';
import { ReservaNueva } from './paginas/ReservaNueva';
import { Reservas } from './paginas/Reservas';
import { Usuarios } from './paginas/Usuarios';
import { MENU, type Pantalla } from './sesion/permisos';
import { useSesion } from './sesion/SesionContext';
import { ProveedorMonitoreo } from './tiempoReal/MonitoreoContext';

function Protegida({ pantalla, children }: { pantalla: Pantalla; children: ReactNode }) {
  const { puede } = useSesion();
  return puede(pantalla) ? <>{children}</> : <SinAcceso />;
}

function ConSesion() {
  const { sesion, cargando } = useSesion();
  const ubicacion = useLocation();
  if (cargando) {
    return (
      <div className="pantalla-carga">
        <Cargando texto="Recuperando la sesión" />
      </div>
    );
  }
  if (!sesion) return <Navigate to="/login" replace state={{ desde: ubicacion.pathname + ubicacion.search }} />;
  return (
    <ProveedorMonitoreo>
      <Layout />
    </ProveedorMonitoreo>
  );
}

function Inicio() {
  const { puede } = useSesion();
  const primera = MENU.find((m) => puede(m.pantalla));
  return primera ? <Navigate to={primera.ruta} replace /> : <SinAcceso />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ConSesion />}>
        <Route index element={<Inicio />} />
        <Route path="monitoreo" element={<Protegida pantalla="monitoreo"><Monitoreo /></Protegida>} />
        <Route path="inventario" element={<Protegida pantalla="inventario"><Inventario /></Protegida>} />
        <Route path="inventario/nuevo" element={<Protegida pantalla="dispositivoNuevo"><DispositivoNuevo /></Protegida>} />
        <Route path="inventario/:id" element={<Protegida pantalla="inventario"><DispositivoDetalle /></Protegida>} />
        <Route path="reservas" element={<Protegida pantalla="reservas"><Reservas /></Protegida>} />
        <Route path="reservas/nueva" element={<Protegida pantalla="reservaNueva"><ReservaNueva /></Protegida>} />
        <Route path="reservas/:id" element={<Protegida pantalla="reservas"><ReservaDetalle /></Protegida>} />
        <Route path="bitacoras" element={<Protegida pantalla="bitacoras"><Bitacoras /></Protegida>} />
        <Route path="bitacoras/:id" element={<Protegida pantalla="bitacoras"><BitacoraDetalle /></Protegida>} />
        <Route path="alertas" element={<Protegida pantalla="alertas"><Alertas /></Protegida>} />
        <Route path="alertas/:id" element={<Protegida pantalla="alertas"><AlertaDetalle /></Protegida>} />
        <Route path="usuarios" element={<Protegida pantalla="usuarios"><Usuarios /></Protegida>} />
        <Route path="auditoria" element={<Protegida pantalla="auditoria"><Auditoria /></Protegida>} />
        <Route path="demo" element={<Protegida pantalla="demo"><Demo /></Protegida>} />
        <Route path="*" element={<NoEncontrado />} />
      </Route>
    </Routes>
  );
}
