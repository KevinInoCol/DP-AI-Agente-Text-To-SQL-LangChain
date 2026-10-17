---
name: vercel-deploy-frontend-v2
description: Despliega Frontend-v2 (React + Vite) del agente Text-to-SQL CitiBike a Vercel con la CLI (proyecto `citibike-text-to-sql`), y lo conecta al Backend FastAPI con un rewrite `/api/*` en `vercel.json`. Cubre el primer despliegue, el redespliegue cuando el Backend ya tiene URL pública, la verificación y los errores típicos. Use when the user asks to "desplegar el Frontend-v2", "subir el frontend a Vercel", "redesplegar el frontend", "conectar el frontend con el backend desplegado", "vercel.json", "/api da 404 en Vercel", or types /vercel-deploy-frontend-v2.
---

# Despliegue de Frontend-v2 a Vercel (CLI)

| Dato | Valor |
|---|---|
| Proyecto Vercel | `citibike-text-to-sql` (cuenta personal `kevininocol`, scope `kevininocols-projects`) |
| URL de producción | https://citibike-text-to-sql.vercel.app |
| Carpeta desplegada | `Frontend-v2/` (la CLI se ejecuta **desde ahí**; no hace falta Root Directory) |
| Framework | Vite (detectado solo: `npm run build` → `dist/`) |
| Script | `.claude/skills/vercel-deploy-frontend-v2/scripts/deploy.sh` |

## Cómo llega el Frontend al Backend

El código del navegador **solo** llama a rutas relativas `/api/...` (`src/api.js`). Quién
resuelve `/api` depende del entorno:

| Entorno | Quién reenvía `/api/*` | Dónde se configura |
|---|---|---|
| Local (`npm run dev` / `preview`) | Proxy de Vite | `BACKEND_URL` en `Frontend-v2/.env` → `vite.config.js` |
| Vercel | Rewrite externo de Vercel | `Frontend-v2/vercel.json` |

Así el Backend **no necesita CORS** y el Frontend sigue sin importar nada de `Backend/`
(regla de `CLAUDE.md`). El proxy de Vite **no existe** en Vercel: sin `vercel.json`,
`/api/health` devuelve 404 y la UI muestra "Backend no disponible".

`BACKEND_URL` también se pasa al build (`--build-env`) pero **solo para mostrarlo** en el
panel lateral. Sin él, el panel dice "no configurado". El destino real es el rewrite.

## Workflow

### 1. Decidir el tipo de despliegue

- Por defecto **preview**. Producción (`--prod`) solo si el usuario lo pide en la
  conversación actual; si no lo dijo, confirma antes.
- Si el usuario da la URL pública del Backend (Cloud Run, etc.), pásala con `--backend`.
  Debe ser `https://` y responder `GET /health` → `{"status":"ok"}`. Compruébalo antes:
  `curl -s <url>/health`.

### 2. Ejecutar el script

```bash
# Primer despliegue / redespliegue sin Backend (estado actual)
bash .claude/skills/vercel-deploy-frontend-v2/scripts/deploy.sh --prod

# Cuando el Backend ya está desplegado
bash .claude/skills/vercel-deploy-frontend-v2/scripts/deploy.sh --prod --backend https://<backend-publico>

# Preview para probar un cambio sin tocar producción
bash .claude/skills/vercel-deploy-frontend-v2/scripts/deploy.sh
```

El script hace, en orden:
1. Verifica `vercel` instalado y logueado (`vercel whoami`).
2. Con `--backend`, escribe `vercel.json` con el rewrite. Sin el flag, respeta el que exista.
3. `npm ci` + `npm run build` local. **Si el build falla, no sube nada.**
4. `vercel link --yes --project citibike-text-to-sql` si falta `.vercel/project.json`.
5. `vercel deploy [--prod] --yes [--build-env BACKEND_URL=...]`.
6. Imprime la URL y el código HTTP de `/` y `/api/health`.

### 3. Verificar

- `/` → 200 siempre.
- `/api/health` → **200** si hay Backend; **404** si no hay `vercel.json` (esperado sin Backend).
- Con Backend: abrir la URL, ver "Backend en línea" y hacer una pregunta **con gráficos**
  (p. ej. "¿Cómo evolucionaron los viajes mes a mes en 2017?") midiendo el tiempo.

### 4. Después de cambiar `vercel.json`

`vercel.json` es parte del código: tras un `--backend` nuevo, avisa al usuario de que hay
que commitearlo. No hagas commit ni push como parte del despliegue.

## Riesgo conocido: tiempo de espera del rewrite

Un turno del agente (BigQuery + subagente de gráficos) puede tardar más de un minuto. La
documentación de Vercel no deja claro cuánto espera un rewrite externo antes de cortar.
Si la pregunta larga falla con **504** / `ROUTER_EXTERNAL_TARGET_ERROR` mientras
`/api/health` sí responde, el plan B es:

1. En `Backend/app.py`, `CORSMiddleware` con `allow_origins` limitado a
   `https://citibike-text-to-sql.vercel.app` (y el dominio de previews si hace falta).
2. En `src/api.js`, usar `import.meta.env.VITE_BACKEND_URL ?? "/api"` como base.
3. Desplegar con `--build-env VITE_BACKEND_URL=https://<backend>` y quitar el rewrite.

Pide confirmación antes: toca el Backend.

## Troubleshooting

| Síntoma | Causa / solución |
|---|---|
| UI: "Backend no disponible", `/api/health` 404 | No hay `vercel.json` o el rewrite apunta mal. Redesplegar con `--backend`. |
| `/api/health` 502/504 enseguida | El Backend está caído o la URL no es pública. Probar `curl <backend>/health`. |
| La UI muestra "no configurado" | Se desplegó sin `BACKEND_URL` en el build. Es solo cosmético. |
| `.env.example` aparece ignorado por git | `vercel link` crea `Frontend-v2/.gitignore` con `.env*`. Debe tener la línea `!.env.example` (ya añadida). |
| Aparece `Frontend-v2/.env.local` | Lo crea `vercel link` con un `VERCEL_OIDC_TOKEN`. Está ignorado; **no lo leas ni lo imprimas** (skill `env-secrets-use-dont-read`). |
| Preview devuelve **302** (login de Vercel) en `/` y `/api/health` | Comportamiento por defecto: Deployment Protection (Vercel Authentication) protege los previews. Ábrelo en el navegador logueado; `curl` no puede verificarlo. Producción está abierta. |
| Build falla en Vercel pero no en local | Versión de Node: el proyecto usa Node 24.x en Vercel. Comparar con `node -v` local. |

## Historial

- 2026-10-16: primer despliegue a producción, **sin Backend** (sin `vercel.json`).
  Pendiente: redesplegar con `--backend` cuando el Backend tenga URL pública.
