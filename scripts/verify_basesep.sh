#!/usr/bin/env bash
# Verifica UnsweepConfig + UnsweepDelegate (M4c) en sepolia.basescan.org (Etherscan v2, chainid 84532).
# Uso: scripts/verify_basesep.sh <CFG> <IMPL> [OWNER] [FEE_RECIPIENT] [FEE_BPS] [CLAIM_TARGETS_CSV]
# Constructor M4c: UnsweepConfig(address _owner, address _feeRecipient, uint16 _feeBps, address[] _claimTargets)
#                  UnsweepDelegate(UnsweepConfig _config)
set -u
cd "$(dirname "$0")/.." || exit 1
export PATH=$HOME/.foundry/bin:$PATH
set -a; . /opt/aire/product.env 2>/dev/null; set +a; unset PAYER_PK OPS_PK
CFG=${1:?CFG}; IMPL=${2:?IMPL}
OWNER=${3:-0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B}
FEE=${4:-0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B}
FEE_BPS=${5:-1500}
CLAIMS=${6:-}
SOLC=0.8.39+commit.ce47f2c8
RPC=https://sepolia.base.org
mask(){ sed -e "s/${ETHERSCAN_API_KEY:-NOKEY}/***/g"; }
A1=$(cast abi-encode 'c(address,address,uint16,address[])' $OWNER $FEE $FEE_BPS "[$CLAIMS]")
A2=$(cast abi-encode 'c(address)' $CFG)
ver(){ forge verify-contract "$1" "$2" --chain 84532 --compiler-version $SOLC --verifier etherscan --verifier-url "https://api.etherscan.io/v2/api?chainid=84532" --etherscan-api-key "$ETHERSCAN_API_KEY" --constructor-args "$3" --watch --retries 20 --delay 10 2>&1 | mask | grep -vE 'warning\[|╭▸|│|╰ help|^\s*$' | tail -8; }
echo == Config; ver $CFG src/UnsweepConfig.sol:UnsweepConfig $A1
sleep 5
echo == Delegate; ver $IMPL src/UnsweepDelegate.sol:UnsweepDelegate $A2
sleep 5
for a in $CFG $IMPL; do echo -n "$a name="; curl -s "https://api.etherscan.io/v2/api?chainid=84532&module=contract&action=getsourcecode&address=$a&apikey=$ETHERSCAN_API_KEY" | python3 -c 'import sys,json;r=json.load(sys.stdin)["result"];r=r[0] if isinstance(r,list) else {};print(r.get("ContractName") or "NO_VERIFICADO", r.get("CompilerVersion",""))'; done
echo -n "owner()="; cast call $CFG 'owner()(address)' --rpc-url $RPC
