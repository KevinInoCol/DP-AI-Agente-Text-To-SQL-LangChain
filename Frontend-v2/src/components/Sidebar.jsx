/**
 * Panel lateral: estado del Backend, thread_id, nueva conversación y
 * preguntas de ejemplo. En móvil se abre como cajón.
 */
import { BACKEND_URL } from "../api.js";

const PREGUNTAS_DE_EJEMPLO = [
  "¿Cuántos viajes hubo por tipo de usuario?",
  "¿Cuáles son las 10 estaciones con más viajes iniciados en 2016?",
  "¿Cómo evolucionaron los viajes mes a mes en 2017?",
  "¿Cuál es la duración promedio de los viajes por género?",
];

export default function Sidebar({ abierto, onCerrar, online, threadId, onThreadId, onNuevaConversacion, onEjemplo, enviando }) {
  const estado = online === null ? "comprobando" : online ? "online" : "offline";
  const etiqueta = { comprobando: "Comprobando…", online: "Backend en línea", offline: "Backend no disponible" }[estado];

  return (
    <>
      <div className={`velo ${abierto ? "visible" : ""}`} onClick={onCerrar} />
      <aside className={`sidebar ${abierto ? "abierto" : ""}`}>
        <div className="sidebar-cabecera">
          <h2>⚙️ Configuración</h2>
          <button className="icon-btn cerrar-btn" onClick={onCerrar} aria-label="Cerrar menú">
            ✕
          </button>
        </div>

        <div className={`estado ${estado}`}>
          <span className="punto" />
          <div>
            <strong>{etiqueta}</strong>
            <code>{BACKEND_URL}</code>
          </div>
        </div>

        <hr />

        <label className="campo">
          <span>thread_id</span>
          <input value={threadId} onChange={(e) => onThreadId(e.target.value)} title="Identidad de la conversación en el Backend." />
        </label>
        <button className="btn-secundario" onClick={onNuevaConversacion} disabled={enviando}>
          🧹 Nueva conversación
        </button>

        <hr />

        <h3>Preguntas de ejemplo</h3>
        <div className="ejemplos">
          {PREGUNTAS_DE_EJEMPLO.map((p) => (
            <button key={p} className="btn-ejemplo" onClick={() => onEjemplo(p)} disabled={enviando}>
              {p}
            </button>
          ))}
        </div>
      </aside>
    </>
  );
}
