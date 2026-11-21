"""UNSWEEP M2b nucleo: config, filtros, turnstile, rate limit, registro sin datos personales."""
import json, os, time, logging, threading
from collections import defaultdict, deque
from datetime import datetime

import requests, psycopg
from web3 import Web3

from relayer import PolicyError, TESTNETS

log = logging.getLogger('unsweep')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RPC = os.environ.get('UNSWEEP_RPC', 'https://sepolia.base.org')
CHAIN_ID = int(os.environ.get('UNSWEEP_CHAIN_ID', '84532'))
DELEGATE = Web3.to_checksum_address(os.environ.get('UNSWEEP_DELEGATE', '0xBe5a2F788fa56DeCc7b13a20F45429d167a8080e'))
CONFIG = Web3.to_checksum_address(os.environ.get('UNSWEEP_CONFIG', '0x2421aa3a6c473fD7ccA6be9bF4024E92CE80176d'))
ETH_USD = float(os.environ.get('UNSWEEP_ETH_USD', '3000'))  # ESTIMACION solo para regla fee>=3xgas en testnet
ASSETS_FILE = os.path.join(HERE, 'data', f'assets_{CHAIN_ID}.json')
OFAC_FILE = os.path.join(HERE, 'data', 'ofac_eth.json')
OFAC_MAX_AGE_S = 7 * 86400
TEST_SECRET = '1x0000000000000000000000000000000AA'
TEST_SITEKEY = '1x00000000000000000000AA'
TURNSTILE_SECRET = os.environ.get('TURNSTILE_SECRET') or (TEST_SECRET if CHAIN_ID in TESTNETS else '')
TURNSTILE_SITEKEY = os.environ.get('TURNSTILE_SITEKEY') or TEST_SITEKEY
RATE = int(os.environ.get('UNSWEEP_RATE_PER_MIN', '20'))
PG_DSN = os.environ.get('UNSWEEP_PG', 'dbname=unsweep')

if CHAIN_ID not in TESTNETS:
    raise SystemExit('mainnet desactivada en M2b')

w3 = Web3(Web3.HTTPProvider(RPC, request_kwargs={'timeout': 20}))


def abi(f, c):
    return json.load(open(os.path.join(ROOT, 'out', f, f'{c}.json')))['abi']


def assets():
    try:
        return json.load(open(ASSETS_FILE))
    except FileNotFoundError:
        return {'tokens': [], 'nfts': []}


def record(kind, status, reason=None, n_tokens=0, n_nfts=0, tx_hash=None):
    """Sin IP, sin direcciones, sin firmas. tx_hash es publico."""
    try:
        with psycopg.connect(PG_DSN, connect_timeout=3) as c:
            c.execute('INSERT INTO rescue_events(chain_id,kind,status,reason,n_tokens,n_nfts,tx_hash) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                      (CHAIN_ID, kind, status, (reason or '')[:200] or None, n_tokens, n_nfts, tx_hash))
    except Exception as e:
        log.warning('pg record failed: %s', type(e).__name__)


def ofac_set():
    """Fail-closed: lista ausente, vacia o >7 dias => excepcion."""
    try:
        d = json.load(open(OFAC_FILE))
        age = time.time() - datetime.fromisoformat(d['fetched_at']).timestamp()
    except Exception:
        raise PolicyError('lista OFAC no disponible')
    if not d.get('addresses') or age > OFAC_MAX_AGE_S:
        raise PolicyError('lista OFAC vacia o caducada')
    return {a.lower() for a in d['addresses']}


_ss = {'t': 0.0, 'set': set()}


def scamsniffer_flag(addr):
    try:
        if time.time() - _ss['t'] > 3600:
            r = requests.get('https://raw.githubusercontent.com/scamsniffer/scam-database/main/blacklist/address.json', timeout=10)
            r.raise_for_status()
            _ss['set'] = {a.lower() for a in r.json()}
            _ss['t'] = time.time()
        return addr.lower() in _ss['set']
    except Exception as e:
        log.warning('scamsniffer fail-open: %s', type(e).__name__)
        return False


GOPLUS_BAD = ('cybercrime', 'money_laundering', 'phishing_activities', 'stealing_attack', 'sanctioned',
              'mixer', 'darkweb_transactions', 'blackmail_activities')


def goplus_flag(addr):
    try:
        r = requests.get(f'https://api.gopluslabs.io/api/v1/address_security/{addr}', params={'chain_id': 8453}, timeout=10).json()
        res = r.get('result') or {}
        return [k for k in GOPLUS_BAD if str(res.get(k)) == '1']
    except Exception as e:
        log.warning('goplus fail-open: %s', type(e).__name__)
        return []


def screen(safe, victim):
    o = ofac_set()
    if safe.lower() in o or victim.lower() in o:
        raise PolicyError('direccion sancionada (OFAC)')
    if scamsniffer_flag(safe):
        raise PolicyError('wallet segura marcada (ScamSniffer)')
    g = goplus_flag(safe)
    if g:
        raise PolicyError('wallet segura marcada (GoPlus: ' + ','.join(g) + ')')
    if goplus_flag(victim) or scamsniffer_flag(victim):
        log.info('victima marcada por reputacion (solo log, es esperable en wallets comprometidas)')


def turnstile_ok(token):
    if not TURNSTILE_SECRET or not token:
        return False
    try:
        r = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify',
                       data={'secret': TURNSTILE_SECRET, 'response': token}, timeout=10).json()
        return bool(r.get('success'))
    except Exception:
        return False  # fail-closed


_hits = defaultdict(deque)
_lock = threading.Lock()


def rate_limited(ip):
    now = time.time()
    with _lock:
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE:
            return True
        q.append(now)
        return False
