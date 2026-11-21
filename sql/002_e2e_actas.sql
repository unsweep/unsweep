-- Actas de E2E en TESTNET (direcciones de prueba públicas, sin claves ni firmas). Separada de rescue_events.
CREATE TABLE IF NOT EXISTS e2e_actas (
  id bigserial PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now(),
  mision text NOT NULL,
  chain_id integer NOT NULL,
  resultado text NOT NULL,
  error_exacto text,
  rescue_tx text,
  prep_txs jsonb NOT NULL,
  wallets jsonb NOT NULL,
  saldos_antes jsonb NOT NULL,
  saldos_despues jsonb NOT NULL,
  notas text
);
