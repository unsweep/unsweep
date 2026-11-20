#!/usr/bin/env bash
export PATH=$HOME/.foundry/bin:$PATH
set -a; . /opt/aire/product.env 2>/dev/null; set +a; unset PAYER_PK OPS_PK
CFG=0x021d3F733dFf4eC20865AEb759345759158Fe6Ed; IMPL=0xee0adcf761C1bd0887080a6EC3df9C63F77877E5
mask(){ sed -e "s/${ETHERSCAN_API_KEY:-NOKEY}/***/g"; }
A1=$(cast abi-encode 'c(address,uint16,uint256)' 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B 1500 50000000000)
A2=$(cast abi-encode 'c(address)' $CFG)
echo == Config
forge verify-contract $CFG src/UnsweepConfig.sol:UnsweepConfig --chain 84532 --verifier etherscan --verifier-url "https://api.etherscan.io/v2/api?chainid=84532" --etherscan-api-key "$ETHERSCAN_API_KEY" --constructor-args $A1 --watch 2>&1 | mask | grep -vE 'warning\[|╭▸|│|╰ help|^\s*$' | tail -8
echo == Delegate
forge verify-contract $IMPL src/UnsweepDelegate.sol:UnsweepDelegate --chain 84532 --verifier etherscan --verifier-url "https://api.etherscan.io/v2/api?chainid=84532" --etherscan-api-key "$ETHERSCAN_API_KEY" --constructor-args $A2 --watch 2>&1 | mask | grep -vE 'warning\[|╭▸|│|╰ help|^\s*$' | tail -8
sleep 10
for a in $CFG $IMPL; do echo -n "$a name="; curl -s "https://api.etherscan.io/v2/api?chainid=84532&module=contract&action=getsourcecode&address=$a&apikey=$ETHERSCAN_API_KEY" | python3 -c 'import sys,json;r=json.load(sys.stdin)["result"];r=r[0] if isinstance(r,list) else {};print(r.get("ContractName") or "NO_VERIFICADO", r.get("CompilerVersion",""))'; done
