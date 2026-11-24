"""#562/#1684: scan_extras emite una linea INFO con n_extras, pages y ms, sin direcciones."""
import svc_scan as S

ADDR = '0x' + '11' * 20


class _Log:
    def __init__(self):
        self.info_calls, self.warn_calls = [], []

    def info(self, fmt, *a):
        self.info_calls.append(fmt % a)

    def warning(self, fmt, *a):
        self.warn_calls.append(fmt % a)


def test_scan_extras_log_n_extras(monkeypatch):
    L = _Log()
    monkeypatch.setattr(S, 'log', L)
    monkeypatch.setattr(S, 'assets', lambda: [])
    monkeypatch.setattr(S.O, 'allowlist', lambda a: set())
    monkeypatch.setattr(S, '_extras_rpc', lambda m, p: {})

    def fake_discover(rpc, addr, allowed):
        rpc('alchemy_getTokenBalances', [addr, 'erc20'])
        rpc('alchemy_getTokenBalances', [addr, 'erc20'])
        return []
    monkeypatch.setattr(S.EX, 'discover_extras', fake_discover)
    assert S.scan_extras(ADDR) == []
    assert not L.warn_calls
    lines = [x for x in L.info_calls if 'n_extras=' in x]
    assert len(lines) == 1
    ln = lines[0]
    assert 'n_extras=0' in ln and 'pages=2' in ln and 'ms=' in ln and ('chain=%s' % S.CHAIN_ID) in ln
    assert '11' * 20 not in ln and '0x' not in ln
