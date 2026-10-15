# LangChain: MCP primero

Antes de escribir o modificar código que use LangChain, LangGraph o sus integraciones
(`langchain`, `langchain-openai`, `langchain-qdrant`, `langgraph-checkpoint-postgres`...),
consulta la documentación actual con la MCP de LangChain:

- `mcp__docs-langchain__search_docs_by_lang_chain` — guías y ejemplos.
- `mcp__reference-langchain__get_symbol` — firma exacta de una clase o función.

No es opcional: la API 1.x rompió con la 0.x (`create_agent` en lugar de
`create_react_agent`/`AgentExecutor`, middleware en lugar de `RunnableWithMessageHistory`,
`.text` como propiedad) y el conocimiento previo del modelo mezcla ambas.
