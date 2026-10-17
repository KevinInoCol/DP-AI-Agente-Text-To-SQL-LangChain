/**
 * Un mensaje del chat. El del asistente pinta texto (markdown), gráficos y
 * tools usadas; si el turno falló, solo el error.
 */
import { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function Mensaje({ rol, contenido }) {
  if (rol === "user") {
    return <div className="burbuja user">{contenido}</div>;
  }
  if (contenido.error) {
    return <div className="burbuja assistant error">⚠️ {contenido.error}</div>;
  }
  const { respuesta, graficos = [], tools_usadas: tools = [] } = contenido;

  return (
    <div className="burbuja assistant">
      <div className="markdown">
        <Markdown remarkPlugins={[remarkGfm]}>{respuesta}</Markdown>
      </div>
      {graficos.length > 0 && (
        <div className="graficos">
          {graficos.map((g, i) => (
            <Grafico key={i} grafico={g} />
          ))}
        </div>
      )}
      {tools.length > 0 && (
        <div className="tools">
          🔧
          {tools.map((t, i) => (
            <span key={i} className="tool">
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function Grafico({ grafico }) {
  const [ampliado, setAmpliado] = useState(false);
  const src = `data:image/png;base64,${grafico.imagen_base64}`;
  const archivo = `${grafico.titulo.replace(/[^\p{L}\p{N}]+/gu, "_")}.png`;

  return (
    <figure className="grafico">
      <img src={src} alt={grafico.titulo} onClick={() => setAmpliado(true)} />
      <figcaption>
        <strong>{grafico.titulo}</strong> — {grafico.descripcion}
        <a href={src} download={archivo} className="descargar">
          Descargar PNG
        </a>
      </figcaption>
      {ampliado && (
        <div className="lightbox" onClick={() => setAmpliado(false)}>
          <img src={src} alt={grafico.titulo} />
        </div>
      )}
    </figure>
  );
}
