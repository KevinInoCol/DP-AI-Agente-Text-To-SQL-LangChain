/**
 * Interfaz de prueba (React) para el agente Text-to-SQL de CitiBike.
 *
 * Versión 2 de Frontend/ (Streamlit): mismas funciones — chat, gráficos del
 * subagente, tools usadas, thread_id editable, nueva conversación y preguntas
 * de ejemplo — sobre la misma API HTTP del Backend.
 *
 * La conversación vive en el Backend (checkpointer por thread_id). Aquí solo
 * se guarda una copia para pintar el chat; "Nueva conversación" genera otro
 * thread_id, así el agente empieza sin memoria.
 *
 * Autor: Ing. Kevin Inofuente Colque - DataPath
 */
import { useEffect, useRef, useState } from "react";

import { backendDisponible, enviarMensaje } from "./api.js";
import Mensaje from "./components/Mensaje.jsx";
import Sidebar from "./components/Sidebar.jsx";

// ============================================
// CONSTANTES
// ============================================
const INTERVALO_HEALTH_MS = 15_000;

const nuevoThreadId = () => `react-${crypto.randomUUID().replaceAll("-", "").slice(0, 8)}`;

export default function App() {
  const [threadId, setThreadId] = useState(nuevoThreadId);
  const [historial, setHistorial] = useState([]);
  const [enviando, setEnviando] = useState(false);
  const [online, setOnline] = useState(null);
  const [texto, setTexto] = useState("");
  const [menuAbierto, setMenuAbierto] = useState(false);
  const finRef = useRef(null);

  useEffect(() => {
    const comprobar = () => backendDisponible().then(setOnline);
    comprobar();
    const id = setInterval(comprobar, INTERVALO_HEALTH_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [historial, enviando]);

  function nuevaConversacion() {
    setThreadId(nuevoThreadId());
    setHistorial([]);
  }

  async function enviar(mensaje) {
    mensaje = mensaje.trim();
    if (!mensaje || enviando) return;
    setTexto("");
    setMenuAbierto(false);
    setHistorial((h) => [...h, { rol: "user", contenido: mensaje }]);
    setEnviando(true);
    const turno = await enviarMensaje(threadId, mensaje);
    setHistorial((h) => [...h, { rol: "assistant", contenido: turno }]);
    setEnviando(false);
  }

  function onKeyDown(e) {
    // Enter envía; Shift+Enter hace salto de línea
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      enviar(texto);
    }
  }

  return (
    <div className="layout">
      <Sidebar
        abierto={menuAbierto}
        onCerrar={() => setMenuAbierto(false)}
        online={online}
        threadId={threadId}
        onThreadId={setThreadId}
        onNuevaConversacion={nuevaConversacion}
        onEjemplo={enviar}
        enviando={enviando}
      />

      <main className="chat">
        <header className="chat-header">
          <button className="icon-btn menu-btn" onClick={() => setMenuAbierto(true)} aria-label="Abrir menú">
            ☰
          </button>
          <div>
            <h1>🚲 CitiBike NYC — Agente Text-to-SQL</h1>
            <p className="subtitulo">
              Interfaz de prueba. Pregunta sobre los viajes de CitiBike; el agente consulta BigQuery y genera
              gráficos.
            </p>
          </div>
        </header>

        <section className="mensajes">
          {historial.length === 0 && (
            <div className="vacio">
              <span className="vacio-icono">💬</span>
              <p>Escribe una pregunta o elige un ejemplo del panel lateral.</p>
            </div>
          )}
          {historial.map((turno, i) => (
            <Mensaje key={i} rol={turno.rol} contenido={turno.contenido} />
          ))}
          {enviando && (
            <div className="burbuja assistant pensando">
              <span className="spinner" /> Consultando BigQuery y preparando la respuesta…
            </div>
          )}
          <div ref={finRef} />
        </section>

        <form
          className="entrada"
          onSubmit={(e) => {
            e.preventDefault();
            enviar(texto);
          }}
        >
          <textarea
            rows={1}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Escribe tu pregunta…"
            disabled={enviando}
          />
          <button type="submit" className="btn-primario" disabled={enviando || !texto.trim()}>
            Enviar
          </button>
        </form>
      </main>
    </div>
  );
}
