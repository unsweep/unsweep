-- Registro de UNSWEEP SIN datos personales: no se guardan IPs, direcciones, claves ni firmas.
CREATE TABLE IF NOT EXISTS rescue_events (
  id          bigserial PRIMARY KEY,
  created_at  timestamptz NOT NULL DEFAULT now(),
  chain_id    integer     NOT NULL,
  kind        text        NOT NULL CHECK (kind IN ('scan','simulate','rescue')),
  status      text        NOT NULL,          -- ok | rejected | error
  reason      text,                          -- codigo corto (ofac_block, policy, race, revert:<Error>...)
  n_tokens    smallint    NOT NULL DEFAULT 0,
  n_nfts      smallint    NOT NULL DEFAULT 0,
  tx_hash     text                           -- publico en el explorador; solo en rescates ok
);
CREATE INDEX IF NOT EXISTS rescue_events_created ON rescue_events (created_at);
