-- ORDEN #166 (respuesta A): ampliar el CHECK de unsweep_scans para admitir 'optimism' (OP Mainnet, chainId 10).
-- Idempotente y sin borrar datos: solo redefine la restriccion; las filas existentes ('base','ethereum') siguen siendo validas.
BEGIN;
ALTER TABLE unsweep_scans DROP CONSTRAINT IF EXISTS unsweep_scans_chain_check;
ALTER TABLE unsweep_scans ADD CONSTRAINT unsweep_scans_chain_check CHECK (chain IN ('base','ethereum','optimism'));
COMMIT;
