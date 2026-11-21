#!/usr/bin/env bash
# Coste real del PASO 2 en solo lectura (sin firmar). Lee las URL RPC de product.env y no las imprime.
set -euo pipefail
BURL=$(grep -E '^BASE_RPC_URL=' /opt/aire/product.env | cut -d= -f2- | tr -d '"')
AURL=$(echo "$BURL" | sed 's#base-mainnet#arb-mainnet#')
OPS=0xF48c54ab4D91C2328111082331ABb4eBA8c2c031; F=0x4e59b44847b379578588920cA78FbF26c0B4956C
FEED=0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70
echo "feed_desc=$(cast call $FEED 'description()(string)' --rpc-url $BURL) feed_dec=$(cast call $FEED 'decimals()(uint8)' --rpc-url $BURL)"
echo "ethusd_raw=$(cast call $FEED 'latestRoundData()(uint80,int256,uint256,uint256,uint80)' --rpc-url $BURL | sed -n 2p)"
for CID in 8453 42161; do
  U=$BURL; [ $CID = 42161 ] && U=$AURL
  echo "== chain $CID real_gasPrice_wei=$(cast gas-price --rpc-url $U) real_basefee_wei=$(cast base-fee --rpc-url $U)"
  for i in 0 1; do
    D=$(python3 -c "import json;print(json.load(open('broadcast/DeployMainnetCreate2.s.sol/$CID/run-latest.json'))['transactions'][$i]['transaction']['input'])")
    echo "tx$i bytes=$(( (${#D}-2)/2 )) estimateGas_real=$(cast estimate --from $OPS $F $D --rpc-url $U)"
    if [ $CID = 8453 ]; then
      echo "tx$i base_l1Fee_wei=$(cast call 0x420000000000000000000000000000000000000F 'getL1Fee(bytes)(uint256)' $D --rpc-url $U) base_l1FeeUpperBound_wei=$(cast call 0x420000000000000000000000000000000000000F 'getL1FeeUpperBound(uint256)(uint256)' $(( (${#D}-2)/2 + 68 )) --rpc-url $U)"
    fi
  done
done
