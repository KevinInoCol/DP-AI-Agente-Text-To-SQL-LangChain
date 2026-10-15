"""Subagente de gráficos: decide (agente.py) y dibuja (renderizado.py)."""

from subagentes.graficos.agente import init_subagente_graficos, planificar_graficos
from subagentes.graficos.especificacion import Grafico, PlanGraficos
from subagentes.graficos.renderizado import renderizar

__all__ = [
    "Grafico",
    "PlanGraficos",
    "init_subagente_graficos",
    "planificar_graficos",
    "renderizar",
]
