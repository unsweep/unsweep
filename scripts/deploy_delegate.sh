#!/usr/bin/env bash
export PATH=$HOME/.foundry/bin:$PATH
set -a; . /opt/aire/product.env 2>/dev/null; set +a; unset PAYER_PK
RPC=https://sepolia.base.org; OPS=0xF48c54ab4D91C2328111082331ABb4eBA8c2c031; CFG=0x021d3F733dFf4eC20865AEb759345759158Fe6Ed
mask(){ sed -e "s/${OPS_PK#0x}/***/g" -e "s/${ETHERSCAN_API_KEY:-NOKEY}/***/g"; }
echo cfg_feeRecipient=$(cast call $CFG 'feeRecipient()(address)' --rpc-url $RPC) feeBps=$(cast call $CFG 'feeBps()(uint16)' --rpc-url $RPC) capUsd8=$(cast call $CFG 'capUsd8()(uint256)' --rpc-url $RPC) owner=$(cast call $CFG 'owner()(address)' --rpc-url $RPC)
N=$(cast nonce $OPS --rpc-url $RPC); echo nonce=$N
if [ "$N" = "1" ]; then
  OUT=$(forge create src/UnsweepDelegate.sol:UnsweepDelegate --rpc-url $RPC --private-key "$OPS_PK" --broadcast --constructor-args $CFG 2>&1 | mask)
  echo "$OUT" | grep -E 'Deployer|Deployed to|Transaction hash|Error|error' | tail -6
  IMPL=$(echo "$OUT" | grep -oP 'Deployed to: \K0x[0-9a-fA-F]{40}')
else echo NO_DESPLIEGO_nonce=$N; fi
unset OPS_PK ETHERSCAN_API_KEY
printf 'chain=base-sepolia(84532)\nUnsweepConfig=%s\nconfig_tx=0x33d497ed290cb2d4af800b103cff60ead5f3445c40d52424b8602d4f6341c09e\nUnsweepDelegate=%s\nfeeRecipient=0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B\nfeeBps=1500\ncapUsd8=50000000000\ndeployer=%s\n' "$CFG" "${IMPL:-PENDIENTE}" "$OPS" > deployments/base-sepolia.txt
cat deployments/base-sepolia.txt
[ -n "${IMPL:-}" ] && echo impl_cfg=$(cast call $IMPL 'config()(address)' --rpc-url $RPC)
echo nonce_after=$(cast nonce $OPS --rpc-url $RPC) bal=$(cast balance $OPS --rpc-url $RPC --ether)
