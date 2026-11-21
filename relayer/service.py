"""UNSWEEP relayer HTTP (M2b). Escucha en 172.18.0.1 (gateway privado de la red docker de Caddy).
Solo recibe direcciones publicas y FIRMAS; nunca claves privadas ni seeds. Mainnet desactivada.
"""
import os
import rlp
from eth_account.datastructures import SignedSetCodeAuthorization
from eth_account import Account
from eth_keys.datatypes import Signature
from eth_utils import keccak
from hexbytes import HexBytes
from fastapi import FastAPI, Request, HTTPException
from web3 import Web3

from relayer import PolicyError, RaceAbort, send_rescue
import eip712 as X
import policy as P
from svc_core import (ETH_USD, w3, abi, log, record, screen, turnstile_ok, rate_limited, ofac_set,
                      CHAIN_ID, DELEGATE, CONFIG, TURNSTILE_SECRET, TEST_SECRET, TURNSTILE_SITEKEY)
from relayer import ACTIVE_MAINNETS
from svc_scan import scan, quote
from svc_mainnet import scan_mainnet, record_scan, ScanError, CHAINS as MAINNET_CHAINS
from starlette.concurrency import run_in_threadpool

SPONSOR_KEY = os.environ.get('OPS_PK')  # se carga desde product.env por systemd; nunca se registra
delegate_c = w3.eth.contract(address=DELEGATE, abi=abi('UnsweepDelegate.sol', 'UnsweepDelegate'))
RPC_URL_SEND = os.environ.get("UNSWEEP_SEND_RPC", "")  # Ethereum: Flashbots Protect
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def _ip(req):
    # uvicorn --proxy-headers solo confia en XFF desde Caddy (172.18.0.0/16) y deja en client.host la IP real;
    # no se lee XFF a mano porque su primer valor lo puede falsificar el cliente.
    return req.client.host if req.client else '?'


def _guard(req):
    if rate_limited(_ip(req)):
        raise HTTPException(429, 'demasiadas peticiones')


def _addr(x):
    if not isinstance(x, str) or not Web3.is_address(x):
        raise HTTPException(400, 'direccion invalida')
    return Web3.to_checksum_address(x)


def build_auth(a):
    """Reconstruye la autorizacion 7702 firmada en el navegador y devuelve (auth, autoridad)."""
    chain_id, nonce = int(a['chainId']), int(a['nonce'])
    impl = _addr(a['address'])
    y, r, s = int(a['yParity']), int(a['r'], 16), int(a['s'], 16)
    if chain_id != CHAIN_ID or chain_id == 0:
        raise PolicyError('autorizacion para otra cadena')
    if impl != DELEGATE:
        raise PolicyError('la autorizacion no delega en UnsweepDelegate')
    h = keccak(b'\x05' + rlp.encode([chain_id, bytes.fromhex(impl[2:]), nonce]))
    sig = Signature(vrs=(y, r, s))
    authority = sig.recover_public_key_from_msg_hash(h).to_checksum_address()
    auth = SignedSetCodeAuthorization(chainId=chain_id, address=bytes.fromhex(impl[2:]), nonce=nonce,
                                      yParity=y, r=r, s=s, signature=sig, authorizationHash=HexBytes(h))
    return auth, authority


@app.get('/api/health')
def health():
    try:
        o = len(ofac_set())
    except Exception:
        o = 0
    try:
        ops = P.ops_status(w3.eth.get_balance(Account.from_key(SPONSOR_KEY).address)) if SPONSOR_KEY else 'none'
    except Exception:
        ops = 'unknown'
    return {'ok': True, 'chainId': CHAIN_ID, 'mainnet': CHAIN_ID in ACTIVE_MAINNETS, 'delegate': DELEGATE, 'ofac_entries': o, 'ops': ops,
            'turnstile': 'test' if TURNSTILE_SECRET == TEST_SECRET else ('prod' if TURNSTILE_SECRET else 'off')}


@app.get('/api/config')
def cfg():
    return {'chainId': CHAIN_ID, 'delegate': DELEGATE, 'config': CONFIG, 'turnstileSitekey': TURNSTILE_SITEKEY}


@app.post('/api/scan')
async def api_scan(req: Request):
    _guard(req)  # limitador activo tambien para mainnet (#552)
    b = await req.json()
    chain = str(b.get('chain') or '').lower()
    if chain in MAINNET_CHAINS:
        # M2d: SOLO LECTURA en mainnet; nunca firma ni acepta claves
        addr = _addr(b.get('address'))
        try:
            s = await run_in_threadpool(scan_mainnet, chain, addr)
        except ScanError as e:
            raise HTTPException(503, 'scan unavailable: %s' % e)
        await run_in_threadpool(record_scan, chain, s, _ip(req),
                                req.headers.get('user-agent', ''), req.headers.get('referer', ''))
        return s
    s = scan(_addr(b.get('address')))
    record('scan', 'ok', n_tokens=len(s['tokens']), n_nfts=len(s['nfts']))
    return s


@app.post('/api/quote')
async def api_quote(req: Request):
    _guard(req)
    b = await req.json()
    victim, safe = _addr(b.get('address')), _addr(b.get('safe'))
    if victim == safe:
        raise HTTPException(400, 'la wallet segura debe ser distinta')
    s = scan(victim)
    q, _ = quote(s)
    record('quote', 'ok' if q['policy_ok'] else 'rejected', q['policy_reason'], len(s['tokens']), len(s['nfts']))
    return {'scan': s, 'quote': q}


@app.post('/api/rescue')
async def api_rescue(req: Request):
    _guard(req)
    b = await req.json()
    if not turnstile_ok(b.get('turnstile')):
        record('rescue', 'rejected', 'turnstile')
        raise HTTPException(403, 'verificacion anti-bot fallida')
    if not SPONSOR_KEY:
        raise HTTPException(503, 'relayer sin wallet patrocinadora')
    try:
        auth, victim = build_auth(b['auth'])
        r = b['rescue']
        safe = _addr(r['safe'])
        if safe == victim:
            raise PolicyError('la wallet segura debe ser distinta')
        screen(safe, victim)
        s = scan(victim)
        _, q = quote(s)
        try:
            rescue_t = X.rescue_tuple(
                safe, [(c['target'], int(c['value']), HexBytes(c['data'])) for c in r.get('calls', [])],
                r.get('tokens', []), [(n['token'], int(n['id'])) for n in r.get('nfts', [])],
                int(r['maxFeeBps']), r.get('minFees', []), int(r['nonce']), int(r['deadline']))
        except ValueError as e:
            raise PolicyError(str(e))
        data = delegate_c.encode_abi('rescue', args=[rescue_t, int(b['v']), HexBytes(b['r']), HexBytes(b['s'])])
        qd, _ = quote(s)
        if not qd['policy_ok']:
            raise PolicyError(qd['policy_reason'] or 'rechazado por politica')
        if rescue_t[4] > qd['maxFeeBps']:
            raise PolicyError('maxFeeBps firmado superior al cotizado')
        rc = send_rescue(w3, SPONSOR_KEY, victim, auth, HexBytes(data), q,
                         track=P.TrackRecord.load() if hasattr(P.TrackRecord, 'load') else None,
                         exception_ref=str(b.get('exceptionRef', ''))[:64], rpc_url=RPC_URL_SEND, eth_usd=ETH_USD)
        txh = Web3.to_hex(rc['transactionHash'])
        ok = int(rc['status']) == 1
        record('rescue', 'mined' if ok else 'reverted', None, len(rescue_t[2]), len(rescue_t[3]), txh)
        return {'txHash': txh, 'status': 'success' if ok else 'reverted', 'gasUsed': int(rc['gasUsed']),
                'explorer': f'https://sepolia.basescan.org/tx/{txh}'}
    except (PolicyError, RaceAbort) as e:
        record('rescue', 'rejected', str(e))
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception as e:
        log.warning('rescue error: %s', type(e).__name__)
        record('rescue', 'error', type(e).__name__)
        raise HTTPException(500, 'error interno')
