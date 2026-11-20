#!/usr/bin/env bash
set -u
export PATH=$HOME/.foundry/bin:$PATH
cd "$(dirname "$0")/.."
set -a; . /opt/aire/product.env 2>/dev/null; set +a
unset PAYER_PK
RPC=https://sepolia.base.org
FEE=0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B
V="--verify --etherscan-api-key $ETHERSCAN_API_KEY --chain 84532"
OUT1=$(forge create src/UnsweepConfig.sol:UnsweepConfig --rpc-url $RPC --private-key "$OPS_PK" --broadcast $V --constructor-args $FEE 1500 50000000000 2>&1)
echo "$OUT1" | grep -E 'Deployer|Deployed to|Transaction hash|Submitted|verif|Verif|GUID|URL|Error|error' | head -15
CFG=$(echo "$OUT1" | grep -oP 'Deployed to: \K0x[0-9a-fA-F]{40}')
[ -z "$CFG" ] && { echo FALLO_CONFIG; exit 1; }
OUT2=$(forge create src/UnsweepDelegate.sol:UnsweepDelegate --rpc-url $RPC --private-key "$OPS_PK" --broadcast $V --constructor-args $CFG 2>&1)
echo "$OUT2" | grep -E 'Deployer|Deployed to|Transaction hash|Submitted|verif|Verif|GUID|URL|Error|error' | head -15
IMPL=$(echo "$OUT2" | grep -oP 'Deployed to: \K0x[0-9a-fA-F]{40}')
unset OPS_PK ETHERSCAN_API_KEY
printf 'chain=base-sepolia(84532)\nUnsweepConfig=%s\nUnsweepDelegate=%s\nfeeRecipient=%s\nfeeBps=1500\ncapUsd8=50000000000\n' "$CFG" "$IMPL" "$FEE" > deployments/base-sepolia.txt
cat deployments/base-sepolia.txt
echo cfg_code_len=$(cast code $CFG --rpc-url $RPC | wc -c) impl_code_len=$(cast code ${IMPL:-0x0} --rpc-url $RPC | wc -c)
echo ops_bal=$(cast balance 0xF48c54ab4D91C2328111082331ABb4eBA8c2c031 --rpc-url $RPC --ether)
