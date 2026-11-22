"""Tests del L2 Sequencer Uptime Feed (#1011/#1012): fail-closed antes de precios y comisiones."""
import ast
import os
import socket
import subprocess
import time
import types
from pathlib import Path

import pytest
from web3 import Web3

import policy as P
import sequencer as SEQ

NOW = 1_800_000_000


class _Fn:
    def __init__(self, v):
        self.v = v

    def call(self):
        if isinstance(self.v, Exception):
            raise self.v
        return self.v


class FakeW3:
    def __init__(self, answer=0, started_at=NOW - 7200, now=NOW, err=None, block_err=None):
        self.calls = []
        rd = err if err else (18446744073709551636, answer, started_at, NOW - 10, 18446744073709551636)
        outer = self

        def contract(address, abi):
            outer.calls.append(address)
            return types.SimpleNamespace(functions=types.SimpleNamespace(latestRoundData=lambda: _Fn(rd)))

        def get_block(tag):
            if block_err:
                raise block_err
            return {'timestamp': now}

        self.eth = types.SimpleNamespace(contract=contract, get_block=get_block)


def test_feeds_oficiales_por_chainid():
    assert SEQ.FEEDS[8453] == '0xBCF85224fc0756B9Fa45aA7892530B47e10b6433'
    assert SEQ.FEEDS[42161] == '0xFdB631F5EE196F0ed6FAa767959853A9F217697D'
    assert SEQ.GRACE_PERIOD_S == 3600
    for a in SEQ.FEEDS.values():
        assert Web3.to_checksum_address(a) == a


def test_sequencer_error_es_policy_y_no_oracle():
    import oracle as O
    assert issubclass(SEQ.SequencerError, P.PolicyError)
    assert not issubclass(SEQ.SequencerError, O.OracleError)


def test_ok():
    w = FakeW3(answer=0, started_at=NOW - 3600)
    r = SEQ.check(w, 8453)
    assert r == {'answer': 0, 'startedAt': NOW - 3600, 'now': NOW}
    assert w.calls == ['0xBCF85224fc0756B9Fa45aA7892530B47e10b6433']


def test_feed_elegido_por_chainid_arbitrum():
    w = FakeW3()
    SEQ.check(w, 42161)
    assert w.calls == ['0xFdB631F5EE196F0ed6FAa767959853A9F217697D']


def test_caido():
    with pytest.raises(SEQ.SequencerError, match='caido'):
        SEQ.check(FakeW3(answer=1, started_at=NOW - 99999), 8453)


def test_periodo_de_gracia():
    with pytest.raises(SEQ.SequencerError, match='gracia'):
        SEQ.check(FakeW3(answer=0, started_at=NOW - 3599), 8453)


def test_error_rpc_fail_closed():
    with pytest.raises(SEQ.SequencerError, match='no se pudo leer'):
        SEQ.check(FakeW3(err=ConnectionError('rpc down')), 8453)


def test_error_bloque_fail_closed():
    with pytest.raises(SEQ.SequencerError, match='no se pudo leer'):
        SEQ.check(FakeW3(block_err=TimeoutError('t')), 42161)


def test_answer_desconocido_y_startedat_cero():
    with pytest.raises(SEQ.SequencerError, match='desconocido'):
        SEQ.check(FakeW3(answer=2), 8453)
    with pytest.raises(SEQ.SequencerError, match='startedAt=0'):
        SEQ.check(FakeW3(answer=0, started_at=0), 42161)


def test_sin_feed_no_aplica():
    w = FakeW3(err=ConnectionError('no debe llamarse'))
    for cid in (1, 84532, 31337):
        assert SEQ.check(w, cid) is None
    assert w.calls == []


def test_api_rescue_comprueba_antes_de_precios():
    src = (Path(__file__).parent / 'service.py').read_text()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.AsyncFunctionDef) and n.name == 'api_rescue')
    seg = ast.get_source_segment(src, fn)
    i_seq, i_scan, i_quote = seg.index('SEQ.check(w3, CHAIN_ID)'), seg.index('scan(victim)'), seg.index('quote(s')
    assert i_seq < i_scan < i_quote


def _free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


ANVIL = os.path.expanduser('~/.foundry/bin/anvil')


@pytest.mark.skipif(not os.environ.get('BASE_RPC_URL') or not os.path.exists(ANVIL),
                    reason='fork de Base: requiere BASE_RPC_URL y anvil')
def test_fork_base_feed_real():
    port = _free_port()
    p = subprocess.Popen([ANVIL, '--fork-url', os.environ['BASE_RPC_URL'], '--port', str(port), '--silent'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        w3 = Web3(Web3.HTTPProvider(f'http://127.0.0.1:{port}', request_kwargs={'timeout': 30}))
        for _ in range(120):
            try:
                if w3.is_connected():
                    break
            except Exception:
                pass
            time.sleep(0.5)
        assert w3.eth.chain_id == 8453
        r = SEQ.check(w3, 8453)
        assert r['answer'] == 0
        assert r['startedAt'] > 0 and r['now'] - r['startedAt'] >= SEQ.GRACE_PERIOD_S
    finally:
        p.terminate(); p.wait(timeout=10)
