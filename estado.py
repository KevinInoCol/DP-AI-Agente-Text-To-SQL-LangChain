"""
Estado del agente orquestador: el contexto que comparten sus tools.

- ultima_consulta: el resultado de la última consulta a BigQuery
  ({"sql", "columnas", "filas", "total_filas"}). Lo escribe consultar_bigquery
  y lo lee generar_graficos. Los datos viajan por el estado, no por el texto
  del LLM: el modelo no tiene que copiar los números, así que no puede
  alterarlos. Se guarda en el checkpointer, así que "grafícalo" funciona
  también en el turno siguiente.
- graficos_turno: los gráficos generados en el turno actual
  ([{"titulo", "descripcion", "tipo", "archivo"}]). agent.responder() lo
  reinicia en cada invocación y lo devuelve al entrypoint.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

from typing_extensions import NotRequired

from langchain.agents import AgentState


class EstadoAgente(AgentState):
    ultima_consulta: NotRequired[dict]
    graficos_turno: NotRequired[list[dict]]
