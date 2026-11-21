#!/usr/bin/env python3
"""E2E UNSWEEP M2c-2 por la web real (un solo intento, sin reintentos).
Navegador headless estandar; NO evade Turnstile. La clave de prueba nunca se imprime."""
import json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent / '.e2e'

def envfile(p):
    d = {}
    for line in p.read_text().splitlines():
        if '=' in line:
            k, v = line.split('=', 1); d[k.strip()] = v.strip()
    return d

keys = envfile(BASE / 'keys.env'); addrs = envfile(BASE / 'addrs.env')
PK = keys['VICTIM_PK']; VICTIM = addrs['VICTIM']; SAFE = addrs['SAFE']

def clean(s):
    s = str(s or '')
    return s.replace(PK, '[REDACTED]').replace(PK[2:], '[REDACTED]')

def log(*a):
    print(time.strftime('%H:%M:%S'), *[clean(x) for x in a], flush=True)

def wait_text(page, sel, pat, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        txt = page.inner_text(sel)
        if re.search(pat, txt):
            return txt
        time.sleep(1)
    return None

result = {'stage': 'start'}
rescue_resp = {}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()
    def on_resp(r):
        if r.url.endswith('/api/rescue'):
            try: rescue_resp['status'] = r.status; rescue_resp['body'] = r.text()[:500]
            except Exception as e: rescue_resp['err'] = type(e).__name__
    page.on('response', on_resp)
    page.on('console', lambda m: log('console', m.type, m.text[:200]))
    try:
        page.goto('https://unsweep.com/', wait_until='load', timeout=60000)
        # paso 1
        page.select_option('#chain', 'testnet')
        page.fill('#victim', VICTIM); page.click('#btnScan')
        t = wait_text(page, '#scanOut', r'Address:|failed|Invalid', 120)
        log('STEP1', t); result['stage'] = 'scan'
        if not t or 'Address:' not in t: raise SystemExit('scan_failed')
        net = page.eval_on_selector('#step1 #chain', 'e => e.options[e.selectedIndex].text')
        log('STEP1_NETWORK', net); result['network'] = net
        if 'Base Sepolia' not in (net or ''): raise SystemExit('scan_not_testnet')
        page.wait_for_selector('#step2', state='visible', timeout=10000)
        # paso 2
        page.fill('#safe', SAFE); page.click('#btnQuote')
        t = wait_text(page, '#quoteOut', r'Estimated value|failed|Invalid|Not eligible|Nothing', 120)
        log('STEP2', t); result['stage'] = 'quote'
        page.wait_for_selector('#step3', state='visible', timeout=10000)
        # paso 3: Turnstile real (sin evasion)
        tok = None; t0 = time.time()
        while time.time() - t0 < 90:
            try:
                tok = page.eval_on_selector('input[name="cf-turnstile-response"]', 'e => e.value')
            except Exception:
                tok = None
            if tok: break
            time.sleep(2)
        result['turnstile_token'] = bool(tok)
        log('TURNSTILE token_obtenido=', bool(tok), 'segundos=', int(time.time() - t0))
        page.screenshot(path=str(BASE / 'step3.png'), full_page=True)
        if not tok: raise SystemExit('turnstile_not_solved_headless')
        result['stage'] = 'turnstile'
        page.fill('#pk', PK); page.click('#btnRescue')
        t = wait_text(page, '#rescueOut', r'Status:|failed', 240)
        log('STEP3', t); result['stage'] = 'rescue'; result['rescueOut'] = clean(t)
    except SystemExit as e:
        result['abort'] = str(e)
    except Exception as e:
        result['abort'] = type(e).__name__ + ': ' + clean(str(e))[:300]
    finally:
        try: page.screenshot(path=str(BASE / 'final.png'), full_page=True)
        except Exception: pass
        result['rescue_http'] = {k: clean(v) for k, v in rescue_resp.items()}
        b.close()
print('RESULT', json.dumps(result))
