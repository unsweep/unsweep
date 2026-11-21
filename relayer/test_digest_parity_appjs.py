"""Paridad del digest Rescue con UN mismo vector en las tres implementaciones REALES:
Solidity (UnsweepDelegate.rescueDigest en anvil) == Python (eip712.py) == JS (unsweepTyped de web/assets/app.js).
"""
import json, os, re, subprocess, time
import pytest
from eth_abi import encode
from eth_account import Account
from web3 import Web3

import eip712 as X
from test_typehash_parity import ROOT, ETHERS, SPONSOR, VECTOR, SAFE, art

PORT = 8549
APP_JS = ROOT / 'web' / 'assets' / 'app.js'
OWNER = '0x0000000000000000000000000000000000000Ab1'

JS = r"""
globalThis.window = globalThis;
require(process.argv[1]);
const E = globalThis.ethers;
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const m = src.match(/\/\/ @@typed-begin[^\n]*\n([\s\S]*?)\/\/ @@typed-end/);
if (!m) { console.error('marcadores @@typed no encontrados en app.js'); process.exit(2); }
const unsweepTyped = new Function(m[1] + '\nreturn unsweepTyped;')();
const v = JSON.parse(process.argv[3]);
const r = { safe: v.safe, calls: v.calls, tokens: v.tokens, nfts: v.nfts, maxFeeBps: v.maxFeeBps,
  minFees: v.minFees, nonce: v.nonce, deadline: v.deadline };
const { domain, types, msg } = unsweepTyped(E, r, v.chainId, v.vc);
const enc = E.TypedDataEncoder.from(types);
console.log(JSON.stringify({ typehash: E.keccak256(E.toUtf8Bytes(enc.encodeType('Rescue'))),
  digest: E.TypedDataEncoder.hash(domain, types, msg) }));
"""


@pytest.fixture(scope='module')
def w3():
    p = subprocess.Popen([os.path.expanduser('~/.foundry/bin/anvil'), '--hardfork', 'prague', '--port', str(PORT), '--silent'])
    w = Web3(Web3.HTTPProvider(f'http://127.0.0.1:{PORT}'))
    for _ in range(50):
        if w.is_connected():
            break
        time.sleep(0.2)
    yield w
    p.terminate()
    p.wait(timeout=10)


def _deploy(w3, f, c, types=(), args=()):
    abi, bc = art(f, c)
    a = Account.from_key(SPONSOR)
    tx = {'chainId': w3.eth.chain_id, 'nonce': w3.eth.get_transaction_count(a.address), 'gas': 6_000_000,
          'maxFeePerGas': w3.eth.gas_price * 2 + 1, 'maxPriorityFeePerGas': 1, 'value': 0,
          'data': bc + encode(list(types), list(args)).hex()}
    rc = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(a.sign_transaction(tx).raw_transaction))
    assert rc.status == 1
    return w3.eth.contract(address=rc.contractAddress, abi=abi)


def test_app_js_has_no_nft_fee_nor_permit():
    s = APP_JS.read_text()
    assert 'maxNftFee' not in s
    assert not re.search(r'\bpermit\b', s)
    assert '@@typed-begin' in s and '@@typed-end' in s


def test_digest_parity_solidity_python_appjs(w3):
    cfg = _deploy(w3, 'UnsweepConfig.sol', 'UnsweepConfig', ['address', 'address', 'uint16', 'address[]'],
                  [OWNER, '0x0000000000000000000000000000000000000FEE', 1500, []])
    impl = _deploy(w3, 'UnsweepDelegate.sol', 'UnsweepDelegate', ['address'], [cfg.address])
    v = VECTOR
    r = X.rescue_tuple(v['safe'], v['calls'], v['tokens'], v['nfts'], v['maxFeeBps'],
                       v['minFees'], v['nonce'], v['deadline'])
    chain_id = w3.eth.chain_id
    sol_th = bytes(impl.functions.RESCUE_TYPEHASH().call())
    sol_dg = bytes(impl.functions.rescueDigest(r).call())
    py_th, py_dg = bytes(X.RESCUE_TYPEHASH), bytes(X.rescue_digest(r, chain_id, impl.address))
    jv = dict(safe=SAFE, calls=[[a, str(b), '0x' + d.hex()] for a, b, d in v['calls']], tokens=v['tokens'],
              nfts=[[a, str(i)] for a, i in v['nfts']], maxFeeBps=v['maxFeeBps'],
              minFees=[str(x) for x in v['minFees']], nonce=str(v['nonce']), deadline=str(v['deadline']),
              chainId=chain_id, vc=impl.address)
    out = subprocess.run(['node', '-e', JS, str(ETHERS), str(APP_JS), json.dumps(jv)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    js = json.loads(out.stdout.strip().splitlines()[-1])
    js_th, js_dg = bytes.fromhex(js['typehash'][2:]), bytes.fromhex(js['digest'][2:])
    assert sol_th == py_th == js_th, (sol_th.hex(), py_th.hex(), js_th.hex())
    assert sol_dg == py_dg == js_dg, (sol_dg.hex(), py_dg.hex(), js_dg.hex())
