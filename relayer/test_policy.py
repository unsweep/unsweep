import pytest

import policy as P


def test_tiers():
    assert P.tier_bps(999.99) == 1500
    assert P.tier_bps(1_000) == 1000
    assert P.tier_bps(10_000) == 1000
    assert P.tier_bps(10_000.01) == 500
    with pytest.raises(P.PolicyError):
        P.tier_bps(0)


def test_ethereum_min_gas_x15():
    fp = P.fee_plan(1, 200, 10)  # tramo 30 vs gas 15 -> 30
    assert fp.fee_usd == 30 and fp.min_fee_usd == 15
    fp = P.fee_plan(1, 5_000, 400)  # tramo 500 vs gas 600 -> 600 (<=15 % = 750)
    assert fp.fee_usd == 600 and fp.max_fee_bps == 1000
    assert P.fee_plan(8453, 5_000, 400).min_fee_usd == 0  # solo Ethereum
    with pytest.raises(P.PolicyError):
        P.fee_plan(1, 100, 20)  # 30 > 15 USD de techo


def test_caps():
    T = P.TrackRecord
    assert P.cap_usd(T(0)) == 10_000
    assert P.cap_usd(T(3)) == 50_000
    assert P.cap_usd(T(10)) is None
    assert P.cap_usd(T(10, incidents=1)) == 50_000
    assert P.cap_usd(T(0, external_audit=True)) is None


def test_manual_exception(tmp_path):
    h = tmp_path / "HUMANO.md"
    h.write_text("x\nUNSWEEP-EXCEPCION caso42 25_000 USD\n")
    P.check_cap(8453, 9_000, P.TrackRecord(), humano_md=h)
    P.check_cap(8453, 20_000, P.TrackRecord(), "caso42", humano_md=h)
    with pytest.raises(P.PolicyError):
        P.check_cap(8453, 20_000, P.TrackRecord(), "otro", humano_md=h)
    with pytest.raises(P.PolicyError):
        P.check_cap(8453, 30_000, P.TrackRecord(), "caso42", humano_md=h)
    P.check_cap(84532, 10**9, P.TrackRecord())  # testnet: sin limite M4


def test_ethereum_route(monkeypatch):
    P.check_ethereum_route(8453, "")
    with pytest.raises(P.PolicyError):
        P.check_ethereum_route(1, "https://eth.example")
    monkeypatch.delenv("UNSWEEP_FLASHBOTS_TYPE4_VERIFIED", raising=False)
    with pytest.raises(P.PolicyError):
        P.check_ethereum_route(1, "https://rpc.flashbots.net/fast")
    monkeypatch.setenv("UNSWEEP_FLASHBOTS_TYPE4_VERIFIED", "1")
    P.check_ethereum_route(1, "https://rpc.flashbots.net/fast")


def test_simulate_aborts():
    class E:
        def call(self, *a):
            raise ValueError("execution reverted")

    class W:
        eth = E()

    with pytest.raises(P.PolicyError):
        P.simulate(W(), {"to": "0x0", "data": b""})


def test_gas_lost_alert_once(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "DATA_DIR", tmp_path)
    h = tmp_path / "HUMANO.md"
    monkeypatch.setattr(P, "HUMANO_MD", h)
    assert P.record_gas_lost(8453, "0x1", 21000, 3.0) == 3.0
    assert not h.exists()
    assert P.record_gas_lost(8453, "0x2", 21000, 2.5) == 5.5
    assert h.read_text().count("Gas perdido") == 1
    P.record_gas_lost(8453, "0x3", 21000, 1.0)
    assert h.read_text().count("Gas perdido") == 1
