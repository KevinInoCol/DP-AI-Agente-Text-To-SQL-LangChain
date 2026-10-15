"""
Conexión a BigQuery con SQLAlchemy (dialecto sqlalchemy-bigquery).

Dos proyectos distintos, y es fácil confundirlos:
- Proyecto de DATOS: bigquery-public-data (dataset público new_york_citibike).
  Es de Google: se lee, pero no se pueden lanzar jobs en él.
- Proyecto de FACTURACIÓN: el de la Service Account (`project_id` de su JSON).
  Ahí se ejecutan y cobran los jobs de consulta.

Por eso la URL apunta al proyecto de datos y `billing_project_id` al de la
Service Account. La SA solo necesita el rol BigQuery Job User en SU proyecto:
el dataset público ya es legible por cualquiera.

Requerida en .env: GOOGLE_APPLICATION_CREDENTIALS (ruta al JSON en credentials/)
Opcionales: BIGQUERY_DATA_PROJECT, BIGQUERY_DATASET, BIGQUERY_LOCATION,
            BIGQUERY_MAX_BYTES_BILLED

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import json
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from sqlalchemy import Engine, create_engine

load_dotenv(find_dotenv())

# ============================================
# VARIABLES DE ENTORNO
# ============================================
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
BIGQUERY_DATA_PROJECT = os.getenv("BIGQUERY_DATA_PROJECT", "bigquery-public-data")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "new_york_citibike")
BIGQUERY_LOCATION = os.getenv("BIGQUERY_LOCATION", "US")
# Tope de bytes facturados POR CONSULTA: BigQuery rechaza el job antes de
# ejecutarlo si lo supera. 2 GB alcanza para agregaciones sobre unas pocas
# columnas de citibike_trips; un SELECT * de la tabla entera no pasa.
BIGQUERY_MAX_BYTES_BILLED = int(os.getenv("BIGQUERY_MAX_BYTES_BILLED", str(2 * 1024**3)))

# ============================================
# CONSTANTES
# ============================================
BASE_DIR = Path(__file__).resolve().parent.parent

_engine: Engine | None = None


# ============================================
# FUNCIONES PÚBLICAS
# ============================================
def ruta_credenciales() -> Path:
    """Ruta absoluta al JSON de la Service Account (relativa al proyecto si no es absoluta)."""
    if not GOOGLE_APPLICATION_CREDENTIALS:
        raise ValueError("❌ Falta GOOGLE_APPLICATION_CREDENTIALS en .env")
    ruta = Path(GOOGLE_APPLICATION_CREDENTIALS)
    ruta = ruta if ruta.is_absolute() else BASE_DIR / ruta
    if not ruta.is_file():
        raise FileNotFoundError(f"❌ No existe la clave de la Service Account: {ruta}")
    return ruta


def proyecto_facturacion() -> str:
    """project_id de la Service Account: ahí corren (y se cobran) los jobs."""
    with open(ruta_credenciales(), encoding="utf-8") as f:
        datos = json.load(f)
    if datos.get("type") != "service_account":
        raise ValueError("❌ El JSON de credentials/ no es de una Service Account")
    return datos["project_id"]


def get_engine() -> Engine:
    """Engine de SQLAlchemy contra el dataset. Se crea UNA vez (singleton)."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            f"bigquery://{BIGQUERY_DATA_PROJECT}/{BIGQUERY_DATASET}"
            f"?maximum_bytes_billed={BIGQUERY_MAX_BYTES_BILLED}",
            credentials_path=str(ruta_credenciales()),
            billing_project_id=proyecto_facturacion(),
            location=BIGQUERY_LOCATION,
        )
    return _engine
