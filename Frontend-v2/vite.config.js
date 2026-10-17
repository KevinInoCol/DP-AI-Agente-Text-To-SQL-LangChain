/**
 * Configuración de Vite.
 *
 * El navegador solo habla con /api; Vite lo reenvía al Backend (BACKEND_URL)
 * quitando el prefijo. Así el Backend no necesita CORS y la URL real no se
 * incrusta en el bundle.
 *
 * Autor: Ing. Kevin Inofuente Colque - DataPath
 */
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command, mode }) => {
  // Prefijo "" para leer también variables sin VITE_ (no se exponen al cliente)
  const env = loadEnv(mode, process.cwd(), "");
  const backendUrl = (env.BACKEND_URL || "http://localhost:8000").replace(/\/$/, "");

  const proxy = {
    "/api": {
      target: backendUrl,
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ""),
      // Un turno puede encadenar BigQuery + subagente de gráficos: más de un minuto
      timeout: 180_000,
      proxyTimeout: 180_000,
    },
  };

  return {
    plugins: [react()],
    server: { port: 5173, proxy },
    preview: { port: 4173, proxy },
    // Solo para mostrar en el panel. En Vercel el destino real lo fija el
    // rewrite de vercel.json; sin BACKEND_URL en el build no hay Backend.
    define: {
      __BACKEND_URL__: JSON.stringify(env.BACKEND_URL || command === "serve" ? backendUrl : "no configurado"),
    },
  };
});
