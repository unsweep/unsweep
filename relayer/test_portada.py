"""Tests de portada (#927 c), cambios web del humano (#93/#95) y rediseno captacion."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "web" / "index.html").read_text()
APPJS = (ROOT / "web" / "assets" / "app.js").read_text()
DELEGATE = "0x38bcF425bC4d13624734e09376F2fafc799fA8c8"
CONFIG = "0x56a345661e3999F2b20f1E069aAC14097Fa0D118"


def test_portada_generada_por_pipeline():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "gen_portada.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


LITERAL_956 = "Security notice: We will never DM you first or ask for your seed phrase."


def _texto(s):
    return re.sub(r"<[^>]+>", "", s).strip()


def test_recuadro_superior_literal_956():
    m = re.findall(r'<p class="notice" id="mainnetNotice">(.*?)</p>', INDEX, re.S)
    assert len(m) == 1
    assert _texto(m[0]) == LITERAL_956
    assert "USD" not in m[0]
    body = INDEX.split("<body>", 1)[1]
    assert body.index('id="mainnetNotice"') < body.index('id="step1"')


def test_frase_seguridad_no_repetida_bajo_scan():
    body = INDEX.split("<body>", 1)[1]
    bajo_scan = body.split('id="btnScan"', 1)[1].split('id="step2"', 1)[0]
    for frag in ("never leaves your browser", "never DM you first", "seed phrase", "Non-custodial"):
        assert frag not in bajo_scan, frag


def test_nota_asterisco_bajo_formulario():
    nota = ('<p class="small muted" id="capNote">*Eligibility limit per rescue, not a guarantee of recovery. Rescues above $10,000 get automatic extra '
            'safety checks (a few seconds more).</p>')
    assert INDEX.count(nota) == 1 and INDEX.count('id="capNote"') == 1
    body = INDEX.split("<body>", 1)[1]
    # #1194: notas fuera del flujo, debajo de la tarjeta (tras step3, antes de FAQ)
    assert body.index('id="step3"') < body.index('id="notes"') < body.index('id="capNote"') < body.index('id="faq"')
    assert "10,000 USD get" not in INDEX and "up to $10,000 per rescue" not in INDEX


def test_orden_portada():
    body = INDEX.split("<body>", 1)[1]
    assert body.index('id="btnScan"') < body.index('id="faq"')
    assert body.index('id="btnScan"') < body.index('id="contracts"') < body.index('id="guides"') < body.index("<footer>")
    intro = re.search(r'<p class="intro">(.*?)</p>', INDEX, re.S).group(1)
    assert "\n" not in intro and len(intro) < 150


def test_contratos_una_sola_vez():
    for a in (DELEGATE, CONFIG):
        extra = 1 if a == DELEGATE else 0  # #1194: enlace al contrato tambien en el paso 3
        assert INDEX.count(a) == 2 + extra
        assert INDEX.count(f'href="https://basescan.org/address/{a}#code"') == 1 + extra
    assert INDEX.count('href="https://github.com/unsweep/unsweep"') == 1
    sec = INDEX.split('id="contracts"', 1)[1].split("</section>", 1)[0]
    assert DELEGATE in sec and CONFIG in sec and "github.com/unsweep/unsweep" in sec
    assert INDEX.count("Verify our contracts") == 1 and "<h2>Verify our contracts</h2>" in sec


def test_tokens_plegables_desde_assets():
    toks = json.loads((ROOT / "relayer" / "data" / "assets_8453.json").read_text())
    toks = toks.get("tokens", toks) if isinstance(toks, dict) else toks
    m = re.search(r'<details class="info" id="tokens"><summary>Supported tokens on Base \((\d+)\)</summary>'
                  r'<p class="small">(.*?)</p>', INDEX)
    assert m and int(m.group(1)) == len(toks)
    assert m.group(2).split(", ") == [t["symbol"] for t in toks]
    assert INDEX.count("Supported tokens on Base") == 1


def test_orden1258_arbitrum():
    # subtitulo literal
    intro = re.search(r'<p class="intro">(.*?)</p>', INDEX, re.S).group(1)
    assert _texto(intro) == "Rescue tokens left in a hacked wallet, even if a sweeper bot drains every deposit. When every second matters."
    # gen:top: Base y Arbitrum operativos, Ethereum solo lectura
    top = INDEX.split("<!--gen:top-->", 1)[1].split("<!--/gen:top-->", 1)[0]
    assert 'id="ethNote"' not in INDEX
    # desplegable Arbitrum desde assets_42161.json (N=12) con nota de deteccion automatica
    toks = json.loads((ROOT / "relayer" / "data" / "assets_42161.json").read_text())
    toks = toks.get("tokens", toks) if isinstance(toks, dict) else toks
    assert len(toks) == 12
    m = re.search(r'<details class="info" id="tokensArb"><summary>Supported tokens on Arbitrum \((\d+)\)</summary>'
                  r'<p class="small">(.*?)</p><p class="small muted">(.*?)</p></details>', INDEX)
    assert m and int(m.group(1)) == 12
    assert m.group(2).split(", ") == [t["symbol"] for t in toks]
    assert "Other ERC-20 tokens found in your wallet are detected automatically" in m.group(3)
    assert INDEX.count("Supported tokens on Arbitrum") == 1
    # selector de red y app.js
    assert re.search(r'<option value="arbitrum"[^>]*>', INDEX)
    assert "/arb/api/" in APPJS and "arbitrum: 42161" in APPJS


def test_faq_10_y_jsonld_coherente():
    qs = re.findall(r'<details class="faq"><summary>(.*?)</summary><p>(.*?)</p></details>', INDEX, re.S)
    assert len(qs) == 11
    m = re.findall(r'<script type="application/ld\+json" id="faqSchema">(.*?)</script>', INDEX, re.S)
    assert len(m) == 1
    ld = json.loads(m[0])
    assert ld["@type"] == "FAQPage" and len(ld["mainEntity"]) == 11
    assert [e["name"] for e in ld["mainEntity"]] == [q for q, _ in qs]
    texto = " ".join(a for _, a in qs)
    for frag in ("15% below 1,000 USD", "10% from 1,000 to 10,000 USD", "5% above 10,000 USD",
                 "you pay nothing", "case by case", "support@unsweep.com", "never DM you first"):
        assert frag in texto, frag


def test_faq_comisiones_coinciden_con_policy():
    sys.path.insert(0, str(ROOT / "relayer"))
    import policy  # noqa: E402
    assert policy.tier_bps(999) == 1500
    assert policy.tier_bps(1_000) == 1000 and policy.tier_bps(10_000) == 1000
    assert policy.tier_bps(10_001) == 500
    assert policy.CAP_INITIAL_USD == 100_000 and policy.HIGH_VALUE_USD == 10_000


def test_csp_compatible_sin_inline_ejecutable():
    assert "<style" not in INDEX and ' style="' not in INDEX
    assert not re.search(r"\son[a-z]+=", INDEX)
    scripts = re.findall(r"<script([^>]*)>(.*?)</script>", INDEX, re.S)
    for attrs, body in scripts:
        assert ('src="' in attrs and not body.strip()) or 'type="application/ld+json"' in attrs


def test_ids_de_appjs_intactos():
    ids = set(re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", APPJS))
    assert ids, "no se encontraron ids en app.js"
    for i in ids:
        assert INDEX.count(f'id="{i}"') == 1, i
    assert 'id="ts"' in INDEX


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


def test_wizard_1194():
    body = INDEX.split('<body', 1)[1]
    # (1) wizard: cuerpos y resumenes colapsados con Edit y botones Continue
    for i in ('step1Body', 'step2Body', 'step1Done', 'step2Done', 'edit1', 'edit2', 'btnToStep2', 'btnToStep3'):
        assert INDEX.count(f'id="{i}"') == 1, i
    assert 'Continue to Step 2 &rarr;' in INDEX or 'Continue to Step 2 →' in INDEX or 'Continue to Step 2 ->' in INDEX
    assert 'Continue to Rescue &rarr;' in INDEX or 'Continue to Rescue →' in INDEX or 'Continue to Rescue ->' in INDEX
    # #1638: el paso final pasa a ser step4 (progreso/resultado); step3 ahora se colapsa con Edit
    for i in ('step3Body', 'step3Done', 'edit3', 'step4'):
        assert INDEX.count(f'id="{i}"') == 1, i
    assert 'id="step4Body"' not in INDEX and 'id="step4Done"' not in INDEX  # paso final: no se colapsa
    # (2) notas fuera del flujo
    assert body.index('id="step3"') < body.index('id="notes"') < body.index('id="faq"')
    # (4) destino nuevo y limpio
    assert INDEX.count('id="destNote"') == 1
    # (5) password con ver/ocultar, enlaces de verificacion, DevTools, sin option D
    assert 'type="password"' in INDEX and INDEX.count('id="pkToggle"') == 1
    assert 'github.com/unsweep/unsweep/blob/main/web/assets/app.js' in INDEX
    assert 'DevTools' in INDEX and INDEX.count('id="devtoolsNote"') == 1
    # #1195: literales exactos de #1194
    assert 'Destination wallet (must be a NEW, clean wallet you control - never the compromised one)' in INDEX
    assert 'Verify in DevTools -> Network tab: only the signed payload is sent, key never leaves this tab' in INDEX
    assert 'option D, coming soon' not in INDEX
    assert 'option D' not in INDEX and 'coming soon' not in INDEX
    # (3) scan con spinner y contador
    import pathlib
    js = (pathlib.Path(__file__).resolve().parent.parent / 'web/assets/app.js').read_text()
    assert 'function runScan' in js and 'b.disabled = true' in js and 'spinner' in js and ' s elapsed' in js
