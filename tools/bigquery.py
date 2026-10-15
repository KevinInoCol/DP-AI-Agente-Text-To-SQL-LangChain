"""
Tool: consultas SQL de solo lectura sobre BigQuery (dataset público CitiBike NYC).

El LLM escribe el SQL y esta tool lo valida y ejecuta. El SQL generado por un
modelo no es de confianza, así que hay cuatro barreras:

1. Validación con sqlglot (dialecto BigQuery): una sola sentencia, solo
   consultas (SELECT / WITH / UNION), y solo tablas de TABLAS_PERMITIDAS.
2. Tope de bytes facturados por consulta (BIGQUERY_MAX_BYTES_BILLED en
   BigQuery/conexion.py): BigQuery rechaza el job antes de ejecutarlo.
3. Máximo de MAX_FILAS_MODELO filas devueltas al modelo, para no inflar el contexto.
4. Permisos: la Service Account solo tiene BigQuery Job User; el dataset es
   público y de solo lectura. Aunque 1 fallara, no hay nada que pueda escribir.

El esquema que ve el modelo vive en prompt/system_prompt.yaml
(<Esquema_De_Datos>). TABLAS_PERMITIDAS debe coincidir con las tablas de ese
bloque: si agregas una tabla al prompt, agrégala también aquí.

Además del texto para el modelo, el resultado (hasta MAX_FILAS_GRAFICO filas)
se guarda en el estado del agente (ultima_consulta, ver estado.py) para que
generar_graficos lo use sin que el LLM tenga que copiar los números.

Tool compartida: no depende del thread_id, se construye en agent.init_resources().

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

from datetime import date, datetime, time
from decimal import Decimal

import sqlglot
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command
from sqlglot import exp

from BigQuery import BIGQUERY_DATA_PROJECT, BIGQUERY_DATASET, BIGQUERY_MAX_BYTES_BILLED, get_engine

# ============================================
# CONSTANTES
# ============================================
TABLAS_PERMITIDAS = frozenset({"citibike_trips"})
MAX_FILAS_MODELO = 50     # filas que ve el LLM
MAX_FILAS_GRAFICO = 500   # filas que se guardan en el estado para graficar


# ============================================
# VALIDACIÓN
# ============================================
def validar_sql(sql: str, tablas_permitidas: frozenset[str] = TABLAS_PERMITIDAS) -> str | None:
    """Devuelve None si el SQL es una consulta permitida, o el motivo del rechazo."""
    try:
        sentencias = [s for s in sqlglot.parse(sql, read="bigquery") if s is not None]
    except sqlglot.errors.ParseError as e:
        return f"SQL inválido para BigQuery: {e}"

    if len(sentencias) != 1:
        return "Envía exactamente UNA sentencia SQL."
    consulta = sentencias[0]
    if not isinstance(consulta, exp.Query):
        return "Solo se permiten consultas de lectura (SELECT / WITH)."

    ctes = {cte.alias_or_name for cte in consulta.find_all(exp.CTE)}
    for tabla in consulta.find_all(exp.Table):
        if not tabla.name:
            continue
        if not tabla.db and tabla.name in ctes:
            continue
        if tabla.catalog and tabla.catalog != BIGQUERY_DATA_PROJECT:
            return f"Proyecto no permitido: {tabla.catalog}. Usa {BIGQUERY_DATA_PROJECT}."
        if tabla.db and tabla.db != BIGQUERY_DATASET:
            return f"Dataset no permitido: {tabla.db}. Usa {BIGQUERY_DATASET}."
        if tabla.name not in tablas_permitidas:
            return (
                f"Tabla desconocida: {tabla.name}. "
                f"Tablas disponibles: {', '.join(sorted(tablas_permitidas))}."
            )
    return None


# ============================================
# EJECUCIÓN
# ============================================
def _a_primitivo(valor):
    """Valores serializables por el checkpointer y legibles por el graficador."""
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (datetime, date, time)):
        return valor.isoformat()
    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor
    return str(valor)


def ejecutar_consulta(sql: str) -> tuple[str, dict | None]:
    """Valida y ejecuta el SQL. Devuelve (texto para el modelo, datos o None). Nunca lanza."""
    motivo = validar_sql(sql)
    if motivo:
        return f"Consulta rechazada: {motivo}", None

    try:
        with get_engine().connect() as conn:
            # exec_driver_sql: el SQL llega tal cual, sin que SQLAlchemy interprete
            # ":algo" como parámetro. Los % se duplican porque el driver de
            # BigQuery des-escapa %% → % aunque no haya parámetros.
            resultado = conn.exec_driver_sql(sql.replace("%", "%%"))
            columnas = list(resultado.keys())
            filas = resultado.fetchmany(MAX_FILAS_GRAFICO + 1)
    except Exception as e:
        mensaje = str(e)
        if "bytesBilledLimitExceeded" in mensaje or "maximum bytes billed" in mensaje.lower():
            return (
                f"Consulta rechazada por costo: procesaría más de "
                f"{BIGQUERY_MAX_BYTES_BILLED / 1024**3:.1f} GB. Selecciona menos columnas, "
                "filtra por un rango de fechas o agrega antes de devolver filas."
            ), None
        return f"Error de BigQuery: {mensaje[:800]}. Corrige el SQL y vuelve a intentarlo.", None

    if not filas:
        return "La consulta no devolvió filas.", None

    filas = [[_a_primitivo(v) for v in fila] for fila in filas[:MAX_FILAS_GRAFICO + 1]]
    total = len(filas) if len(filas) <= MAX_FILAS_GRAFICO else f"más de {MAX_FILAS_GRAFICO}"
    filas = filas[:MAX_FILAS_GRAFICO]
    datos = {"sql": sql, "columnas": columnas, "filas": filas, "total_filas": total}

    lineas = [" | ".join(columnas)]
    lineas += [" | ".join("" if v is None else str(v) for v in f) for f in filas[:MAX_FILAS_MODELO]]
    texto = "\n".join(lineas)
    if len(filas) > MAX_FILAS_MODELO:
        texto += (
            f"\n(Se muestran solo las primeras {MAX_FILAS_MODELO} de {total} filas. "
            "Usa agregaciones o LIMIT si necesitas un resumen.)"
        )
    return texto, datos


# ============================================
# FACTORY
# ============================================
def get_bigquery_tool():
    """Devuelve la tool de consulta."""

    @tool("consultar_bigquery")
    def consultar_bigquery_tool(sql: str, runtime: ToolRuntime) -> Command | str:
        """Ejecuta UNA consulta SQL de solo lectura (BigQuery Standard SQL) sobre
        los viajes de CitiBike NYC (tabla citibike_trips).

        Úsala para cualquier pregunta que se responda con datos: conteos,
        promedios, rankings, tendencias por fecha, estaciones, duración de viajes,
        tipo de usuario, etc. Las columnas están en el system prompt.

        No la uses para preguntas sobre políticas o procedimientos del negocio:
        para eso está buscar_base_conocimiento.

        Reglas del SQL:
        - Solo SELECT / WITH. Nada de INSERT, UPDATE, DELETE, CREATE, DROP.
        - Nombre de tabla completo con backticks:
          `bigquery-public-data.new_york_citibike.citibike_trips`.
        - Selecciona solo las columnas necesarias (nunca SELECT *) y agrega o
          usa LIMIT: el modelo ve como máximo 50 filas.
        - Filtra por rango de fechas cuando la pregunta lo permita: cada
          consulta tiene un tope de bytes procesados.

        Args:
            sql: la consulta completa en BigQuery Standard SQL.
        """
        print(f"   🗄️  BigQuery: {sql}")
        texto, datos = ejecutar_consulta(sql)
        if datos is None:
            return texto
        return Command(
            update={
                "ultima_consulta": datos,
                "messages": [ToolMessage(texto, tool_call_id=runtime.tool_call_id)],
            }
        )

    return consultar_bigquery_tool
