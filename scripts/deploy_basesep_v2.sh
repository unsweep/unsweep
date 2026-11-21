#!/usr/bin/env bash
# Redespliegue Base Sepolia del contrato corregido + verificacion Sourcify (no requiere API key).
set -u
export PATH=$HOME/.foundry/bin:$PATH
cd "$(dirname "$0")/.."
set -a; . /opt/aire/product.env 2>/dev/null; set +a
unset PAYER_PK ETHERSCAN_API_KEY
RPC=https://sepolia.base.org
FEE=0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B
flt(){ grep -E 'Deployer|Deployed to|Transaction hash|Error|error' | head -8; }
OUT1=$(forge create src/UnsweepConfig.sol:UnsweepConfig --rpc-url $RPC --private-key "$OPS_PK" --broadcast --constructor-args $FEE 1500 50000000000 2>&1)
echo "$OUT1" | flt
CFG=$(echo "$OUT1" | grep -oP 'Deployed to: \K0x[0-9a-fA-F]{40}')
[ -z "$CFG" ] && { echo FALLO_CONFIG; exit 1; }
sleep 4
OUT2=$(forge create src/UnsweepDelegate.sol:UnsweepDelegate --rpc-url $RPC --private-key "$OPS_PK" --broadcast --constructor-args $CFG 2>&1)
echo "$OUT2" | flt
IMPL=$(echo "$OUT2" | grep -oP 'Deployed to: \K0x[0-9a-fA-F]{40}')
unset OPS_PK
[ -z "$IMPL" ] && { echo FALLO_DELEGATE; exit 1; }
printf 'chain=base-sepolia(84532)\ncommit=%s\nUnsweepConfig=%s\nUnsweepDelegate=%s\nfeeRecipient=%s\nfeeBps=1500\ncapUsd8=50000000000\n' "$(git rev-parse --short HEAD)" "$CFG" "$IMPL" "$FEE" > deployments/base-sepolia.txt
cat deployments/base-sepolia.txt
sleep 8
A1=$(cast abi-encode 'c(address,uint16,uint256)' $FEE 1500 50000000000)
A2=$(cast abi-encode 'c(address)' $CFG)
echo == verify Config
forge verify-contract $CFG src/UnsweepConfig.sol:UnsweepConfig --chain 84532 --verifier sourcify --constructor-args $A1 --watch 2>&1 | grep -vE 'warning\[|╭▸|│|╰ help|^\s*$' | tail -5
echo == verify Delegate
forge verify-contract $IMPL src/UnsweepDelegate.sol:UnsweepDelegate --chain 84532 --verifier sourcify --constructor-args $A2 --watch 2>&1 | grep -vE 'warning\[|╭▸|│|╰ help|^\s*$' | tail -5
echo cfg_code_len=$(cast code $CFG --rpc-url $RPC | wc -c) impl_code_len=$(cast code $IMPL --rpc-url $RPC | wc -c)
echo ops_bal=$(cast balance 0xF48c54ab4D91C2328111082331ABb4eBA8c2c031 --rpc-url $RPC --ether)
