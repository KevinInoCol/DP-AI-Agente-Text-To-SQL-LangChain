/**
 * Cliente del Backend (FastAPI).
 *
 * Cliente delgado: no sabe nada de LLMs, BigQuery ni prompts. Solo conoce
 * POST /chat y GET /health, siempre a través del proxy /api de Vite.
 *
 * Autor: Ing. Kevin Inofuente Colque - DataPath
 */

// ============================================
// CONSTANTES
// ============================================
const API = "/api";
// Un turno puede encadenar BigQuery + subagente de gráficos: más de un minuto.
const TIMEOUT_CHAT_MS = 180_000;
const TIMEOUT_HEALTH_MS = 3_000;
export const BACKEND_URL = __BACKEND_URL__;

// ============================================
// ENDPOINTS
// ============================================
export async function backendDisponible() {
  try {
    const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(TIMEOUT_HEALTH_MS) });
    return r.ok;
  } catch {
    return false;
  }
}

/** POST /chat. Devuelve la respuesta del Backend o un objeto con `error`. */
export async function enviarMensaje(threadId, mensaje) {
  let r;
  try {
    r = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread_id: threadId, mensaje }),
      signal: AbortSignal.timeout(TIMEOUT_CHAT_MS),
    });
  } catch (e) {
    if (e.name === "TimeoutError") {
      return { error: `El Backend no respondió en ${TIMEOUT_CHAT_MS / 1000} s.` };
    }
    return { error: `No se pudo conectar con el Backend en ${BACKEND_URL}. ¿Está levantado?` };
  }
  if (!r.ok) {
    // El proxy de Vite responde 502/504 cuando el Backend está caído
    const esJson = (r.headers.get("content-type") || "").includes("json");
    const detalle = esJson ? (await r.json()).detail : await r.text();
    return { error: `El Backend devolvió ${r.status}: ${detalle || r.statusText}` };
  }
  return r.json();
}
