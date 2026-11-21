"""Confirma EIP-7702 por JSON-RPC directo (eth_estimateGas con authorizationList). No envia nada."""
import json, sys, urllib.request
from eth_account import Account
RPC = {'base': ('https://mainnet.base.org', 8453), 'arbitrum': ('https://arb1.arbitrum.io/rpc', 42161)}
IMPL = '0x000000000000000000000000000000000000dEaD'
def rpc(url, m, p):
    req = urllib.request.Request(url, json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': m, 'params': p}).encode(), {'Content-Type': 'application/json', 'User-Agent': 'unsweep-check'})
    return json.load(urllib.request.urlopen(req, timeout=20))
ok = True
for name, (url, cid) in RPC.items():
    a = Account.create(); s = Account.create()
    au = Account.sign_authorization({'chainId': cid, 'address': IMPL, 'nonce': 0}, a.key)
    item = {'chainId': hex(cid), 'address': IMPL, 'nonce': '0x0', 'yParity': hex(au.y_parity), 'r': hex(au.r), 's': hex(au.s)}
    base_tx = {'from': s.address, 'to': a.address, 'data': '0x'}
    real_cid = rpc(url, 'eth_chainId', [])
    g0 = rpc(url, 'eth_estimateGas', [base_tx])
    g1 = rpc(url, 'eth_estimateGas', [{**base_tx, 'type': '0x4', 'authorizationList': [item]}])
    r0, r1 = g0.get('result'), g1.get('result')
    d = int(r1, 16) - int(r0, 16) if r0 and r1 else None
    good = d is not None and d >= 12500
    ok &= good
    print(json.dumps({'chain': name, 'eth_chainId': real_cid.get('result'), 'gas_sin_auth': r0, 'gas_con_auth': r1, 'delta': d, 'err': g1.get('error'), '7702_activo': good}))
sys.exit(0 if ok else 1)
