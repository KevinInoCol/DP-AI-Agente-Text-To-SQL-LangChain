"""
Dibujo determinista de un Grafico (especificacion.py) con matplotlib → PNG.

Valida la especificación contra los datos reales antes de dibujar: si una
columna no existe o no es numérica donde debe serlo, lanza ValueError y el
gráfico se descarta. Nunca completa ni inventa valores.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin ventana: corre en un servidor

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from subagentes.graficos.especificacion import Grafico  # noqa: E402

# ============================================
# CONSTANTES
# ============================================
MAX_CATEGORIAS = 20   # barras: más que esto es ilegible
MAX_PORCIONES = 8     # torta: el resto se agrupa en "Otros"
TAMANO_FIGURA = (10, 5.5)
DPI = 120
COLORES = ["#2563eb", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4", "#84cc16", "#ec4899"]


# ============================================
# AUXILIARES
# ============================================
def _es_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _a_fecha(v):
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v)
        except ValueError:
            return None
    return None


def _columna(datos: dict, nombre: str) -> list:
    if nombre not in datos["columnas"]:
        raise ValueError(f"la columna '{nombre}' no existe ({', '.join(datos['columnas'])})")
    i = datos["columnas"].index(nombre)
    return [fila[i] for fila in datos["filas"]]


def _numerica(datos: dict, nombre: str) -> list[float]:
    valores = _columna(datos, nombre)
    if not all(v is None or _es_numero(v) for v in valores):
        raise ValueError(f"la columna '{nombre}' no es numérica")
    return [float("nan") if v is None else float(v) for v in valores]


def _formato_miles(valor, _pos) -> str:
    return f"{valor:,.0f}" if abs(valor) >= 1000 else f"{valor:,.2f}".rstrip("0").rstrip(".")


def _ordenar_y_recortar(g: Grafico, x: list, ys: list[list[float]], limite: int):
    indices = list(range(len(x)))
    if g.ordenar != "ninguno":
        indices.sort(key=lambda i: ys[0][i], reverse=g.ordenar == "desc")
    n = min(g.top_n or limite, limite)
    indices = indices[:n]
    return [x[i] for i in indices], [[y[i] for i in indices] for y in ys]


# ============================================
# FUNCIÓN PÚBLICA
# ============================================
def renderizar(g: Grafico, datos: dict, ruta: Path) -> None:
    """Dibuja el gráfico y lo guarda como PNG en `ruta`. Lanza ValueError si no es dibujable."""
    if not datos.get("filas"):
        raise ValueError("no hay filas para graficar")

    fig, ax = plt.subplots(figsize=TAMANO_FIGURA)
    try:
        if g.tipo == "histograma":
            valores = [v for v in _numerica(datos, g.columna_x) if v == v]
            ax.hist(valores, bins="auto", color=COLORES[0], edgecolor="white")
            ax.set_ylabel(g.etiqueta_y or "Frecuencia")
        else:
            if not g.columnas_y:
                raise ValueError(f"el tipo '{g.tipo}' necesita al menos una columna Y")
            x = _columna(datos, g.columna_x)
            ys = [_numerica(datos, c) for c in g.columnas_y[:3]]

            if g.tipo in ("barras", "barras_horizontales"):
                x, ys = _ordenar_y_recortar(g, x, ys, MAX_CATEGORIAS)
                etiquetas = [str(v) for v in x]
                ancho = 0.8 / len(ys)
                for k, (col, y) in enumerate(zip(g.columnas_y, ys)):
                    posiciones = [i + (k - (len(ys) - 1) / 2) * ancho for i in range(len(x))]
                    if g.tipo == "barras":
                        ax.bar(posiciones, y, width=ancho, label=col, color=COLORES[k])
                    else:
                        ax.barh(posiciones, y, height=ancho, label=col, color=COLORES[k])
                if g.tipo == "barras":
                    ax.set_xticks(range(len(x)), etiquetas, rotation=45 if max(map(len, etiquetas)) > 8 else 0, ha="right")
                else:
                    ax.set_yticks(range(len(x)), etiquetas)
                    ax.invert_yaxis()

            elif g.tipo in ("lineas", "area"):
                fechas = [_a_fecha(v) for v in x]
                if all(f is not None for f in fechas):
                    x = fechas
                orden = sorted(range(len(x)), key=lambda i: x[i])
                x = [x[i] for i in orden]
                for k, (col, y) in enumerate(zip(g.columnas_y, ys)):
                    y = [y[i] for i in orden]
                    ax.plot(x, y, marker="o" if len(x) <= 30 else None, label=col, color=COLORES[k])
                    if g.tipo == "area":
                        ax.fill_between(x, y, alpha=0.2, color=COLORES[k])
                fig.autofmt_xdate()

            elif g.tipo == "dispersion":
                ax.scatter(_numerica(datos, g.columna_x), ys[0], alpha=0.6, color=COLORES[0])

            elif g.tipo == "torta":
                pares = sorted(zip(x, ys[0]), key=lambda p: p[1], reverse=True)
                if len(pares) > MAX_PORCIONES:
                    resto = sum(v for _, v in pares[MAX_PORCIONES - 1:])
                    pares = pares[: MAX_PORCIONES - 1] + [("Otros", resto)]
                ax.pie(
                    [v for _, v in pares],
                    labels=[str(e) for e, _ in pares],
                    autopct="%1.1f%%",
                    colors=COLORES,
                    startangle=90,
                )
                ax.axis("equal")

            if len(ys) > 1 and g.tipo != "torta":
                ax.legend()

        if g.tipo != "torta":
            # En barras horizontales las categorías (X lógico) van en el eje vertical
            if g.tipo == "barras_horizontales":
                ax.set_ylabel(g.etiqueta_x)
                ax.set_xlabel(g.etiqueta_y)
            else:
                ax.set_xlabel(g.etiqueta_x)
                if g.tipo != "histograma":
                    ax.set_ylabel(g.etiqueta_y)
            eje = ax.xaxis if g.tipo == "barras_horizontales" else ax.yaxis
            eje.set_major_formatter(FuncFormatter(_formato_miles))
            ax.grid(axis="x" if g.tipo == "barras_horizontales" else "y", alpha=0.3)
            ax.spines[["top", "right"]].set_visible(False)

        ax.set_title(g.titulo, fontsize=13, fontweight="bold", loc="left")
        fig.tight_layout()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(ruta, dpi=DPI)
    finally:
        plt.close(fig)
