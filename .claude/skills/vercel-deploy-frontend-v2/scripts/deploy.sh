#!/usr/bin/env bash
# ============================================
# Despliega Frontend-v2 (React + Vite) a Vercel con la CLI.
#
# Uso (desde cualquier carpeta del repo):
#   bash .claude/skills/vercel-deploy-frontend-v2/scripts/deploy.sh [--prod] [--backend https://url-del-backend]
#
#   --prod      Despliega a producción (por defecto: preview).
#   --backend   Escribe Frontend-v2/vercel.json con el rewrite /api/* → <url>/*.
#               Sin este flag se respeta el vercel.json que exista (o ninguno).
#
# Autor: Ing. Kevin Inofuente Colque - DataPath
# ============================================
set -euo pipefail

PROYECTO_VERCEL="citibike-text-to-sql"
URL_PRODUCCION="https://${PROYECTO_VERCEL}.vercel.app"

PROD=0
BACKEND=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prod) PROD=1; shift ;;
    --backend) BACKEND="${2:-}"; shift 2 ;;
    *) echo "✗ Argumento desconocido: $1"; exit 2 ;;
  esac
done

RAIZ="$(git rev-parse --show-toplevel)"
cd "$RAIZ/Frontend-v2"

# ---------- 1. Preflight ----------
command -v vercel >/dev/null || { echo "✗ Falta la CLI: npm i -g vercel"; exit 1; }
USUARIO="$(vercel whoami 2>/dev/null)" || { echo "✗ No hay sesión: vercel login"; exit 1; }
echo "✓ Vercel CLI como: $USUARIO"

# ---------- 2. Rewrite /api → Backend ----------
if [[ -n "$BACKEND" ]]; then
  [[ "$BACKEND" =~ ^https:// ]] || { echo "✗ --backend debe ser una URL https:// pública"; exit 1; }
  BACKEND="${BACKEND%/}"
  cat > vercel.json <<EOF
{
  "\$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [
    { "source": "/api/:path*", "destination": "${BACKEND}/:path*" }
  ]
}
EOF
  echo "✓ vercel.json: /api/* → ${BACKEND}/*"
elif [[ -f vercel.json ]]; then
  BACKEND="$(node -e 'const r=require("./vercel.json").rewrites||[];const d=(r.find(x=>x.source==="/api/:path*")||{}).destination||"";console.log(d.replace(/\/:path\*$/,""))')"
  echo "✓ vercel.json existente: /api/* → ${BACKEND:-(sin rewrite /api)}"
else
  echo "! Sin vercel.json: /api devolverá 404 y la UI mostrará 'Backend no disponible'"
fi

# ---------- 3. Build local (si falla, no se sube) ----------
npm ci --silent
npm run build >/dev/null || { echo "✗ npm run build falló; corrígelo antes de desplegar"; exit 1; }
rm -rf dist
echo "✓ Build local OK"

# ---------- 4. Link ----------
if [[ ! -f .vercel/project.json ]]; then
  vercel link --yes --project "$PROYECTO_VERCEL"
fi

# ---------- 5. Deploy ----------
ARGS=(deploy --yes)
[[ $PROD -eq 1 ]] && ARGS+=(--prod)
# BACKEND_URL en el build solo sirve para mostrarlo en el panel lateral
[[ -n "$BACKEND" ]] && ARGS+=(--build-env "BACKEND_URL=$BACKEND")

INICIO=$SECONDS
SALIDA="$(vercel "${ARGS[@]}" 2>&1)" || { echo "$SALIDA" | tail -20; echo "✗ Deploy falló"; exit 1; }
URL_DEPLOY="$(echo "$SALIDA" | grep -Eo 'https://[a-z0-9.-]+\.vercel\.app' | head -1)"
echo "✓ Deploy $([[ $PROD -eq 1 ]] && echo production || echo preview) en $((SECONDS - INICIO)) s: $URL_DEPLOY"

# ---------- 6. Verificación ----------
URL_BASE="$([[ $PROD -eq 1 ]] && echo "$URL_PRODUCCION" || echo "$URL_DEPLOY")"
echo "  ${URL_BASE}            → HTTP $(curl -s -o /dev/null -w '%{http_code}' "$URL_BASE")"
echo "  ${URL_BASE}/api/health → HTTP $(curl -s -o /dev/null -w '%{http_code}' "$URL_BASE/api/health")"
