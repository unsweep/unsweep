#!/usr/bin/env python3
"""E2E M4c en Base Sepolia (84532): rescate EIP-7702 patrocinado de 1 ERC-20 + 1 NFT en la misma cesta.
Usa relayer.send_rescue (eth_call obligatoria antes de enviar). Victima y wallet segura efimeras.
Nunca imprime claves. Uso: .venv/bin/python scripts/e2e_basesep_m4c.py"""
import json, os, re, secrets, sys, time, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'relayer'))
from eth_account import Account
from web3 import Web3
import relayer as R
import eip712 as X

RPC = 'https://sepolia.base.org'
D = dict(l.strip().split('=', 1) for l in open(ROOT / 'deployments/base-sepolia.txt') if '=' in l)
CFG, IMPL = D['UnsweepConfig'], D['UnsweepDelegate']
USDC, NFT = D['TEST_USDC_MOCK'], D['TEST_NFT_MOCK']
OPS_EXPECTED = '0xF48c54ab4D91C2328111082331ABb4eBA8c2c031'
MAX_FEE_BPS = 1500
AMOUNT = 400 * 10**6


def ops_key():
    for l in open('/opt/aire/product.env'):
        m = re.match(r"\s*(?:export\s+)?OPS_PK\s*=\s*[\"']?([^\"'\s#]+)", l)
        if m:
            return m.group(1)
    raise SystemExit('OPS_PK no encontrada')


def abi(f, c):
    return json.load(open(ROOT / 'out' / f / f'{c}.json'))['abi']


w3 = Web3(Web3.HTTPProvider(RPC))
assert w3.eth.chain_id == 84532, 'no es Base Sepolia'
OPS = Account.from_key(ops_key())
assert OPS.address == OPS_EXPECTED, 'OPS no coincide'
ERC20 = [{'name': n, 'type': 'function', 'stateMutability': s, 'inputs': i, 'outputs': o} for n, s, i, o in [
    ('balanceOf', 'view', [{'type': 'address', 'name': 'a'}], [{'type': 'uint256', 'name': ''}]),
    ('mint', 'nonpayable', [{'type': 'address', 'name': 't'}, {'type': 'uint256', 'name': 'a'}], [])]]
ERC721 = [{'name': n, 'type': 'function', 'stateMutability': s, 'inputs': i, 'outputs': o} for n, s, i, o in [
    ('ownerOf', 'view', [{'type': 'uint256', 'name': 'id'}], [{'type': 'address', 'name': ''}]),
    ('mint', 'nonpayable', [{'type': 'address', 'name': 't'}, {'type': 'uint256', 'name': 'id'}], [])]]
usdc = w3.eth.contract(address=USDC, abi=ERC20)
nft = w3.eth.contract(address=NFT, abi=ERC721)
cfg = w3.eth.contract(address=CFG, abi=abi('UnsweepConfig.sol', 'UnsweepConfig'))
del_abi = abi('UnsweepDelegate.sol', 'UnsweepDelegate')


def ops_send(fn):
    tx = fn.build_transaction({'from': OPS.address, 'chainId': 84532,
                               'nonce': w3.eth.get_transaction_count(OPS.address, 'pending'),
                               'maxFeePerGas': w3.eth.gas_price * 2 + 1, 'maxPriorityFeePerGas': 1})
    rc = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(OPS.sign_transaction(tx).raw_transaction), timeout=120)
    assert rc.status == 1, 'mint fallo'
    return rc.transactionHash.hex()


victim, safe = Account.create(), Account.create()
fee_to = cfg.functions.feeRecipient().call()
cfg_bps = cfg.functions.feeBps().call()
nft_id = secrets.randbits(64)
ev = {'chain': 84532, 'config': CFG, 'delegate': IMPL, 'victim': victim.address, 'safe': safe.address,
      'fee_recipient': fee_to, 'config_feeBps': cfg_bps, 'maxFeeBps_signed': MAX_FEE_BPS, 'nft': NFT, 'nft_id': str(nft_id),
      'token': USDC, 'amount': AMOUNT}
ev['mint_erc20_tx'] = ops_send(usdc.functions.mint(victim.address, AMOUNT))
ev['mint_nft_tx'] = ops_send(nft.functions.mint(victim.address, nft_id))
assert nft.functions.ownerOf(nft_id).call() == victim.address

safe0_tok = usdc.functions.balanceOf(safe.address).call(); safe0_eth = w3.eth.get_balance(safe.address)
fee0 = usdc.functions.balanceOf(fee_to).call()
bal = usdc.functions.balanceOf(victim.address).call()

nonce, deadline = secrets.randbits(64), int(time.time()) + 1800
r = X.rescue_tuple(safe.address, [], [USDC], [(NFT, nft_id)], MAX_FEE_BPS, [], nonce, deadline)
digest = X.rescue_digest(r, 84532, victim.address)
sig = Account._sign_hash(digest, victim.key) if hasattr(Account, '_sign_hash') else Account.unsafe_sign_hash(digest, victim.key)
dc = w3.eth.contract(address=victim.address, abi=del_abi)
calldata = dc.encode_abi('rescue', args=[r, sig.v, sig.r.to_bytes(32, 'big'), sig.s.to_bytes(32, 'big')])
auth = R.sign_auth(victim.key, 84532, IMPL, w3.eth.get_transaction_count(victim.address))
q = R.Quote(rescued_usd=400, fee_usd=60, gas_cost_usd=0.05)
rc = R.send_rescue(w3, OPS.key, victim.address, auth, calldata, q, gas=1_500_000)
ev['rescue_tx'] = rc.transactionHash.hex() if rc.transactionHash.hex().startswith('0x') else '0x' + rc.transactionHash.hex()
ev['rescue_status'] = rc.status; ev['rescue_block'] = rc.blockNumber; ev['rescue_gas'] = rc.gasUsed
ev['simulacion_eth_call'] = 'OK (relayer.send_rescue -> policy.simulate, previa al envio)'

fee_got = usdc.functions.balanceOf(fee_to).call() - fee0
safe_got = usdc.functions.balanceOf(safe.address).call() - safe0_tok
eff = min(cfg_bps, MAX_FEE_BPS)
ev.update({'fee_paid': fee_got, 'safe_received': safe_got, 'fee_bps_effective': round(fee_got * 10_000 / bal, 4) if bal else None,
           'owner_of_nft': nft.functions.ownerOf(nft_id).call(), 'safe_eth_before': safe0_eth, 'safe_eth_after': w3.eth.get_balance(safe.address)})
checks = {
    'rescue_status_1': rc.status == 1,
    'fee_le_signed': fee_got * 10_000 <= bal * MAX_FEE_BPS + 10_000,
    'safe_no_pierde': usdc.functions.balanceOf(safe.address).call() >= safe0_tok and ev['safe_eth_after'] >= safe0_eth and safe_got > 0,
    'nft_en_safe': ev['owner_of_nft'] == safe.address,
    'conservacion': fee_got + safe_got == bal,
}
ev['checks'] = checks
out = ROOT / 'evidence/m4d'; out.mkdir(parents=True, exist_ok=True)
(out / 'e2e.json').write_text(json.dumps(ev, indent=2, default=str))
print(json.dumps(ev, indent=2, default=str))
sys.exit(0 if all(checks.values()) else 2)
