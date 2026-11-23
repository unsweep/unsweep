# BITACORA UNSWEEP

## 2026-11-22 - Cierre ORDEN HUMANA #1581 (rama guides-fix-1290)

- HECHO: relayer/data/assets_8453.json = 16 tokens; assets_42161.json = 12 tokens (coinciden con las cifras de la orden).
- Commit de contenido: 57730eaa7c91a07a0d52c5cf3bf5cc029d31b234 (6 guias nuevas con JSON-LD TechArticle+FAQPage, sitemap.xml, llms.txt, nav cruzada con aviso de no afiliacion de MetaMask, README tecnico UNSWEEP que sustituye al de Foundry, docs/reddit_educational_posts.md con 4 borradores y 4 disclosures).
- Pruebas: python3 -m pytest -q relayer/test_portada.py -> 15 passed. JSON-LD de las 6 guias parseado con json.loads (TechArticle+FAQPage). Escaneo de secretos del README: limpio.
- web/index.html: git diff b0159b8..57730ea vacio (titulo, subtitulo y notice intactos).
- Despliegue: ALLOW_UNPUSHED=1 bash deploy/deploy_static.sh -> desplegado 57730ea; rollback /opt/aire/backups/unsweep-static/20261122T183805Z.
- Verificacion en vivo (curl): HTTP 200, presentes en sitemap.xml y llms.txt servidos:
  - https://unsweep.com/guides/why-eth-for-gas-gets-stolen-immediately.html
  - https://unsweep.com/guides/rescue-usdc-weth-hacked-metamask-base.html
  - https://unsweep.com/guides/rescue-tokens-hacked-wallet-arbitrum.html
  - https://unsweep.com/guides/sweeper-bot-vs-eip-7702-delegation.html
  - https://unsweep.com/guides/how-to-check-if-wallet-has-sweeper-bot.html
  - https://unsweep.com/guides/what-to-do-first-5-minutes-after-wallet-hack.html
- Borradores Reddit: NO publicados por AIRE; decision del humano segun normas de cada subreddit.
- Sin push (no requerido). Ingresos en cadena atribuibles a esta orden: ninguno registrado (contenido SEO, efecto no medible aun).
- Estado: ESPERA PASIVA, sin abrir misiones nuevas.
