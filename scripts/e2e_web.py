#!/usr/bin/env python3
"""E2E UNSWEEP por la web real, modo MAINNET (#737 4a-fix3, respuesta humana #85 = X).
Valida SOLO el escaneo en Base mainnet (8453): sin clave privada, sin firma y sin /api/rescue.
Un solo intento, sin reintentos. Navegador headless estandar; no interactua con Turnstile.
Uso: e2e_web.py [URL] [DIRECCION_PUBLICA]
  URL por defecto: https://unsweep.com/
  DIRECCION por defecto: VICTIM de .e2e/addrs.env (solo direccion publica; nunca se lee keys.env)."""
import json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent / '.e2e'
URL = sys.argv[1] if len(sys.argv) > 1 else 'https://unsweep.com/'

def envfile(p):
    d = {}
    for line in p.read_text().splitlines():
        if '=' in line:
            k, v = line.split('=', 1); d[k.strip()] = v.strip()
    return d

if len(sys.argv) > 2:
    ADDR = sys.argv[2]
else:
    ADDR = envfile(BASE / 'addrs.env')['VICTIM']
if not re.fullmatch(r'0x[0-9a-fA-F]{40}', ADDR or ''):
    print('RESULT', json.dumps({'abort': 'bad_address'})); sys.exit(1)

def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)

def wait_text(page, sel, pat, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        txt = page.inner_text(sel)
        if re.search(pat, txt):
            return txt
        time.sleep(1)
    return None

result = {'stage': 'start', 'mode': 'mainnet_scan_only', 'url': URL}
signing_calls = []
BASE.mkdir(exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()
    def on_req(r):
        if r.url.endswith('/api/rescue') or r.url.endswith('/api/quote'):
            signing_calls.append(r.url)
    page.on('request', on_req)
    page.on('console', lambda m: log('console', m.type, m.text[:200]))
    try:
        page.goto(URL, wait_until='load', timeout=60000)
        page.select_option('#chain', 'base')
        net = page.eval_on_selector('#step1 #chain', 'e => e.options[e.selectedIndex].text')
        log('STEP1_NETWORK', net); result['network'] = net
        if not net or 'Base' not in net or re.search(r'sepolia|testnet', net, re.I):
            raise SystemExit('network_not_mainnet')
        page.fill('#victim', ADDR); page.click('#btnScan')
        t = wait_text(page, '#scanOut', r'Address:|failed|Invalid', 120)
        log('STEP1', t); result['stage'] = 'scan'; result['scanOut'] = (t or '')[:500]
        if not t or 'Address:' not in t: raise SystemExit('scan_failed')
        if re.search(r'failed|error', t, re.I): raise SystemExit('scan_error')
        result['stage'] = 'scan_ok'
    except SystemExit as e:
        result['abort'] = str(e)
    except Exception as e:
        result['abort'] = type(e).__name__ + ': ' + str(e)[:300]
    finally:
        try: page.screenshot(path=str(BASE / 'final_mainnet.png'), full_page=True)
        except Exception: pass
        result['signing_calls'] = signing_calls
        b.close()
print('RESULT', json.dumps(result))
# Exito: escaneo mainnet correcto y ninguna llamada de cotizacion/rescate (sin firma).
_ok = ('abort' not in result and result.get('stage') == 'scan_ok' and not signing_calls)
sys.exit(0 if _ok else 1)
