"""
Tool: delegar en el subagente de gráficos (patrón "subagente como tool").

Flujo:
  1. consultar_bigquery deja el resultado en el estado (ultima_consulta).
  2. El orquestador llama a generar_graficos con una instrucción en lenguaje
     natural (qué quiere destacar).
  3. Esta tool toma los datos del estado, se los pasa al subagente junto con
     la instrucción, y el subagente devuelve 1 o 2 especificaciones.
  4. renderizar() dibuja cada una como PNG en GRAFICOS_DIR/<thread_id>/.
  5. Los gráficos se registran en el estado (graficos_turno) para que el
     entrypoint los entregue, y el orquestador recibe solo títulos y
     descripciones para mencionarlos en su respuesta.

Tool compartida: el thread_id se lee del runtime, no de una clausura.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import re
import uuid
from pathlib import Path

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

from subagentes.graficos import planificar_graficos, renderizar

# ============================================
# CONSTANTES
# ============================================
GRAFICOS_DIR = Path(__file__).resolve().parent.parent / "graficos_generados"


def _carpeta_del_hilo(thread_id: str) -> Path:
    return GRAFICOS_DIR / re.sub(r"[^A-Za-z0-9_-]", "_", thread_id)


# ============================================
# FUNCIÓN IMPERATIVA
# ============================================
def generar_graficos(instruccion: str, datos: dict, carpeta: Path) -> tuple[list[dict], list[str]]:
    """Planifica con el subagente y dibuja. Devuelve (gráficos, errores). No lanza."""
    try:
        plan = planificar_graficos(instruccion, datos)
    except Exception as e:
        return [], [f"el subagente de gráficos falló: {e}"]

    graficos, errores = [], []
    for g in plan.graficos:
        ruta = carpeta / f"{uuid.uuid4().hex[:12]}.png"
        try:
            renderizar(g, datos, ruta)
        except Exception as e:
            errores.append(f"'{g.titulo}' no se pudo dibujar: {e}")
            continue
        graficos.append(
            {"titulo": g.titulo, "descripcion": g.descripcion, "tipo": g.tipo, "archivo": str(ruta)}
        )
    return graficos, errores


# ============================================
# FACTORY
# ============================================
def get_graficos_tool():
    """Devuelve la tool que invoca al subagente de gráficos."""

    @tool("generar_graficos")
    def generar_graficos_tool(instruccion: str, runtime: ToolRuntime) -> Command | str:
        """Genera 1 o 2 gráficos con el resultado de la ÚLTIMA consulta a
        consultar_bigquery. Los datos se toman automáticamente: no los copies.

        Úsala justo después de una consulta exitosa cuyo resultado tenga varias
        filas comparables: rankings, evoluciones en el tiempo, distribuciones,
        comparaciones entre categorías. También cuando el usuario pida un gráfico.

        No la uses si el resultado es un único número, si la consulta falló o
        si todavía no consultaste BigQuery.

        Args:
            instruccion: qué debe destacar el gráfico, en una frase
                (ej: 'comparar los viajes por tipo de usuario',
                'mostrar la evolución mensual de viajes en 2016').
        """
        datos = runtime.state.get("ultima_consulta")
        if not datos:
            return "No hay datos para graficar: primero ejecuta consultar_bigquery."

        thread_id = runtime.config.get("configurable", {}).get("thread_id", "sin_hilo")
        print(f"   📊 Subagente de gráficos: '{instruccion}'")
        graficos, errores = generar_graficos(instruccion, datos, _carpeta_del_hilo(thread_id))

        if not graficos:
            return "No se pudo generar ningún gráfico: " + "; ".join(errores)

        resumen = "Gráficos generados (se entregan al usuario junto con tu respuesta):\n"
        resumen += "\n".join(f"- {g['titulo']}: {g['descripcion']}" for g in graficos)
        if errores:
            resumen += "\nDescartados: " + "; ".join(errores)
        return Command(
            update={
                "graficos_turno": [*runtime.state.get("graficos_turno", []), *graficos],
                "messages": [ToolMessage(resumen, tool_call_id=runtime.tool_call_id)],
            }
        )

    return generar_graficos_tool
