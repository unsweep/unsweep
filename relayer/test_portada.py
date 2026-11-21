"""Tests de portada (#927 c) y de los cambios web del humano (#93/#95)."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "web" / "index.html").read_text()
APPJS = (ROOT / "web" / "assets" / "app.js").read_text()


def test_portada_generada_por_pipeline():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "gen_portada.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_portada_tope_y_nota_literal_927():
    assert "up to $100,000* per rescue" in INDEX
    assert ('<p class="small" id="capNote">*Rescues above $10,000 get automatic extra '
            'safety checks (a few seconds more).</p>') in INDEX
    assert INDEX.count('id="capNote"') == 1
    assert "up to $10,000 per rescue" not in INDEX


def test_web_limpia_humano():
    assert INDEX.count('href="mailto:support@unsweep.com"') == 1
    assert ('Contact: <a href="mailto:support@unsweep.com">support@unsweep.com</a> '
            '(never send keys or seed phrases).') in INDEX
    assert "Supported token:" not in INDEX
    assert "tabRescueMainnet" not in INDEX and "tabScan" not in INDEX


def test_appjs_humano_ethereum_solo_lectura():
    assert "if (chain === 'ethereum') {" in APPJS
    assert "if (chain === 'base' || chain === 'ethereum') {" not in APPJS
    assert re.search(r"Ethereum mainnet: read-only check", APPJS)
