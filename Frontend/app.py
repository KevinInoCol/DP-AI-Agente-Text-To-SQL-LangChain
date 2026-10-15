"""
Interfaz de prueba (Streamlit) para el agente Text-to-SQL de CitiBike.

Cliente delgado del Backend: no sabe nada de LLMs, BigQuery ni prompts. Solo
habla con la API HTTP (POST /chat, GET /health) y muestra la respuesta, las
tools que usó el agente y los gráficos que devolvió el subagente.

La conversación vive en el Backend (checkpointer por thread_id). Aquí solo se
guarda una copia para pintar el chat; "Nueva conversación" genera otro
thread_id, así el agente empieza sin memoria.

Ejecutar (con el Backend levantado en otra terminal):
    streamlit run app.py

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import base64
import os
import uuid

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ============================================
# VARIABLES DE ENTORNO
# ============================================
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ============================================
# CONSTANTES
# ============================================
# Un turno puede encadenar BigQuery + subagente de gráficos: más de un minuto.
TIMEOUT_CHAT_S = 180
TIMEOUT_HEALTH_S = 3
PREGUNTAS_DE_EJEMPLO = [
    "¿Cuántos viajes hubo por tipo de usuario?",
    "¿Cuáles son las 10 estaciones con más viajes iniciados en 2016?",
    "¿Cómo evolucionaron los viajes mes a mes en 2017?",
    "¿Cuál es la duración promedio de los viajes por género?",
]


# ============================================
# CLIENTE DEL BACKEND
# ============================================
def backend_disponible(url: str) -> bool:
    try:
        return requests.get(f"{url}/health", timeout=TIMEOUT_HEALTH_S).ok
    except requests.RequestException:
        return False


def enviar_mensaje(url: str, thread_id: str, mensaje: str) -> dict:
    """POST /chat. Devuelve la respuesta del Backend o un dict con 'error'."""
    try:
        r = requests.post(
            f"{url}/chat",
            json={"thread_id": thread_id, "mensaje": mensaje},
            timeout=TIMEOUT_CHAT_S,
        )
    except requests.ConnectionError:
        return {"error": f"No se pudo conectar con el Backend en {url}. ¿Está levantado?"}
    except requests.Timeout:
        return {"error": f"El Backend no respondió en {TIMEOUT_CHAT_S} s."}
    if not r.ok:
        detalle = r.json().get("detail", r.text) if "json" in r.headers.get("content-type", "") else r.text
        return {"error": f"El Backend devolvió {r.status_code}: {detalle}"}
    return r.json()


# ============================================
# PINTADO
# ============================================
def pintar_turno(turno: dict) -> None:
    """Pinta un mensaje del asistente: texto, gráficos y tools usadas."""
    if "error" in turno:
        st.error(turno["error"])
        return
    st.markdown(turno["respuesta"])
    graficos = turno.get("graficos", [])
    if graficos:
        columnas = st.columns(len(graficos))
        for col, g in zip(columnas, graficos):
            with col:
                st.image(base64.b64decode(g["imagen_base64"]), width="stretch")
                st.caption(f"**{g['titulo']}** — {g['descripcion']}")
    if turno.get("tools_usadas"):
        st.caption("🔧 " + " → ".join(turno["tools_usadas"]))


def nueva_conversacion() -> None:
    st.session_state.thread_id = f"streamlit-{uuid.uuid4().hex[:8]}"
    st.session_state.historial = []


# ============================================
# APP
# ============================================
st.set_page_config(page_title="CitiBike Text-to-SQL", page_icon="🚲", layout="wide")

if "thread_id" not in st.session_state:
    nueva_conversacion()

with st.sidebar:
    st.header("⚙️ Configuración")
    url = st.text_input("URL del Backend", value=BACKEND_URL).rstrip("/")
    if backend_disponible(url):
        st.success("Backend en línea")
    else:
        st.error("Backend no disponible")

    st.divider()
    st.text_input("thread_id", key="thread_id", help="Identidad de la conversación en el Backend.")
    st.button("🧹 Nueva conversación", on_click=nueva_conversacion, width="stretch")

    st.divider()
    st.subheader("Preguntas de ejemplo")
    pregunta_ejemplo = None
    for i, p in enumerate(PREGUNTAS_DE_EJEMPLO):
        if st.button(p, key=f"ejemplo_{i}", width="stretch"):
            pregunta_ejemplo = p

st.title("🚲 CitiBike NYC — Agente Text-to-SQL")
st.caption("Interfaz de prueba. Pregunta sobre los viajes de CitiBike; el agente consulta BigQuery y genera gráficos.")

for turno in st.session_state.historial:
    with st.chat_message(turno["rol"]):
        if turno["rol"] == "user":
            st.markdown(turno["contenido"])
        else:
            pintar_turno(turno["contenido"])

mensaje = st.chat_input("Escribe tu pregunta…") or pregunta_ejemplo
if mensaje:
    st.session_state.historial.append({"rol": "user", "contenido": mensaje})
    with st.chat_message("user"):
        st.markdown(mensaje)
    with st.chat_message("assistant"):
        with st.spinner("Consultando BigQuery y preparando la respuesta…"):
            turno = enviar_mensaje(url, st.session_state.thread_id, mensaje)
        pintar_turno(turno)
    st.session_state.historial.append({"rol": "assistant", "contenido": turno})
