# Agente Text-to-SQL CitiBike — LangChain 1.x

Agente conversacional que responde preguntas sobre los datos públicos de CitiBike NYC
consultando BigQuery, con un subagente de gráficos y memoria persistente (PostgreSQL).

```
Backend/    API FastAPI con el agente (orquestador + subagente de gráficos)
Frontend/   interfaz de prueba en Streamlit que consume la API
```

```
Backend/
├── model_config/model.yaml       LLMs (gpt-4.1) y límites de memoria
├── prompt/system_prompt.yaml     persona, reglas y esquema de citibike_trips (orquestador)
├── prompt/graficos_prompt.yaml   prompt del subagente de gráficos
├── chat_history/                 checkpointer (estado) + log plano (auditoría)
├── tools/                        consultar_bigquery, generar_graficos
├── subagentes/graficos/          subagente de gráficos: decide (LLM) y dibuja (matplotlib)
├── estado.py                     estado compartido entre tools (ultima_consulta, graficos_turno)
├── BigQuery/conexion.py          engine SQLAlchemy → bigquery-public-data.new_york_citibike
├── credentials/                  clave JSON de la Service Account (en .gitignore)
├── migraciones_SQL/              tabla chat_log
├── RAG/ + vector_store.py        ingesta a Qdrant (hoy sin uso: el agente no tiene tool de retrieval)
├── graficos_generados/           PNG generados (en .gitignore)
├── agent.py                      orquestador
└── app.py                        API FastAPI

Frontend/
└── app.py                        chat de prueba: respuesta, gráficos y tools usadas
```

## Puesta en marcha

Un solo entorno virtual en la raíz sirve para los dos:

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r Backend/requirements.txt -r Frontend/requirements.txt
```

### Backend

```bash
cd Backend
cp .env.example .env              # completar credenciales
```

1. Copia la clave JSON de la Service Account a `Backend/credentials/` y apunta
   `GOOGLE_APPLICATION_CREDENTIALS` a ella (ruta relativa a `Backend/`). La SA necesita
   `roles/bigquery.jobUser` en su propio proyecto (ahí se facturan las consultas) y la
   BigQuery API habilitada.
2. `migraciones_SQL/` se aplica sola al arrancar (ver su README).
3. Levanta la API: `uvicorn app:app --reload --port 8000`

```bash
curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"thread_id": "usuario-1", "mensaje": "¿Cuáles fueron las 5 estaciones con más viajes iniciados en 2016?"}'
```

`thread_id` es la identidad de la conversación: usa un ID estable por persona
(teléfono, ID de contacto) para que el agente la recuerde entre sesiones.

### Frontend

Con el Backend levantado, en otra terminal:

```bash
cd Frontend
cp .env.example .env              # BACKEND_URL (por defecto http://localhost:8000)
streamlit run app.py
```

La barra lateral muestra si el Backend está en línea, el `thread_id` de la conversación,
un botón para empezar una nueva y preguntas de ejemplo.

## Memoria

- **Retención**: descarta mensajes de más de `retention_days` días (los guarda `chat_log`).
- **Resumen**: al superar `token_limit` tokens, resume y conserva los últimos `keep_messages`.
- **Retoma**: si el usuario vuelve tras `reengagement_hours`, el agente lo saluda de nuevo.

## Seguridad de la tool `consultar_bigquery`

El SQL lo escribe el LLM, así que se valida antes de ejecutarlo:

1. **sqlglot**: una sola sentencia, solo `SELECT`/`WITH`, solo tablas permitidas.
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
