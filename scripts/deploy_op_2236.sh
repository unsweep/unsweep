#!/usr/bin/env bash
# ORDEN #2236 paso 3: despliegue + verificacion de UnsweepConfig/UnsweepDelegate en OP Mainnet (chainId 10).
# Reutiliza script/DeployMainnetCreate2.s.sol (CREATE2 idempotente, factory 0x4e59b448...956C) => mismas
# direcciones que Base/Arbitrum: Config 0x56a345661e3999F2b20f1E069aAC14097Fa0D118, Delegate 0x38bcF425bC4d13624734e09376F2fafc799fA8c8.
#
# Modos:
#   ./scripts/deploy_op_2236.sh simulate   (POR DEFECTO) fork de OP, SIN --broadcast, clave de prueba de anvil.
#   BROADCAST=YES ./scripts/deploy_op_2236.sh deploy   transmite con OPS_PK (solo tras financiacion autorizada).
#   ./scripts/deploy_op_2236.sh verify     forge verify-contract en optimistic.etherscan.io (requiere ETHERSCAN_API_KEY).
# Nunca imprime OP_RPC_URL, OPS_PK ni claves del explorador.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.foundry/bin:$PATH"
ENVF=${ENVF:-/opt/aire/product.env}
get(){ grep "^$1=" "$ENVF" | head -1 | cut -d= -f2- | tr -d '"'; }
OP_RPC_URL=${OP_RPC_URL:-$(get OP_RPC_URL)}
[ -n "$OP_RPC_URL" ] || { echo "OP_RPC_URL ausente" >&2; exit 2; }
redact(){ sed -E 's#https?://[^ ]+#<RPC_REDACTED>#g; s#0x[0-9a-fA-F]{64}#<HEX64_REDACTED>#g'; }
CID=$(cast chain-id --rpc-url "$OP_RPC_URL")
[ "$CID" = "10" ] || { echo "chainId=$CID != 10, abortado" >&2; exit 3; }
CFG=0x56a345661e3999F2b20f1E069aAC14097Fa0D118
IMPL=0x38bcF425bC4d13624734e09376F2fafc799fA8c8
OWNER=0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B
MODE=${1:-simulate}
case "$MODE" in
  simulate)
    # Clave EFIMERA aleatoria solo para simular (CREATE2 via factory: direcciones independientes del sender); no se guarda ni se transmite nada.
    OPS_PK=0x$(openssl rand -hex 32) \
      forge script script/DeployMainnetCreate2.s.sol:DeployMainnetCreate2 --fork-url "$OP_RPC_URL" -vv 2>&1 | redact
    rm -rf cache/DeployMainnetCreate2.s.sol/10
    ;;
  deploy)
    [ "${BROADCAST:-}" = "YES" ] || { echo "Falta BROADCAST=YES (proteccion)" >&2; exit 4; }
    OPS_PK=${OPS_PK:-$(get OPS_PK)}
    [ -n "$OPS_PK" ] || { echo "OPS_PK ausente" >&2; exit 5; }
    OPS_PK="$OPS_PK" forge script script/DeployMainnetCreate2.s.sol:DeployMainnetCreate2 \
      --rpc-url "$OP_RPC_URL" --broadcast -vv 2>&1 | redact
    rm -rf cache/DeployMainnetCreate2.s.sol/10
    ;;
  verify)
    KEY=${ETHERSCAN_API_KEY:-$(get ETHERSCAN_API_KEY)}
    [ -n "$KEY" ] || { echo "ETHERSCAN_API_KEY ausente: verificacion NO_DISPONIBLE" >&2; exit 6; }
    CLAIMS_ARGS=$(cast abi-encode 'c(address,address,uint16,address[])' $OWNER $OWNER 1500 '[]')
    forge verify-contract --chain optimism --etherscan-api-key "$KEY" --watch \
      --constructor-args "$CLAIMS_ARGS" $CFG src/UnsweepConfig.sol:UnsweepConfig 2>&1 | redact
    forge verify-contract --chain optimism --etherscan-api-key "$KEY" --watch \
      --constructor-args "$(cast abi-encode 'c(address)' $CFG)" $IMPL src/UnsweepDelegate.sol:UnsweepDelegate 2>&1 | redact
    ;;
  *) echo "modo desconocido: $MODE" >&2; exit 1;;
esac
for a in $CFG $IMPL; do c=$(cast code $a --rpc-url "$OP_RPC_URL"); echo "$a code_bytes=$(( (${#c}-2)/2 ))"; done
