# #1011/#1012 helpers de fork Arbitrum One (42161). Solo anvil LOCAL via proxy RPC de solo lectura
# (scripts/rpc_proxy.py, RPC_ENV_KEY=ARB_RPC_URL_2). Nunca se envia nada a mainnet.
# Preparacion de saldo SIN consultas historicas (sin eth_getLogs): anvil_setStorageAt sobre el slot
# de balances del USDC nativo; plan B: impersonar una direccion con saldo leida con balanceOf.
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

from eth_abi import encode
from web3 import Web3

PROXY = os.environ.get('ARB_FORK_PROXY', 'http://127.0.0.1:8557')
FORK_BLOCK = int(os.environ.get('ARB_FORK_BLOCK', '526343476'))
PORT = int(os.environ.get('ARB_FORK_PORT', '8558'))
COLD = '0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B'
USDC = '0xaf88d065e77c8cC2239327C5EDb3A432268e5831'
SEQ_FEED = '0xFdB631F5EE196F0ed6FAa767959853A9F217697D'
# plan B (solo si ningun slot de storage funciona): holders indicados explicitamente en
# ARB_FALLBACK_HOLDERS (coma). Sin valor por defecto: no se asume ninguna direccion no verificada.
FALLBACK_HOLDERS = [a.strip() for a in os.environ.get('ARB_FALLBACK_HOLDERS', '').split(',') if a.strip()]
MAX_SLOT = 20
GAS_OUT = Path(os.environ.get('ARB_GAS_OUT', '/tmp/arb_fork_gas.json'))
ERC20 = [
    {'name': 'balanceOf', 'type': 'function', 'stateMutability': 'view', 'inputs': [{'name': 'a', 'type': 'address'}], 'outputs': [{'name': '', 'type': 'uint256'}]},
    {'name': 'transfer', 'type': 'function', 'stateMutability': 'nonpayable', 'inputs': [{'name': 't', 'type': 'address'}, {'name': 'v', 'type': 'uint256'}], 'outputs': [{'name': '', 'type': 'bool'}]},
]


def proxy_ok():
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'eth_chainId', 'params': []}).encode()
    try:
        req = urllib.request.Request(PROXY, data=body, headers={'Content-Type': 'application/json'})
        return json.loads(urllib.request.urlopen(req, timeout=5).read())['result'] == '0xa4b1'
    except Exception:
        return False


def start_anvil():
    exe = os.path.expanduser('~/.foundry/bin/anvil')
    p = subprocess.Popen([exe, '--hardfork', 'prague', '--chain-id', '42161', '--port', str(PORT),
                          '--fork-url', PROXY, '--fork-block-number', str(FORK_BLOCK), '--silent'])
    w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:%d' % PORT, request_kwargs={'timeout': 120}))
    for _ in range(150):
        if w3.is_connected():
            break
        time.sleep(0.2)
    assert w3.eth.chain_id == 42161
    return p, w3


def rec_gas(key, gas):
    d = json.loads(GAS_OUT.read_text()) if GAS_OUT.exists() else {}
    d[key] = int(gas)
    GAS_OUT.write_text(json.dumps(d, indent=1, sort_keys=True))


def _slot_key(who, slot):
    return '0x' + Web3.keccak(encode(['address', 'uint256'], [Web3.to_checksum_address(who), slot])).hex().removeprefix('0x')


def _word(v):
    return '0x' + int(v).to_bytes(32, 'big').hex()


def _set_storage(w3, key, val):
    r = w3.provider.make_request('anvil_setStorageAt', [USDC, key, val])
    assert 'error' not in r, 'anvil_setStorageAt fallo: %s' % r.get('error')


def set_usdc_balance(w3, who, amount):
    """Fija balanceOf(who)==amount en el fork. Devuelve ('storage', slot) o ('impersonate', holder)."""
    usdc = w3.eth.contract(address=USDC, abi=ERC20)
    who = Web3.to_checksum_address(who)
    for slot in range(MAX_SLOT + 1):
        key = _slot_key(who, slot)
        orig = w3.eth.get_storage_at(USDC, key)
        _set_storage(w3, key, _word(amount))
        if usdc.functions.balanceOf(who).call() == amount:
            return 'storage', slot
        _set_storage(w3, key, _word(int.from_bytes(bytes(orig), 'big')))  # restaurar
    # plan B: impersonar una direccion con saldo leida con balanceOf en el bloque del fork
    for h in FALLBACK_HOLDERS:
        h = Web3.to_checksum_address(h)
        if usdc.functions.balanceOf(h).call(block_identifier=FORK_BLOCK) >= amount:
            w3.provider.make_request('anvil_setBalance', [h, hex(10**18)])
            w3.provider.make_request('anvil_impersonateAccount', [h])
            try:
                tx = w3.eth.send_transaction({'from': h, 'to': USDC, 'data': usdc.encode_abi('transfer', [who, amount])})
                assert w3.eth.wait_for_transaction_receipt(tx).status == 1
            finally:
                w3.provider.make_request('anvil_stopImpersonatingAccount', [h])
            assert usdc.functions.balanceOf(who).call() >= amount
            return 'impersonate', h
    raise AssertionError('no se pudo fijar saldo USDC nativo (ni storage slots 0..%d ni holders de respaldo)' % MAX_SLOT)
