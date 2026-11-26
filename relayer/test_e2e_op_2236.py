"""ORDEN #2236 fase B: e2e SOLO LECTURA contra OP Mainnet (chainId 10).

Se salta si falta OP_RPC_URL. Nunca imprime la URL. Solo eth_chainId, eth_getCode y lecturas del scan.
No firma ni envia transacciones. Reintenta UNICAMENTE ante 'rpc rate limited' (HTTP 429 de cuota del proveedor);
cualquier otro error falla.
"""
import os
import time

import pytest

import svc_mainnet as M

pytestmark = pytest.mark.skipif(not os.environ.get('OP_RPC_URL', '').strip(),
                                reason='OP_RPC_URL no definida (e2e OP solo lectura)')

UNSWEEP_DELEGATE = '0x38bcF425bC4d13624734e09376F2fafc799fA8c8'
WETH_PREDEPLOY = '0x4200000000000000000000000000000000000006'  # predeploy OP Stack (contrato)
PUBLIC_EOA = '0x000000000000000000000000000000000000dEaD'   # direccion publica sin codigo


def _retry_rl(fn, tries=4, wait=8):
    for i in range(tries):
        try:
            return fn()
        except M.ScanError as e:
            if 'rate limited' not in str(e) or i == tries - 1:
                raise
            time.sleep(wait)


def _rpc(method, params):
    return _retry_rl(lambda: M._rpc(M._url('optimism'), method, params, time.time() + 20))


def test_op_1_chain_id_is_10():
    assert int(_rpc('eth_chainId', []), 16) == 10


def test_op_2_delegate_bytecode_documented():
    """Documenta (no exige) si UnsweepDelegate tiene bytecode en OP. Si no lo tiene, el rescate en OP es NO_DISPONIBLE."""
    code = _rpc('eth_getCode', [UNSWEEP_DELEGATE, 'latest']) or '0x'
    has_code = code not in ('0x', '0x0')
    print('UNSWEEP_DELEGATE_OP_CODE_BYTES=%d' % ((len(code) - 2) // 2 if has_code else 0))
    import op_mainnet as OP
    # #162-A: el rescate OP esta activo, asi que el delegate DEBE tener bytecode en OP
    assert has_code, 'UnsweepDelegate sin bytecode en OP con RESCUE_ENABLED=True'
    assert OP.UNSWEEP_DELEGATE.lower() == UNSWEEP_DELEGATE.lower() and OP.rescue_enabled() is True


def test_op_3_scan_public_contract_detects_code_not_delegation():
    s = _retry_rl(lambda: M.scan_mainnet('optimism', WETH_PREDEPLOY))
    assert s['delegation7702']['active'] is False
    assert s['delegation7702']['delegate'] is None
    assert s['isContract'] is True


def test_op_4_scan_public_eoa_no_delegation():
    time.sleep(3)
    s = _retry_rl(lambda: M.scan_mainnet('optimism', PUBLIC_EOA))
    assert s['delegation7702']['active'] is False
    assert s['isContract'] is False
