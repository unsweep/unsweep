#!/usr/bin/env bash
# E2E local: sweeper bot real vs rescate EIP-7702 patrocinado. SOLO anvil.
set -u
export PATH=$HOME/.foundry/bin:$PATH
cd "$(dirname "$0")/.."
RPC=http://127.0.0.1:18545
LOG=/tmp/unsweep_sweeper.log; : > $LOG
export SPONSOR_PK=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
ATT_PK=0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a
ATT=$(cast wallet address --private-key $ATT_PK)
export VICTIM_PK=0x$(printf '%064x' 0xA11CE)
VICTIM=$(cast wallet address --private-key $VICTIM_PK)
export SAFE=0x0000000000000000000000000000000000005AFE
FEE=0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B
anvil --hardfork prague --port 18545 --block-time 1 --silent & ANVIL=$!
trap 'kill $ANVIL $SW 2>/dev/null' EXIT
sleep 2
OUT=$(forge script script/LocalE2E.s.sol:LocalE2E --sig 'setupLocal()' --rpc-url $RPC --broadcast --slow 2>&1)
export IMPL=$(echo "$OUT" | awk '/IMPL/{print $2}' | head -1)
export USDC=$(echo "$OUT" | awk '/USDC/{print $2}' | head -1)
echo "victim=$VICTIM impl=$IMPL usdc=$USDC"
bash scripts/sweeper_bot.sh $RPC $VICTIM_PK $ATT $LOG & SW=$!
sleep 1
echo '== intento clasico: enviar 0.01 ETH de gas a la victima'
ATT0=$(cast balance $ATT --rpc-url $RPC)
cast send $VICTIM --value 0.01ether --private-key $SPONSOR_PK --rpc-url $RPC >/dev/null
sleep 4
echo "victim_eth=$(cast balance $VICTIM --rpc-url $RPC) attacker_delta=$(( $(cast balance $ATT --rpc-url $RPC) - ATT0 ))"
echo "victim_usdc=$(cast call $USDC 'balanceOf(address)(uint256)' $VICTIM --rpc-url $RPC)"
echo -n 'victima intenta mover tokens: '
cast send $USDC 'transfer(address,uint256)' $SAFE 1 --private-key $VICTIM_PK --rpc-url $RPC >/dev/null 2>&1 && echo OK_INESPERADO || echo FALLA_sin_gas
echo '== rescate EIP-7702 patrocinado (1 tx tipo 4)'
forge script script/LocalE2E.s.sol:LocalE2E --sig 'rescueLocal()' --rpc-url $RPC --broadcast --slow 2>&1 | grep -E 'ONCHAIN EXECUTION COMPLETE|Hash|Error|error' | head -5
sleep 2
echo "safe_usdc=$(cast call $USDC 'balanceOf(address)(uint256)' $SAFE --rpc-url $RPC)"
echo "fee_usdc=$(cast call $USDC 'balanceOf(address)(uint256)' $FEE --rpc-url $RPC)"
echo "victim_usdc=$(cast call $USDC 'balanceOf(address)(uint256)' $VICTIM --rpc-url $RPC)"
echo "victim_code=$(cast code $VICTIM --rpc-url $RPC)"
echo '== log sweeper'; cat $LOG
