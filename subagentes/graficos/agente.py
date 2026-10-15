"""
Subagente de gráficos: recibe la instrucción del orquestador y el perfil de los
datos, y decide 1 o 2 gráficos (PlanGraficos) con structured output.

Patrón "subagente como tool" de LangChain: el orquestador no ve su
razonamiento, solo el resultado (tools/graficos.py). Contexto aislado: al
subagente le llega un perfil compacto de los datos (columnas, tipos, muestra),
no la conversación.

Config: model_config/model.yaml (bloque subagentes.graficos)
Prompt: prompt/graficos_prompt.yaml

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import json

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from subagentes.graficos.especificacion import PlanGraficos

# ============================================
# CONSTANTES
# ============================================
FILAS_DE_MUESTRA = 15

# Singleton: se crea UNA vez en init_subagente_graficos()
_subagente = None


# ============================================
# FUNCIONES PÚBLICAS
# ============================================
def init_subagente_graficos(llm_cfg: dict, system_prompt: str) -> None:
    """Una vez al arrancar."""
    global _subagente
    _subagente = create_agent(
        model=init_chat_model(
            llm_cfg["model"],
            model_provider=llm_cfg["provider"],
            temperature=llm_cfg["temperature"],
        ),
        tools=[],
        system_prompt=system_prompt,
        response_format=PlanGraficos,
    )


def perfil_de_datos(datos: dict) -> str:
    """Resumen compacto del resultado: columnas con tipo y cardinalidad + muestra."""
    columnas = []
    for i, nombre in enumerate(datos["columnas"]):
        valores = [f[i] for f in datos["filas"] if f[i] is not None]
        if valores and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in valores):
            tipo = f"numérico (min {min(valores):,.2f}, max {max(valores):,.2f})"
        else:
            tipo = "texto o fecha"
        columnas.append(f"- {nombre}: {tipo}, {len(set(map(str, valores)))} valores distintos")
    muestra = [dict(zip(datos["columnas"], f)) for f in datos["filas"][:FILAS_DE_MUESTRA]]
    return (
        f"SQL ejecutado:\n{datos['sql']}\n\n"
        f"Filas disponibles para graficar: {len(datos['filas'])}"
        f" (de {datos['total_filas']} devueltas por la consulta)\n\n"
        "Columnas:\n" + "\n".join(columnas) + "\n\n"
        f"Primeras {len(muestra)} filas:\n" + json.dumps(muestra, ensure_ascii=False, default=str)
    )


def planificar_graficos(instruccion: str, datos: dict) -> PlanGraficos:
    """Invoca al subagente y devuelve su plan validado por Pydantic."""
    if _subagente is None:
        raise RuntimeError("Llama a init_subagente_graficos() al arrancar")
    mensaje = (
        f"Instrucción del analista: {instruccion}\n\n"
        f"{perfil_de_datos(datos)}"
    )
    resultado = _subagente.invoke({"messages": [{"role": "user", "content": mensaje}]})
    return resultado["structured_response"]
