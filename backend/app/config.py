"""Configuración por variables de entorno (``.env``). Los nombres de las variables son los campos en mayúsculas."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


def _vacio_es_none(valor: object) -> object:
    if isinstance(valor, str) and not valor.strip():
        return None
    return valor


class ConfiguracionBD(BaseSettings):
    """Conexión a la base. La usan la aplicación, las pruebas y Alembic (que no necesita el resto).

    - Dentro de Docker Compose, ``BD_URL`` llega definido con el host ``db`` y el puerto interno 5432.
    - En la máquina (uvicorn, pytest, alembic), si ``BD_URL`` no está definido, la URL se arma con
      ``127.0.0.1:PUERTO_BD`` y las credenciales ``POSTGRES_*`` del mismo ``.env``.
    """

    # Busca el .env en la raíz del proyecto y en backend/ (el de backend/ tiene prioridad).
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore")

    postgres_db: str = "robots"
    postgres_user: str = "robots"
    postgres_password: str = "robots_dev"
    # 127.0.0.1 y no "localhost": en Windows "localhost" prueba primero ::1 (IPv6), donde Compose no publica,
    # y cada conexión nueva espera el rechazo varios segundos (decisión I-6).
    host_bd: str = "127.0.0.1"
    puerto_bd: int = 5433
    bd_url: str | None = None
    bd_url_pruebas: str | None = None

    @field_validator("bd_url", "bd_url_pruebas", mode="before")
    @classmethod
    def _bd_vacio_es_none(cls, valor: object) -> object:
        return _vacio_es_none(valor)

    @property
    def url_bd(self) -> str:
        """URL de la base: ``BD_URL`` si está definida; si no, ``127.0.0.1:PUERTO_BD``."""
        if self.bd_url:
            return self.bd_url
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.host_bd,
            port=self.puerto_bd,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    @property
    def url_bd_pruebas(self) -> str:
        """URL de la base de pruebas: la indicada o la principal con el sufijo ``_test``."""
        if self.bd_url_pruebas:
            return self.bd_url_pruebas
        url = make_url(self.url_bd)
        return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


class Configuracion(ConfiguracionBD):
    # ----------------------------------------------------------------- API en la máquina
    puerto_api: int = 8010  # puerto publicado por Compose y el de `python -m app`

    # ----------------------------------------------------------------- Seguridad
    jwt_secreto: str = Field(min_length=32)
    jwt_expira_horas: int = Field(default=8, ge=1)
    jwt_algoritmo: str = "HS256"
    dominio_correo_institucional: str | None = None
    cors_origenes: str = "http://localhost:5173"
    # Costo de Argon2 (RNF05). Las pruebas lo bajan para ir rápido.
    argon2_iteraciones: int = Field(default=3, ge=1)
    argon2_memoria_kib: int = Field(default=65536, ge=64)

    # ----------------------------------------------------------------- Funcionamiento
    # Módulos removibles de la entrega 2: "todos", "ninguno" (solo la entrega 1) o lista "rf02,rf03".
    modulos_activos: str = "todos"
    modo_demo: bool = False
    tareas_activas: bool = True
    nivel_log: str = "INFO"

    # ----------------------------------------------------------------- Parámetros de negocio (sección 6)
    bateria_minima_asignacion: int = 30
    bateria_alerta: int = 20
    retraso_alerta_min: int = 10
    viento_max_kmh: float = 30
    lluvia_max_pct: float = 60
    mantenimiento_dias: int = 30
    mantenimiento_horas: float = 50
    retencion_video_meses: int = 3
    intervalo_monitoreo_seg: float = Field(default=5, gt=0, le=5)
    espera_entrega_min: float = 5
    max_intentos_codigo: int = 3
    fraccion_recorrido: float = Field(default=0.8, gt=0, le=1)
    video_url_expira_min: int = 10

    # ----------------------------------------------------------------- Monitoreo y tiempo real (técnicos)
    monitor_concurrencia: int = Field(default=8, ge=1)  # transacciones del monitor en paralelo
    sse_ping_seg: float = Field(default=15, gt=0)  # comentario ": ping" para mantener viva la conexión
    sse_revalidar_seg: float = Field(default=30, gt=0)  # cada cuánto se revisa que el usuario siga activo

    # ----------------------------------------------------------------- Campus y simulador
    base_ubicacion: str = "Base de operaciones"
    zona_operacion: str | None = None
    semilla_simulador: int = 42

    # ----------------------------------------------------------------- Clima (RF23)
    clima_proveedor: Literal["open-meteo", "falso"] = "open-meteo"
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"

    # ----------------------------------------------------------------- Videos (RF12, RESTR04)
    almacenamiento: Literal["local", "s3"] = "local"
    almacenamiento_local_dir: Path = Path("./datos/videos")
    pendientes_dir: Path = Path("./datos/pendientes")
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    # Credenciales de un usuario IAM con acceso solo al bucket. Si están vacías, boto3 usa su cadena habitual
    # (variables de entorno del contenedor, perfil de AWS o rol de la máquina).
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    @field_validator(
        "dominio_correo_institucional",
        "zona_operacion",
        "s3_bucket",
        "s3_endpoint_url",
        "aws_access_key_id",
        "aws_secret_access_key",
        mode="before",
    )
    @classmethod
    def _opcional_vacio_es_none(cls, valor: object) -> object:
        return _vacio_es_none(valor)

    @property
    def lista_cors_origenes(self) -> list[str]:
        return [origen.strip() for origen in self.cors_origenes.split(",") if origen.strip()]
