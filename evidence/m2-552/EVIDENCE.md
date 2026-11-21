# Orden #552 (UNSWEEP M2 hardening) - evidencias
- (a) OK: headers_*unsweep*.txt -> unsweep.com 200; www 301 -> https://unsweep.com/ (redirección de la orden #13), ambos con las 6 cabeceras (CSP incluida); 200 final tras seguir la redirección.
- (b) OK: Caddyfile.diff solo toca los bloques unsweep.com/www; los sha256 de las cabeceras x402 (/gas 402, / 405) son iguales antes y después (sin líneas variables). Copia: x402-netcheck/Caddyfile.bak-m2-552-*. caddy validate=Valid; reload en caliente, sin reiniciar contenedores.
- (c) OK: HTML servido con 0 <script>, 0 src externos y 0 <style> inline (CSS en /assets/style.css).
- (d) NO APLICABLE / NO VERIFICADO: no existe ningún escáner ni relayer HTTP desplegado (relayer.py es una biblioteca; ss y docker no muestran ningún servicio UNSWEEP). La build caddy:2 v2.11.9 no trae rate_limit (no se recompila). Límite a implementar cuando exista el backend: slowapi 10/min/IP en el escáner y 3/min/IP en el relayer, con la IP leída de X-Forwarded-For solo desde Caddy.
- (e) OK: ss_ltnp.txt -> en 0.0.0.0 solo sshd:22 (excluido) y docker-proxy 80/443 (Caddy). Sin compose ni contenedores UNSWEEP.
- (f) OK: 'We will never DM you first.' en la línea siguiente a 'We never ask for your private key'.
- (3) bundles web3: la web no usa web3, así que no hay bundle (ni viem ni package-lock) que registrar. connect-src='self' porque no se usa ningún RPC.
- (g) Basescan: etherscan_v2_check.txt -> las direcciones NUEVAS no están verificadas. Una línea añadida al bloque #54 de HUMANO.md (el #53 ya no existe), ver HUMANO.diff.
