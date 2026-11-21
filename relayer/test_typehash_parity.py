"""Paridad EIP-712 de Rescue: Solidity (UnsweepDelegate en anvil) == Python (eip712.py) == JS (ethers de la web).

Falla si el typehash o el digest no coinciden en las tres implementaciones.
"""
import json, os, re, subprocess, time, pathlib
import pytest
from eth_abi import encode
from eth_account import Account
from web3 import Web3
import eip712 as X

ROOT = pathlib.Path(__file__).resolve().parents[1]
PORT = 8547
SPONSOR = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'
ETHERS = ROOT / 'web' / 'assets' / 'ethers.min.js'

JS = r"""
globalThis.window = globalThis;
require(process.argv[1]);
const E = globalThis.ethers;
const v = JSON.parse(process.argv[2]);
const c = E.AbiCoder.defaultAbiCoder();
const types = { Rescue: [
  { name: 'safe', type: 'address' }, { name: 'callsHash', type: 'bytes32' }, { name: 'tokensHash', type: 'bytes32' },
  { name: 'nftsHash', type: 'bytes32' },
  { name: 'maxFeeBps', type: 'uint16' }, { name: 'minFeesHash', type: 'bytes32' }, { name: 'nonce', type: 'uint256' },
  { name: 'deadline', type: 'uint256' }] };
const msg = { safe: v.safe,
  callsHash: E.keccak256(c.encode(['tuple(address,uint256,bytes)[]'], [v.calls])),
  tokensHash: E.keccak256(c.encode(['address[]'], [v.tokens])),
  nftsHash: E.keccak256(c.encode(['tuple(address,uint256)[]'], [v.nfts])),
  maxFeeBps: v.maxFeeBps,
  minFeesHash: E.keccak256(c.encode(['uint256[]'], [v.minFees])), nonce: v.nonce, deadline: v.deadline };
const domain = { name: 'Unsweep', version: '1', chainId: v.chainId, verifyingContract: v.vc };
const enc = E.TypedDataEncoder.from(types);
console.log(JSON.stringify({ typehash: E.keccak256(E.toUtf8Bytes(enc.encodeType('Rescue'))),
  digest: E.TypedDataEncoder.hash(domain, types, msg) }));
"""


def art(f, c):
    j = json.load(open(ROOT / 'out' / f / f'{c}.json'))
    return j['abi'], j['bytecode']['object']


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


def deploy(w3, f, c, types=(), args=()):
    abi, bc = art(f, c)
    a = Account.from_key(SPONSOR)
    tx = {'chainId': w3.eth.chain_id, 'nonce': w3.eth.get_transaction_count(a.address), 'gas': 6_000_000,
          'maxFeePerGas': w3.eth.gas_price * 2 + 1, 'maxPriorityFeePerGas': 1, 'value': 0,
          'data': bc + encode(list(types), list(args)).hex()}
    rc = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(a.sign_transaction(tx).raw_transaction))
    assert rc.status == 1
    return w3.eth.contract(address=rc.contractAddress, abi=abi)


SAFE = '0x1111111111111111111111111111111111111111'
T1 = '0x2222222222222222222222222222222222222222'
T2 = '0x3333333333333333333333333333333333333333'
NFT = '0x4444444444444444444444444444444444444444'
VECTOR = dict(safe=SAFE, calls=[(T1, 0, bytes.fromhex('deadbeef'))], tokens=[T1, T2], nfts=[(NFT, 7)],
              maxFeeBps=1000, minFees=[5_000_000, 0], nonce=2**200 + 17, deadline=1_900_000_000)


def test_typehash_string_matches_solidity_source():
    src = (ROOT / 'src' / 'UnsweepDelegate.sol').read_text()
    m = re.search(r'RESCUE_TYPEHASH\s*=\s*keccak256\(\s*"([^"]+)"', src)
    assert m, 'no se encontro RESCUE_TYPEHASH en el contrato'
    assert Web3.keccak(text=m.group(1)) == X.RESCUE_TYPEHASH


def test_parity_solidity_python_js(w3):
    cfg = deploy(w3, 'UnsweepConfig.sol', 'UnsweepConfig', ['address', 'address', 'uint16', 'address[]'],
                 ['0x0000000000000000000000000000000000000Ab1', '0x0000000000000000000000000000000000000FEE', 1500, []])
    impl = deploy(w3, 'UnsweepDelegate.sol', 'UnsweepDelegate', ['address'], [cfg.address])
    v = VECTOR
    r = X.rescue_tuple(v['safe'], v['calls'], v['tokens'], v['nfts'], v['maxFeeBps'],
                       v['minFees'], v['nonce'], v['deadline'])
    chain_id = w3.eth.chain_id
    # Solidity
    sol_th = bytes(impl.functions.RESCUE_TYPEHASH().call())
    sol_dg = bytes(impl.functions.rescueDigest(r).call())
    # Python
    py_th, py_dg = bytes(X.RESCUE_TYPEHASH), bytes(X.rescue_digest(r, chain_id, impl.address))
    # JS (ethers vendorizado de la web)
    jv = dict(safe=SAFE, calls=[[a, str(b), '0x' + d.hex()] for a, b, d in v['calls']], tokens=v['tokens'],
              nfts=[[a, str(i)] for a, i in v['nfts']], maxFeeBps=v['maxFeeBps'],
              minFees=[str(x) for x in v['minFees']], nonce=str(v['nonce']), deadline=str(v['deadline']),
              chainId=chain_id, vc=impl.address)
    out = subprocess.run(['node', '-e', JS, str(ETHERS), json.dumps(jv)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    js = json.loads(out.stdout.strip().splitlines()[-1])
    js_th, js_dg = bytes.fromhex(js['typehash'][2:]), bytes.fromhex(js['digest'][2:])
    assert sol_th == py_th == js_th, (sol_th.hex(), py_th.hex(), js_th.hex())
    assert sol_dg == py_dg == js_dg, (sol_dg.hex(), py_dg.hex(), js_dg.hex())


def test_parity_detects_mismatch():
    """Control negativo: cambiar maxFeeBps cambia el digest (el test no pasa por accidente)."""
    v = VECTOR
    a = X.rescue_tuple(v['safe'], v['calls'], v['tokens'], v['nfts'], 1000, v['minFees'], v['nonce'], v['deadline'])
    b = X.rescue_tuple(v['safe'], v['calls'], v['tokens'], v['nfts'], 999, v['minFees'], v['nonce'], v['deadline'])
    assert X.rescue_digest(a, 1, SAFE) != X.rescue_digest(b, 1, SAFE)
