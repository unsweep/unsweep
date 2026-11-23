"""Tests ORDEN #1638 (UX UNSWEEP Fase 1): pkConfirm bajo btnRescue, step4 y goStep 1-4."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "web" / "index.html").read_text()
APPJS = (ROOT / "web" / "assets" / "app.js").read_text()
PK_TEXT = ("I confirm this is ONLY the compromised wallet key (not safe wallet or seed phrase) "
           "and signing happens locally here.")
NODE = shutil.which("node")


def test_pkconfirm_debajo_de_btnrescue_con_texto_exacto():
    i_btn = INDEX.index('id="btnRescue"')
    i_pk = INDEX.index('id="pkConfirm"')
    assert i_btn < i_pk
    assert INDEX.count('id="pkConfirm"') == 1 and INDEX.count('id="btnRescue"') == 1
    # inmediatamente debajo: solo el cierre del boton y la fila del checkbox entre ambos
    between = INDEX[i_btn:i_pk]
    assert between.count("<button") == 0 and between.count("</button>") == 1
    assert PK_TEXT in INDEX


def test_btnrescue_deshabilitado_por_defecto():
    tag = re.search(r'<button[^>]*id="btnRescue"[^>]*>', INDEX).group(0)
    assert re.search(r"\sdisabled(\s|>|=)", tag)


def test_step4_existe_con_fases_y_resultado():
    s4 = INDEX.split('id="step4"', 1)[1].split("</section>", 1)[0]
    for i in ("phSign", "phSend", "phConfirm", "step4Out", "step4Result", "resStatus", "resTx", "resLink"):
        assert f'id="{i}"' in s4, i
    assert "Status" in s4 and "Tx hash" in s4
    body = INDEX.split("<body>", 1)[1]
    assert body.index('id="step3"') < body.index('id="step4"') < body.index('id="notes"')
    # step3 colapsable como los demas pasos
    assert 'id="step3Body"' in INDEX and 'id="step3Done"' in INDEX and 'id="edit3"' in INDEX


def test_appjs_estatico_goStep_y_rescate():
    assert "const MAX_STEP = 4;" in APPJS
    assert "goStep(4)" in APPJS
    assert "https://basescan.org/tx/" in APPJS
    # el listener change de pkConfirm solo sincroniza disabled
    line = next(l for l in APPJS.splitlines() if "c.addEventListener('change'" in l)
    assert "sync" in line and "rescue" not in line.lower().replace("btnrescue", "")
    assert "click()" not in line and "dispatchEvent" not in line


def _extract(name_start, end_marker):
    i = APPJS.index(name_start)
    j = APPJS.index(end_marker, i)
    return APPJS[i:j]


HARNESS = r"""
const els = {};
function mk(id){ const e={id, hidden:false, disabled:false, checked:false, scrolled:0, listeners:{},
  addEventListener(t,f){(this.listeners[t]=this.listeners[t]||[]).push(f);},
  fire(t){(this.listeners[t]||[]).forEach(f=>f({type:t}));},
  scrollIntoView(){this.scrolled++;}}; els[id]=e; return e; }
['step1','step1Body','step1Done','step2','step2Body','step2Done','step3','step3Body','step3Done','step4','pkConfirm','btnRescue'].forEach(mk);
const $ = (id) => els[id];
let rescueCalls = 0;
__CODE__
// rescue click handler stub registered like app.js
els.btnRescue.addEventListener('click', () => { rescueCalls++; });
const out = {};
// pkConfirm sync
out.initialDisabled = els.btnRescue.disabled;
els.pkConfirm.checked = true; els.pkConfirm.fire('change');
out.afterCheck = els.btnRescue.disabled;
els.pkConfirm.checked = false; els.pkConfirm.fire('change');
out.afterUncheck = els.btnRescue.disabled;
out.rescueCallsAfterChange = rescueCalls;
// goStep
const snap = () => [1,2,3,4].map(i => ({sec: els['step'+i].hidden, body: els['step'+i+'Body'] ? els['step'+i+'Body'].hidden : null, done: els['step'+i+'Done'] ? els['step'+i+'Done'].hidden : null}));
out.steps = {};
for (const n of [1,2,3,4]) { goStep(n); out.steps[n] = snap(); }
out.scroll4 = els.step4.scrolled;
out.bad = [0,5,-1,1.5,'x'].map(v => { try { goStep(v); return 'noerr'; } catch(e) { return e.name; } });
out.tx = [txLink(8453, '0x'+'ab'.repeat(32), null), txLink(8453, 'bad', null), txLink(42161, '0x'+'ab'.repeat(32), 'https://arbiscan.io/tx/x')];
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node no disponible")
def test_logica_goStep_pkconfirm_txlink_en_node(tmp_path):
    sync_line = next(l for l in APPJS.splitlines() if "c.addEventListener('change'" in l)
    gostep = _extract("  const MAX_STEP = 4;", "  async function runScan()")
    txlink = _extract("  function txLink(", "  function showResult(")
    code = "\n".join([txlink, gostep, sync_line])
    f = tmp_path / "h.js"
    f.write_text(HARNESS.replace("__CODE__", code))
    r = subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout.strip().splitlines()[-1])
    # pkConfirm: habilita/deshabilita y nunca dispara el rescate
    assert o["initialDisabled"] is True
    assert o["afterCheck"] is False and o["afterUncheck"] is True
    assert o["rescueCallsAfterChange"] == 0
    # goStep(4): pasos 1-3 colapsados (body oculto, Done visible), step4 visible y con scroll
    s4 = o["steps"]["4"]
    for k in range(3):
        assert s4[k]["sec"] is False and s4[k]["body"] is True and s4[k]["done"] is False
    assert s4[3]["sec"] is False
    assert o["scroll4"] >= 1
    # goStep(1): solo step1 visible
    s1 = o["steps"]["1"]
    assert s1[0]["sec"] is False and s1[0]["body"] is False
    assert all(s1[k]["sec"] is True for k in (1, 2, 3))
    # rango validado
    assert o["bad"] == ["RangeError"] * 5
    # enlace basescan
    assert o["tx"][0] == "https://basescan.org/tx/0x" + "ab" * 32
    assert o["tx"][1] is None
    assert o["tx"][2] == "https://arbiscan.io/tx/x"
