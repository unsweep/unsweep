"""#89: tests de tools/gen_env_min.py sobre archivos temporales (nunca toca product.env)."""
import importlib.util
import os
import re
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("gen_env_min", ROOT / "tools" / "gen_env_min.py")
gem = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gem)

FAKE = {
    "TURNSTILE_SECRET": "fake-ts-secret-AAA",
    "TURNSTILE_SITEKEY": "fake-ts-site-BBB",
    "OPS_PK": "0x" + "11" * 32,
    "BASE_RPC_URL": "https://base.example.invalid/k1",
    "OP_RPC_URL": "https://op.example.invalid/k1",
    "ETH_RPC_URL": "https://eth.example.invalid/k2",
}
# Claves que NUNCA deben llegar al contenedor
FORBIDDEN = {
    "PAYER_PK": "0x" + "22" * 32,
    "VICTIM_TEST_PK": "0x" + "33" * 32,
    "GITHUB_TOKEN": "ghp_fakefakefake",
    "CDP_API_KEY_SECRET": "fake-cdp",
    "ETHERSCAN_API_KEY": "fake-es",
    "BASE_RPC_URL_2": "https://other.invalid",
    "ARB_RPC_URL_2": "https://arb.invalid",
}


def _src(tmp_path, data):
    p = tmp_path / "product.env"
    lines = ["# comentario", ""]
    lines += [f"{k}={v}" for k, v in data.items()]
    lines.append("export GITHUB_TOKEN2=ghp_x")
    p.write_text("\n".join(lines) + "\n")
    return p


def test_solo_claves_permitidas_y_permisos_600(tmp_path, capsys):
    src = _src(tmp_path, {**FAKE, **FORBIDDEN})
    dest = tmp_path / "out" / "relayer.env"
    dest.parent.mkdir()
    assert gem.generate(str(src), str(dest)) is True
    got = gem.parse(str(dest))
    assert set(got) == set(gem.ALLOWED)
    assert got == {k: FAKE[k] for k in gem.ALLOWED}
    assert stat.S_IMODE(os.stat(dest).st_mode) == 0o600
    assert gem.check(str(dest)) is True
    out = capsys.readouterr().out
    for v in list(FAKE.values()) + list(FORBIDDEN.values()):
        assert v not in out, "se imprimio un valor"
    # sin temporales residuales
    assert [p.name for p in dest.parent.iterdir()] == ["relayer.env"]


def test_allowed_es_exactamente_lo_aprobado_89():
    assert set(gem.ALLOWED) == {"TURNSTILE_SECRET", "TURNSTILE_SITEKEY", "OPS_PK", "BASE_RPC_URL", "ETH_RPC_URL", "OP_RPC_URL"}


def test_falta_clave_no_escribe(tmp_path):
    data = dict(FAKE)
    del data["OPS_PK"]
    src = _src(tmp_path, data)
    dest = tmp_path / "relayer.env"
    assert gem.generate(str(src), str(dest)) is False
    assert not dest.exists()


def test_check_detecta_extra_y_permisos(tmp_path):
    dest = tmp_path / "relayer.env"
    dest.write_text("".join(f"{k}={v}\n" for k, v in {**FAKE, "PAYER_PK": "x"}.items()))
    os.chmod(dest, 0o600)
    assert gem.check(str(dest)) is False
    dest.write_text("".join(f"{k}={v}\n" for k, v in FAKE.items()))
    os.chmod(dest, 0o644)
    assert gem.check(str(dest)) is False


def test_umask_restaurado(tmp_path):
    src = _src(tmp_path, FAKE)
    before = os.umask(0o022)
    os.umask(before)
    gem.generate(str(src), str(tmp_path / "e"))
    after = os.umask(0o022)
    os.umask(after)
    assert before == after


def test_allowed_cubre_rpc_de_svc_mainnet():
    txt = (ROOT / "relayer" / "svc_mainnet.py").read_text()
    envs = set(re.findall(r"'env':\s*'([A-Z_]+)'", txt))
    assert envs, "no se encontraron CHAINS[...]['env']"
    assert envs <= set(gem.ALLOWED), envs - set(gem.ALLOWED)
