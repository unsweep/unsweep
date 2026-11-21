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
from svc_core import (ETH_USD, assets, w3, abi, log, record, screen, turnstile_ok, rate_limited, ofac_set,
                      CHAIN_ID, DELEGATE, CONFIG, TURNSTILE_SECRET, TEST_SECRET, TURNSTILE_SITEKEY)
from relayer import ACTIVE_MAINNETS
from svc_scan import scan, quote, _eth_usd, config_c
import oracle as O
import sequencer as SEQ
from fastapi.responses import JSONResponse
from svc_mainnet import scan_mainnet, record_scan, ScanError, CHAINS as MAINNET_CHAINS
from starlette.concurrency import run_in_threadpool

SPONSOR_KEY = os.environ.get('OPS_PK')  # se carga desde product.env por systemd; nunca se registra
delegate_c = w3.eth.contract(address=DELEGATE, abi=abi('UnsweepDelegate.sol', 'UnsweepDelegate'))
RPC_URL_SEND = os.environ.get("UNSWEEP_SEND_RPC", "")  # Ethereum: Flashbots Protect
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(O.OracleError)
async def _oracle_fail_closed(req, e):
    # FAIL-CLOSED: sin precio Chainlink valido no se cotiza ni se rescata
    log.warning('oracle fail-closed: %s', e)
    return JSONResponse(status_code=503, content={'detail': 'precio no disponible (oraculo): reintenta en unos minutos'})


def _ip(req):
    # uvicorn --proxy-headers solo confia en XFF desde Caddy (172.18.0.0/16) y deja en client.host la IP real;
    # no se lee XFF a mano porque su primer valor lo puede falsificar el cliente.
    return req.client.host if req.client else '?'


def _guard(req):
    if rate_limited(_ip(req)):
        raise HTTPException(429, 'demasiadas peticiones')


UNLISTED_MSG = ('token fuera de la lista soportada en esta red: %s. Puedes registrar tu caso en '
                'https://github.com/unsweep/unsweep/blob/main/docs/CASOS.md (solo direcciones publicas; '
                'NUNCA incluyas claves privadas ni frases semilla)')


EX_MAX = 20  # #985


def _cs(t):
    try:
        return Web3.to_checksum_address(str(t))
    except Exception:
        return str(t)


def check_allowlist(tokens):
    """Rechaza (PolicyError) cualquier token que no este en assets_<chain>.json."""
    allowed = O.allowlist(assets())
    bad = []
    for t in tokens or []:
        try:
            ok = Web3.to_checksum_address(str(t)) in allowed
        except Exception:
            ok = False
        if not ok:
            bad.append(str(t)[:42])
    if bad:
        raise PolicyError(UNLISTED_MSG % ', '.join(bad[:5]))


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
    if s.get('approvalsError'):  # #92: 429/RPC caido -> error VISIBLE (app.js muestra 'Scan failed: ...')
        raise HTTPException(503, 'approvals check unavailable (%s); retry in a minute' % s['approvalsError'])
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
    s['safe'] = safe  # #985: destino de la simulacion de extras
    q, _ = quote(s, extras=[str(x) for x in (b.get('extras') or [])][:EX_MAX])
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
        listed_set = O.allowlist(assets())
        req_extras = [str(t) for t in r.get('tokens', []) if _cs(t) not in listed_set]
        check_allowlist([t for t in r.get('tokens', []) if _cs(t) in listed_set])
        if len(req_extras) > EX_MAX:
            raise PolicyError('demasiados tokens sin verificar (max %d)' % EX_MAX)
        safe = _addr(r['safe'])
        if safe == victim:
            raise PolicyError('la wallet segura debe ser distinta')
        screen(safe, victim)
        SEQ.check(w3, CHAIN_ID)  # #1011/#1012: L2 Sequencer Uptime Feed, fail-closed, antes de precios y comisiones
        s = scan(victim)
        s['safe'] = safe
        _, q = quote(s, extras=req_extras or None)
        if req_extras:  # #985: solo extras seleccionados por el servidor tras simular
            q0, _ = quote(s, extras=req_extras)
            sel = {_cs(l['token']) for l in q0['lines'] if l.get('unverified')}
            if any(_cs(t) not in sel for t in req_extras):
                raise PolicyError(q0.get('extras_reason') or 'token sin verificar excluido por simulacion')
        try:
            rescue_t = X.rescue_tuple(
                safe, [(c['target'], int(c['value']), HexBytes(c['data'])) for c in r.get('calls', [])],
                r.get('tokens', []), [(n['token'], int(n['id'])) for n in r.get('nfts', [])],
                int(r['maxFeeBps']), r.get('minFees', []), int(r['nonce']), int(r['deadline']))
        except ValueError as e:
            raise PolicyError(str(e))
        data = delegate_c.encode_abi('rescue', args=[rescue_t, int(b['v']), HexBytes(b['r']), HexBytes(b['s'])])
        qd, _ = quote(s, extras=req_extras or None)
        if not qd['policy_ok']:
            raise PolicyError(qd['policy_reason'] or 'rechazado por politica')
        if rescue_t[4] > qd['maxFeeBps']:
            raise PolicyError('maxFeeBps firmado superior al cotizado')
        high = CHAIN_ID in P.MAINNETS and P.needs_extra_checks(q.rescued_usd)
        split = None
        if high:  # #927(c): datos para la resimulacion exacta SAFE/fee
            split = {'lines': qd['lines'], 'safe': safe, 'fee_to': config_c.functions.feeRecipient().call()}
        try:
            rc = send_rescue(w3, SPONSOR_KEY, victim, auth, HexBytes(data), q,
                             track=P.TrackRecord.load() if hasattr(P.TrackRecord, 'load') else None,
                             exception_ref=str(b.get('exceptionRef', ''))[:64], rpc_url=RPC_URL_SEND,
                             eth_usd=_eth_usd(), split=split)
        except (PolicyError, RaceAbort) as e:
            if high:
                P.record_case(CHAIN_ID, q.rescued_usd, q.fee_usd, 'rechazado: ' + str(e)[:80])
            raise
        txh = Web3.to_hex(rc['transactionHash'])
        ok = int(rc['status']) == 1
        if high:  # #927(e)
            P.record_case(CHAIN_ID, q.rescued_usd, q.fee_usd, 'ok' if ok else 'revert', txh)
        record('rescue', 'mined' if ok else 'reverted', None, len(rescue_t[2]), len(rescue_t[3]), txh)
        return {'txHash': txh, 'status': 'success' if ok else 'reverted', 'gasUsed': int(rc['gasUsed']),
                'explorer': f'https://sepolia.basescan.org/tx/{txh}'}
    except O.OracleError:
        raise  # fail-closed -> 503 via exception_handler (antes que PolicyError: es subclase)
    except (PolicyError, RaceAbort) as e:
        record('rescue', 'rejected', str(e))
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception as e:
        log.warning('rescue error: %s', type(e).__name__)
        record('rescue', 'error', type(e).__name__)
        raise HTTPException(500, 'error interno')
