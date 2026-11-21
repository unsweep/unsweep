"""Acta PASO 4 (#90/#141): verifica en cadena (eth_call, solo lectura) description() y decimals()
de los feeds Chainlink de relayer/data/assets_8453.json en Base 8453. No firma nada.
Uso: python tools/verify_feeds_8453.py [RPC_URL]  (por defecto https://mainnet.base.org)
Sale con 1 si algun feed no coincide con su simbolo/par/decimales.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from web3 import Web3

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'relayer' / 'data' / 'assets_8453.json'
OUT = ROOT / 'evidence' / 'chainlink'
ABI = [{'name': 'description', 'type': 'function', 'stateMutability': 'view', 'inputs': [], 'outputs': [{'type': 'string'}]},
       {'name': 'decimals', 'type': 'function', 'stateMutability': 'view', 'inputs': [], 'outputs': [{'type': 'uint8'}]}]


def norm(x):
    x = x.strip().upper()
    return 'ETH' if x == 'WETH' else x


def main():
    rpc = sys.argv[1] if len(sys.argv) > 1 else 'https://mainnet.base.org'
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 20}))
    assert w3.eth.chain_id == 8453, 'no es Base mainnet'
    blk = w3.eth.get_block('latest')
    bn = blk['number']
    d = json.loads(ASSETS.read_text())
    rows = [('ETH/USD (eth_usd_feed)', 'ETH', d['eth_usd_feed'])] + [(t['symbol'], t['symbol'], t['feed']) for t in d['tokens']]
    out, ok_all = [], True
    for label, sym, f in rows:
        c = w3.eth.contract(address=Web3.to_checksum_address(f['address']), abi=ABI)
        desc = c.functions.description().call(block_identifier=bn)
        dec = int(c.functions.decimals().call(block_identifier=bn))
        base, quote = [p.strip() for p in desc.split('/')]
        ok = (norm(base) == norm(sym) and quote.upper() == f['quote'].upper()
              and desc.replace(' ', '').upper() == f['pair'].replace(' ', '').upper()
              and dec == int(f['decimals']))
        ok_all &= ok
        out.append({'simbolo': label, 'feed': f['address'], 'description_onchain': desc, 'decimals_onchain': dec,
                    'par_esperado': f['pair'], 'decimals_esperado': int(f['decimals']), 'coincide': ok})
    acta = {'chain_id': 8453, 'rpc': rpc, 'bloque': bn, 'bloque_timestamp': blk['timestamp'],
            'generado_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'metodo': 'eth_call description()/decimals() en el bloque indicado (solo lectura)',
            'tokens': len(d['tokens']), 'todos_coinciden': ok_all, 'feeds': out}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'acta_feeds_8453.json').write_text(json.dumps(acta, indent=2, ensure_ascii=False) + '\n')
    md = ['# Acta de verificacion on-chain de feeds Chainlink (Base 8453)', '',
          f'- Bloque: {bn} (timestamp {blk["timestamp"]}), RPC: {rpc}', f'- Generado (UTC): {acta["generado_utc"]}',
          f'- Metodo: {acta["metodo"]}', f'- Resultado: {"TODOS COINCIDEN" if ok_all else "HAY DISCREPANCIAS"}', '',
          '| Simbolo | Feed | description() | decimals() | Esperado | OK |', '|---|---|---|---|---|---|']
    md += [f"| {r['simbolo']} | {r['feed']} | {r['description_onchain']} | {r['decimals_onchain']} | {r['par_esperado']} / {r['decimals_esperado']} | {'si' if r['coincide'] else 'NO'} |" for r in out]
    (OUT / 'acta_feeds_8453.md').write_text('\n'.join(md) + '\n')
    for r in out:
        print(r['simbolo'], '|', r['description_onchain'], '|', r['decimals_onchain'], '|', 'OK' if r['coincide'] else 'FALLO')
    print('BLOQUE', bn, 'TODOS_COINCIDEN', ok_all)
    sys.exit(0 if ok_all else 1)


if __name__ == '__main__':
    main()
