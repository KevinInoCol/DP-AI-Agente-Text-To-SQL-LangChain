# Agente Text-to-SQL CitiBike — LangChain 1.x

Agente conversacional que responde preguntas sobre los datos públicos de CitiBike NYC
consultando BigQuery, con RAG (Qdrant) y memoria persistente (PostgreSQL).

```
model_config/model.yaml       LLM (gpt-4.1) y límites de memoria
prompt/system_prompt.yaml     persona, reglas y esquema de citibike_trips (orquestador)
prompt/graficos_prompt.yaml   prompt del subagente de gráficos
chat_history/                 checkpointer (estado) + log plano (auditoría)
RAG/rag.py                    ingesta → Qdrant
tools/                        consultar_bigquery, generar_graficos, buscar_base_conocimiento
subagentes/graficos/          subagente de gráficos: decide (LLM) y dibuja (matplotlib)
estado.py                     estado compartido entre tools (ultima_consulta, graficos_turno)
BigQuery/conexion.py          engine SQLAlchemy → bigquery-public-data.new_york_citibike
credentials/                  clave JSON de la Service Account (en .gitignore)
vector_store.py               par (embeddings, colección): fuente única
migraciones_SQL/              tabla chat_log
agent.py                      orquestador
graficos_generados/           PNG generados (en .gitignore)
app.py                        API FastAPI
```

## Puesta en marcha

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env              # completar credenciales
```

0. Copia la clave JSON de la Service Account a `credentials/` y apunta
   `GOOGLE_APPLICATION_CREDENTIALS` a ella. La SA necesita `roles/bigquery.jobUser`
   en su propio proyecto (ahí se facturan las consultas) y la BigQuery API habilitada.

1. Ejecuta `migraciones_SQL/` en orden (ver su README).
2. Copia tus documentos (.pdf, .txt, .md) a `RAG/Base_de_Conocimiento/` y ejecuta
   `python RAG/rag.py`.
3. Levanta la API: `uvicorn app:app --reload --port 8000`

```bash
curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"thread_id": "usuario-1", "mensaje": "¿Cuáles fueron las 5 estaciones con más viajes iniciados en 2016?"}'
```

`thread_id` es la identidad de la conversación: usa un ID estable por persona
(teléfono, ID de contacto) para que el agente la recuerde entre sesiones.

## Memoria

- **Retención**: descarta mensajes de más de `retention_days` días (los guarda `chat_log`).
- **Resumen**: al superar `token_limit` tokens, resume y conserva los últimos `keep_messages`.
- **Retoma**: si el usuario vuelve tras `reengagement_hours`, el agente lo saluda de
  nuevo y reverifica datos.

## Seguridad de la tool `consultar_bigquery`

El SQL lo escribe el LLM, así que se valida antes de ejecutarlo:

1. **sqlglot**: una sola sentencia, solo `SELECT`/`WITH`, solo tablas de `new_york_citibike`.
2. **Tope de costo**: `BIGQUERY_MAX_BYTES_BILLED` (2 GB por defecto) por consulta.
3. **Máximo 50 filas** devueltas al modelo.
4. **Permisos mínimos**: la Service Account solo puede ejecutar jobs, no escribir.

## Subagente de gráficos

```
usuario → orquestador ─ consultar_bigquery ──► BigQuery
                │            └─ guarda el resultado en el estado (ultima_consulta)
                └─ generar_graficos(instrucción)
                         └─ subagente: instrucción + perfil de los datos → 1-2 especificaciones
                         └─ matplotlib dibuja los PNG con los datos exactos del estado
```

- Los números no pasan por el texto del LLM: el subagente decide *qué* graficar y el
  dibujo lo hace código determinista con el resultado real de la consulta.
- Si una especificación es inválida (columna inexistente, eje Y no numérico), ese
  gráfico se descarta y el orquestador se entera.
- `POST /chat` devuelve los gráficos en `graficos[].imagen_base64` (PNG).
