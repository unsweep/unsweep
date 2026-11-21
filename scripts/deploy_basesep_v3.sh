#!/usr/bin/env bash
# M2: redespliegue en Base Sepolia del codigo endurecido (M1.1) + activos de PRUEBA para el E2E.
# SOLO TESTNET (84532). Los Mock* se pueden acunar sin restriccion: nunca desplegarlos en mainnet.
set -u
export PATH=$HOME/.foundry/bin:$PATH
cd "$(dirname "$0")/.."
set -a; . /opt/aire/product.env 2>/dev/null; set +a
unset PAYER_PK ETHERSCAN_API_KEY
RPC=https://sepolia.base.org
CHAIN=$(cast chain-id --rpc-url $RPC)
[ "$CHAIN" = "84532" ] || { echo "ABORT chain=$CHAIN no es Base Sepolia"; unset OPS_PK; exit 1; }
FEE=0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B
NFT_FLAT_FEE=5000000
flt(){ grep -E 'Deployed to|Transaction hash|Error|error' | head -4; }
dep(){ # $1=contrato  resto=args constructor
  local c=$1; shift
  local out
  if [ $# -gt 0 ]; then out=$(forge create "$c" --rpc-url $RPC --private-key "$OPS_PK" --broadcast --constructor-args "$@" 2>&1)
  else out=$(forge create "$c" --rpc-url $RPC --private-key "$OPS_PK" --broadcast 2>&1); fi
  echo "$out" | flt >&2
  echo "$out" | grep -oP 'Deployed to: \K0x[0-9a-fA-F]{40}'
}
[ -f deployments/base-sepolia.txt ] && grep -q 'commit=e503a71' deployments/base-sepolia.txt && mv deployments/base-sepolia.txt deployments/base-sepolia.e503a71.DEPRECATED.txt
TUSD=$(dep test/Mocks.sol:MockToken 6) ; [ -z "$TUSD" ] && { echo FALLO_TUSD; unset OPS_PK; exit 1; }; sleep 3
GOV=$(dep test/Mocks.sol:MockToken 18) ; [ -z "$GOV" ] && { echo FALLO_GOV; unset OPS_PK; exit 1; }; sleep 3
AIRDROP=$(dep test/Mocks.sol:MockAirdrop $GOV) ; [ -z "$AIRDROP" ] && { echo FALLO_AIRDROP; unset OPS_PK; exit 1; }; sleep 3
NFT=$(dep test/Mocks.sol:MockERC721) ; [ -z "$NFT" ] && { echo FALLO_NFT; unset OPS_PK; exit 1; }; sleep 3
CFG=$(dep src/UnsweepConfig.sol:UnsweepConfig $FEE 1500 $TUSD $NFT_FLAT_FEE) ; [ -z "$CFG" ] && { echo FALLO_CONFIG; unset OPS_PK; exit 1; }; sleep 3
IMPL=$(dep src/UnsweepDelegate.sol:UnsweepDelegate $CFG) ; [ -z "$IMPL" ] && { echo FALLO_DELEGATE; unset OPS_PK; exit 1; }
unset OPS_PK
printf 'chain=base-sepolia(84532)\ncommit=%s\nUnsweepConfig=%s\nUnsweepDelegate=%s\nfeeRecipient=%s\nfeeBps=1500\nnftFeeToken=%s\nnftFlatFee=%s\nTEST_USDC_MOCK=%s\nTEST_GOV_MOCK=%s\nTEST_AIRDROP_MOCK=%s\nTEST_NFT_MOCK=%s\n' \
  "$(git rev-parse --short HEAD)" "$CFG" "$IMPL" "$FEE" "$TUSD" "$NFT_FLAT_FEE" "$TUSD" "$GOV" "$AIRDROP" "$NFT" > deployments/base-sepolia.txt
cat deployments/base-sepolia.txt
sleep 8
ver(){ forge verify-contract "$1" "$2" --chain 84532 --verifier sourcify ${3:+--constructor-args $3} --watch 2>&1 | grep -vE 'warning\[|╭▸|│|╰ help|^\s*$' | tail -2; }
echo == verify Config;   ver $CFG src/UnsweepConfig.sol:UnsweepConfig "$(cast abi-encode 'c(address,uint16,address,uint256)' $FEE 1500 $TUSD $NFT_FLAT_FEE)"
echo == verify Delegate; ver $IMPL src/UnsweepDelegate.sol:UnsweepDelegate "$(cast abi-encode 'c(address)' $CFG)"
echo == verify mocks
ver $TUSD test/Mocks.sol:MockToken "$(cast abi-encode 'c(uint8)' 6)"
ver $GOV test/Mocks.sol:MockToken "$(cast abi-encode 'c(uint8)' 18)"
ver $AIRDROP test/Mocks.sol:MockAirdrop "$(cast abi-encode 'c(address)' $GOV)"
ver $NFT test/Mocks.sol:MockERC721 ""
echo cfg_code_len=$(cast code $CFG --rpc-url $RPC | wc -c) impl_code_len=$(cast code $IMPL --rpc-url $RPC | wc -c)
echo ops_bal=$(cast balance 0xF48c54ab4D91C2328111082331ABb4eBA8c2c031 --rpc-url $RPC --ether)
