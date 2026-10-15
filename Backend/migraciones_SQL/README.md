# Migraciones SQL

Ejecutar en orden en el editor SQL de Supabase (o con `psql`). Todas son idempotentes.

| Orden | Archivo | Crea |
|---|---|---|
| 1 | `001_chat_log.sql` | Log plano de la conversación (una fila por mensaje) + RLS |

Las tablas del checkpointer (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`,
`checkpoint_migrations`) **no** van aquí: las crea y migra `PostgresSaver.setup()` al
arrancar la app (`chat_history/postgres_store.py`), que además les activa RLS.

`001_chat_log.sql` también se ejecuta solo al arrancar (`chat_history.init_chat_history()`),
y el arranque falla si alguna de las cinco tablas de memoria falta o no tiene RLS.
Correrlo a mano sigue siendo válido: es idempotente.
