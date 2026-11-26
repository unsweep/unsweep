-- UNSWEEP M2d: registro de escaneos mainnet. NO guarda la direccion escaneada.
CREATE TABLE IF NOT EXISTS unsweep_scans (
  id bigserial PRIMARY KEY,
  ts timestamptz NOT NULL DEFAULT now(),
  chain text NOT NULL CHECK (chain IN ('base','ethereum','optimism')),
  hallazgo_7702 boolean NOT NULL,
  n_approvals integer NOT NULL,
  ip_hash text NOT NULL,
  propio boolean NOT NULL DEFAULT false,   -- escaneos propios: excluidos de la senal
  cached boolean NOT NULL DEFAULT false,
  ua_bot boolean NOT NULL DEFAULT false,   -- firma de bot en el User-Agent: excluido de la senal
  referer_host text
);
CREATE INDEX IF NOT EXISTS unsweep_scans_ts ON unsweep_scans (ts);
