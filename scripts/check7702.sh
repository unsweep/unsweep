#!/usr/bin/env bash
# Comprueba soporte EIP-7702 con estimateGas de tx tipo 4 (no envia nada). Clave efimera sin fondos.
export PATH=$HOME/.foundry/bin:$PATH
set -a; . /opt/aire/product.env 2>/dev/null; set +a
EPH=0x$(openssl rand -hex 32)
FROM=$(cast wallet address --private-key $EPH)
echo eph=$FROM
for n in "base|$BASE_RPC_URL" "basesep|https://sepolia.base.org" "arb|https://arb1.arbitrum.io/rpc" "arbsep|https://sepolia-rollup.arbitrum.io/rpc"; do
  name=${n%%|*}; rpc=${n#*|}
  echo "== $name chainId=$(cast chain-id --rpc-url $rpc 2>&1)"
  AUTH=$(cast wallet sign-auth 0x000000000000000000000000000000000000dEaD --private-key $EPH --rpc-url $rpc 2>&1)
  echo "auth_prefix=${AUTH:0:6} auth_len=${#AUTH}"
  echo -n 'estimate_type4: '
  cast estimate --from $FROM --auth $AUTH --rpc-url $rpc $FROM 0x 2>&1 | sed -E 's#https?://[^ ]*#<rpc>#g' | grep -v -e '^Warning' -e '^$' | head -4
  echo -n "estimate_type2_control: "; cast estimate --from $FROM --rpc-url $rpc $FROM 0x 2>&1 | sed -E "s#https?://[^ ]*#<rpc>#g" | head -2
  echo "code_eph=$(cast code $FROM --rpc-url $rpc 2>&1)"
done
