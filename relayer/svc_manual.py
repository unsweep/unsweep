# #1690 (3): contratos ERC-20 anadidos a mano (Step 2). Misma tuberia que los extras.
# Decision #1690(a): las sondas eth_getCode/balanceOf/decimals/symbol van DIRECTAS al RPC del relayer
# (UNSWEEP_RPC, el mismo endpoint que el w3 de svc_core). Alchemy queda solo para discover_extras (#1684).
from web3 import Web3

import manual as MAN
import oracle as O
from svc_core import assets, RPC

# Mismo endpoint que svc_core.w3, con timeout corto para no bloquear la cotizacion.
_w3m = Web3(Web3.HTTPProvider(RPC, request_kwargs={'timeout': MAN.MANUAL_TIMEOUT}))


class ManualRpcError(Exception):
    pass


def manual_rpc(method, params, _w3=None):
    # JSON-RPC sobre UNSWEEP_RPC. Errores -> excepcion (fail-soft en MAN.probe).
    r = (_w3 or _w3m).provider.make_request(method, params)
    if not isinstance(r, dict) or 'error' in r or 'result' not in r:
        raise ManualRpcError('rpc error')
    return r['result']


def add_manual(s, contracts, rpc=None, allowed=None):
    # Valida y anade a s['extras'] los contratos manuales. Devuelve (aceptados, rechazados). Nunca lanza por RPC.
    if not contracts:
        return [], []
    ok, why = MAN.manual_enabled(s)
    if not ok:
        return [], [{'address': c, 'reason': why} for c in contracts]
    if allowed is None:
        allowed = O.allowlist(assets())
    acc, rej = MAN.resolve(rpc or manual_rpc, s['address'], contracts, allowed, s.get('extras') or [])
    s['extras'] = list(s.get('extras') or []) + acc
    return acc, rej
