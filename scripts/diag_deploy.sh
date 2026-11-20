#!/usr/bin/env bash
export PATH=$HOME/.foundry/bin:$PATH
set -a; . /opt/aire/product.env 2>/dev/null; set +a; unset PAYER_PK
RPC=https://sepolia.base.org; OPS=0xF48c54ab4D91C2328111082331ABb4eBA8c2c031
N=$(cast nonce $OPS --rpc-url $RPC); echo nonce=$N bal=$(cast balance $OPS --rpc-url $RPC --ether)
echo opspk_len=${#OPS_PK} addr_ok=$([ "$(cast wallet address --private-key "$OPS_PK" 2>/dev/null)" = "$OPS" ] && echo si || echo no)
mask(){ sed -e "s/${OPS_PK#0x}/***/g" -e "s/${ETHERSCAN_API_KEY:-NOKEY}/***/g"; }
if [ "$N" = "0" ]; then
  forge create src/UnsweepConfig.sol:UnsweepConfig --rpc-url $RPC --private-key "$OPS_PK" --broadcast --constructor-args 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B 1500 50000000000 2>&1 | mask | grep -vE 'warning\[|╭▸|│|╰ help|^\s*$' | tail -15
else echo YA_HAY_TX_nonce=$N; fi
echo nonce_after=$(cast nonce $OPS --rpc-url $RPC)
