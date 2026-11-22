import time
#!/usr/bin/env python3
"""PASO 3 (#737) B1: proxy JSON-RPC local (127.0.0.1) de SOLO LECTURA para que anvil haga fork
sin poner la URL con clave en la linea de comandos.
- Lee BASE_RPC_URL de /opt/aire/product.env en tiempo de ejecucion y NUNCA la imprime.
- Garantia de 0 transacciones en mainnet: solo reenvia metodos de lectura (allowlist);
  cualquier envio/firma (eth_sendRawTransaction, eth_sendTransaction, eth_sign*, personal_*...)
  se rechaza, tambien dentro de lotes, y se contabiliza en /tmp/rpc_proxy_blocked.count.
Uso: rpc_proxy.py [puerto] (por defecto 8547)."""
import json, re, sys, threading, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ALLOWED = {
    'eth_chainId', 'net_version', 'web3_clientVersion', 'eth_blockNumber', 'eth_getBlockByNumber',
    'eth_getBlockByHash', 'eth_getBalance', 'eth_getCode', 'eth_getStorageAt', 'eth_getTransactionCount',
    'eth_call', 'eth_estimateGas', 'eth_gasPrice', 'eth_maxPriorityFeePerGas', 'eth_feeHistory',
    'eth_getTransactionByHash', 'eth_getTransactionReceipt', 'eth_getBlockReceipts', 'eth_getLogs',
    'eth_getProof', 'eth_getAccount', 'eth_getBlockTransactionCountByNumber',
    'eth_getTransactionByBlockNumberAndIndex', 'eth_syncing',
}
COUNT = '/tmp/rpc_proxy_blocked.count'
BLOCKED_LOG = '/tmp/rpc_proxy_blocked_methods.log'
LOCK = threading.Lock()


def upstream():
    # #1011: RPC_ENV_KEY elige la clave de product.env (p.ej. ARB_RPC_URL_2); por defecto BASE_RPC_URL.
    import os
    key = os.environ.get('RPC_ENV_KEY', 'BASE_RPC_URL')
    if not re.fullmatch(r'[A-Z0-9_]+', key):
        raise SystemExit('RPC_ENV_KEY invalida')
    for line in open('/opt/aire/product.env'):
        m = re.match(r'\s*(?:export\s+)?' + key + r'\s*=\s*(.+)', line)
        if m:
            return m.group(1).strip().strip('"\'')
    raise SystemExit(key + ' no encontrada')


UP = upstream()


def bump(methods=()):
    with LOCK:
        try:
            with open(BLOCKED_LOG, 'a') as f:
                f.write('%d %s\n' % (int(time.time()), ','.join(str(m)[:64] for m in methods)))
        except Exception:
            pass
        try:
            n = int(open(COUNT).read().strip() or 0)
        except Exception:
            n = 0
        open(COUNT, 'w').write(str(n + 1))


class H(BaseHTTPRequestHandler):
    def reply(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        try:
            payload = json.loads(body)
        except Exception:
            return self.reply(400, b'{"jsonrpc":"2.0","id":null,"error":{"code":-32700,"message":"parse error"}}')
        reqs = payload if isinstance(payload, list) else [payload]
        bad = [r for r in reqs if not isinstance(r, dict) or r.get('method') not in ALLOWED]
        if bad:
            bump([r.get('method') if isinstance(r, dict) else '?' for r in bad])
            err = [{'jsonrpc': '2.0', 'id': (r.get('id') if isinstance(r, dict) else None),
                    'error': {'code': -32601, 'message': 'bloqueado por proxy de solo lectura (0 tx en mainnet)'}}
                   for r in reqs]
            return self.reply(200, json.dumps(err if isinstance(payload, list) else err[0]).encode())
        try:
            req = urllib.request.Request(UP, data=body, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as r:
                data, code = r.read(), r.status
        except urllib.error.HTTPError as e:
            data, code = e.read(), e.code
        except Exception:
            data, code = b'{"jsonrpc":"2.0","id":null,"error":{"code":-32000,"message":"proxy upstream error"}}', 502
        self.reply(code, data)

    def log_message(self, *a):
        pass  # sin logs: evita filtrar nada


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8547
    ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()
