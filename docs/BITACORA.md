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

## 2026-11-23T20:22Z ORDEN #1638 UX UNSWEEP Fase 1: COMPLETADA
- Commit ecded4ec8923ba7bccbdd0bbf5ee1a8b027dd393 en origin/main (padre dbc2d66).
- #pkConfirm bajo #btnRescue (texto exacto); #btnRescue disabled por defecto; el change de #pkConfirm solo sincroniza disabled.
- #step4: fases firmando/enviando/confirmando y resultado Status, Tx hash y enlace basescan.org/tx/<hash>; goStep 1-4 (RangeError fuera de rango), goStep(4) colapsa 1-3 y hace scrollIntoView.
- Tests: 144 passed (139 + 5 nuevos en relayer/test_ux_1638.py) con projects/unsweep/.venv. test_wizard_1194 actualizado: el paso final no colapsable es ahora step4.
- SRI app.js sha384-nO7yAD6Dromyo7gEltJyU9Ru/c3/vSdykD1R/7Z3aeSWktcctd7y6mqtb0qoIwRm (coincide con lo servido). style.css no tiene atributo integrity y no ha cambiado.
- Deploy: deploy_static exit 0 (backup /opt/aire/backups/unsweep-static/20261123T202216Z), deploy_relayer exit 0 (rollback unsweep-relayer:rollback-dbc2d664).
- Produccion: sha256 de index, app.js y style.css iguales al commit; /api/health 200 (chainId 8453).
- Logs: logs/fase1_1638_deploy.log, logs/fase1_1638_verify.log. Ingresos en cadena atribuibles: ninguno registrado.
