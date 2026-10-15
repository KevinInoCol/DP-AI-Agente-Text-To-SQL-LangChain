CREATE TABLE IF NOT EXISTS chat_log (
    id           BIGSERIAL PRIMARY KEY,
    thread_id    TEXT        NOT NULL,
    rol          TEXT        NOT NULL CHECK (rol IN ('user', 'assistant')),
    contenido    TEXT        NOT NULL,
    tools_usadas TEXT[],
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chat_log_thread_id_creado_en_idx
    ON chat_log (thread_id, creado_en);

ALTER TABLE chat_log ENABLE ROW LEVEL SECURITY;
