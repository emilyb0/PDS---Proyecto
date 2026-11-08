"""Esquema inicial: ejecuta tal cual ``docs/modelo/esquema_bd.sql``.

La copia literal está en ``migraciones/sql/0001_esquema_bd.sql``. Esta migración NO se edita:
cualquier cambio al esquema va en una migración nueva (reglas de oro de CLAUDE.md).

Revisión: 0001
Anterior: ninguna
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ARCHIVO_SQL = Path(__file__).resolve().parent.parent / "sql" / "0001_esquema_bd.sql"


def upgrade() -> None:
    sql = ARCHIVO_SQL.read_text(encoding="utf-8")
    # Sin parámetros: así psycopg envía el script completo (varias sentencias, cuerpos $$ y '%' de los RAISE).
    op.get_bind().exec_driver_sql(sql, execution_options={"no_parameters": True})


def downgrade() -> None:
    op.get_bind().exec_driver_sql(
        """
        DROP FUNCTION IF EXISTS reporte_dispositivo(INT, DATE, DATE);
        DROP TABLE IF EXISTS video, atencion_alerta, alerta_mantenimiento, alerta_servicio, alerta,
                             incidencia, lectura_sensor, registro_telemetria, bitacora_servicio, reserva,
                             vertice_zona, zona_operacion, ubicacion, mantenimiento, sensor, dispositivo,
                             registro_auditoria, usuario CASCADE;
        DROP FUNCTION IF EXISTS fn_validar_reserva();
        DROP FUNCTION IF EXISTS fn_validar_baja();
        DROP TYPE IF EXISTS causa_alerta, tipo_alerta, tipo_incidencia, estado_servicio, estado_reserva,
                            tipo_servicio, tipo_mantenimiento, estado_sensor, estado_dispositivo,
                            tipo_dispositivo, accion_auditoria, estado_usuario, rol_usuario;
        """,
        execution_options={"no_parameters": True},
    )
