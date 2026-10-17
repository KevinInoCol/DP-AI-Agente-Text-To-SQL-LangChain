# Agente Text-to-SQL CitiBike (LangChain 1.x)

Dos aplicaciones:
- `Backend/`: el agente (FastAPI). Estructura según la skill `agent-project-structure`
  (ver `.claude/skills/`). Sin debounce: cada mensaje recibido se procesa como un turno.
- `Frontend/`: interfaz de prueba en Streamlit. Solo habla con la API HTTP del Backend
  (`POST /chat`, `GET /health`); nunca importa código de `Backend/`.
- `Frontend-v2/`: la misma interfaz en React + Vite. Mismo contrato: solo la API HTTP,
  vía el proxy `/api` de Vite (`BACKEND_URL` en `Frontend-v2/.env`), sin CORS en el Backend.

Las rutas de la tabla de abajo son relativas a `Backend/`. Los comandos del Backend se
ejecutan desde `Backend/` (los módulos se importan por nombre: `agent`, `tools`, ...).

@.claude/rules/langchain-mcp-first.md

## Dónde va cada cambio

| Cambio | Archivo |
|---|---|
| Modelo, temperatura, límites de memoria | `model_config/model.yaml` |
| Persona / reglas del agente | `prompt/system_prompt.yaml` (skill `agent-prompt-yaml-format`) |
| Nueva tool | `tools/<nombre>.py` + `tools/__init__.py` + `agent.build_agent()` + prompt |
| Conexión a BigQuery (proyecto, dataset, tope de bytes) | `BigQuery/conexion.py` |
| Validación / ejecución del SQL del agente | `tools/bigquery.py` |
| Qué gráficos elige el subagente | `prompt/graficos_prompt.yaml` + `subagentes/graficos/especificacion.py` |
| Cómo se dibujan los gráficos | `subagentes/graficos/renderizado.py` |
| Estado compartido entre tools | `estado.py` |
| Esquema de la base (Postgres) | `migraciones_SQL/` |
| Canal de entrada (API) | `app.py` |
| Interfaz de prueba | `../Frontend/app.py` (Streamlit), `../Frontend-v2/src/` (React) |

`agent.py` solo cambia para orquestación.

## BigQuery

- Datos: `bigquery-public-data.new_york_citibike` (público, solo lectura).
- Facturación: el proyecto de la Service Account (`project_id` del JSON en `credentials/`).
- El esquema de `citibike_trips` está escrito en `prompt/system_prompt.yaml`
  (`<Esquema_De_Datos>`). Si agregas una tabla, agrégala también a
  `TABLAS_PERMITIDAS` en `tools/bigquery.py`.
- `tools/bigquery.py` rechaza todo lo que no sea una única consulta de lectura sobre
  las tablas del dataset (sqlglot). No relajes esa validación.
