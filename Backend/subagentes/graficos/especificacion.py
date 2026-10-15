"""
Contrato de salida del subagente de gráficos (structured output).

El subagente NO dibuja: decide QUÉ graficar y lo devuelve con este esquema.
El dibujo lo hace renderizado.py con código determinista, así un error del
modelo nunca produce un gráfico con números inventados: como mucho, un
gráfico que no se puede dibujar y se descarta.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

from typing import Literal

from pydantic import BaseModel, Field

TipoGrafico = Literal[
    "barras",
    "barras_horizontales",
    "lineas",
    "area",
    "dispersion",
    "torta",
    "histograma",
]


class Grafico(BaseModel):
    """Un gráfico construido a partir de las columnas del resultado."""

    tipo: TipoGrafico = Field(description="Tipo de gráfico más adecuado para los datos.")
    titulo: str = Field(description="Título corto y descriptivo, en español.")
    descripcion: str = Field(
        description="Una frase con lo que muestra el gráfico o el hallazgo principal."
    )
    columna_x: str = Field(
        description="Columna del eje X (categoría, fecha o, en histograma, la variable numérica)."
    )
    columnas_y: list[str] = Field(
        default_factory=list,
        description="Columnas numéricas del eje Y (1 a 3). Vacía solo en histograma.",
    )
    etiqueta_x: str = Field(default="", description="Rótulo legible del eje X.")
    etiqueta_y: str = Field(default="", description="Rótulo legible del eje Y.")
    ordenar: Literal["ninguno", "asc", "desc"] = Field(
        default="ninguno",
        description="Orden de las barras según la primera columna Y. Ignorado en líneas.",
    )
    top_n: int | None = Field(
        default=None,
        description="Mostrar solo las primeras N categorías tras ordenar (barras y torta).",
    )


class PlanGraficos(BaseModel):
    """Los gráficos que el subagente propone para un resultado."""

    graficos: list[Grafico] = Field(
        min_length=1,
        max_length=2,
        description="Uno o dos gráficos. Dos solo si muestran aspectos distintos de los datos.",
    )
