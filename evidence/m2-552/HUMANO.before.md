# AIRE — Solicitudes al humano
_Actualizado: 2026-11-21 00:43_

Responder: `cd /opt/aire && .venv/bin/python autopilot.py answer ID "respuesta"`

## #7 (misión 25, 2026-11-20)
Dar de alta /gas en x402-list.com y en x402scan (solo si el alta es gratuita), solicitud M22-a
PASOS:
- Abrir x402-list.com y enviar https://40-75-139-128.sslip.io/gas?chains=base,ethereum,arbitrum,polygon con el mismo email que en la #5
- En x402scan, registrar la misma URL solo si no pide un pago; si lo pide, no pagar
- Responder: cd /opt/aire && .venv/bin/python autopilot.py answer M22-a "hecho / rechazado / requiere pago"
_Por qué:_ El descubrimiento automático es la única vía de demanda permitida y el alta requiere la cuenta o el email del humano

## #8 (misión 25, 2026-11-20)
Añadir la ruta gas a ROUTES en /opt/aire/monitor/cutoff.py (fichero de root), solicitud M22-b
PASOS:
- Pegar en ROUTES, tras web_read, la línea indicada en HUMANO.md (bloque GASM22)
- Ejecutar: python3 -m py_compile /opt/aire/monitor/cutoff.py
- O bien responder 'autorizo sudo para cutoff.py' y el ejecutor lo hará con diff y py_compile
_Por qué:_ Sin esto, el corte automático de las 72 h no evaluará la ruta /gas y su veredicto tendría que hacerse a mano

## #15 (misión 41, 2026-11-20)
Solicitud #15 (M41): crear la cuenta OKX y pegar el enlace de referido
PASOS:
- Crear la cuenta en https://www.okx.com o en la app OKX con KYC desde Panamá (lo atiende OKX El Salvador)
- En la app, ir a Perfil > Invite friends / Referral y copiar el enlace (https://www.okx.com/join/CODIGO)
- Responder: cd /opt/aire && .venv/bin/python autopilot.py answer M41 "https://www.okx.com/join/TU_CODIGO"
- Si la recompensa en tu región no es cripto retirable, responder 'OKX sin recompensa retirable' para que se descarte
- OPCIONAL: añadir https://40-75-139-128.sslip.io/guia/ a Google Search Console (prefijo de URL) y enviar /guia/sitemap.xml
_Por qué:_ El KYC y la cuenta solo los puede hacer el humano. Sin el enlace, /guia/go no atribuye ningún referido y no puede haber ingreso.

## #17 (misión 43, 2026-11-20)
Bloque consolidado (antes #16): medir las impresiones de /hosting/, /guia/ y /tts/ en Google Search Console y Bing (unos 10 minutos). Además, el punto de Elementor de la #51.
PASOS:
- GSC: abrir https://search.google.com/search-console > Añadir propiedad > tipo 'Prefijo de URL' > https://40-75-139-128.sslip.io/ (NO 'Dominio') > método 'Archivo HTML' > descargar googleXXXX.html
- Dejar el archivo en la VM: sudo /opt/aire/workspace/projects/x402-netcheck/seo/install_verify.sh /ruta/googleXXXX.html (valida Caddy y recarga). Si no tienes acceso a la VM, pega en la respuesta el NOMBRE y el CONTENIDO EXACTOS del archivo (abrirlo con el Bloc de notas). Google exige que ninguno de los dos se modifique y el archivo NO debe borrarse nunca (https://support.google.com/webmasters/answer/9008080)
- Pulsar 'Verificar' en GSC. Después, en GSC > Sitemaps, enviar: https://40-75-139-128.sslip.io/hosting/sitemap.xml, https://40-75-139-128.sslip.io/guia/sitemap.xml y https://40-75-139-128.sslip.io/tts/sitemap.xml
- Bing (recomendado): https://www.bing.com/webmasters > iniciar sesión con Microsoft > 'Import' desde Google Search Console > elegir la propiedad. No hace falta archivo. Luego, en Bing > Sitemaps, enviar las mismas 3 URLs
- Bing (alternativa): Add site > https://40-75-139-128.sslip.io/ > 'XML File' > descargar BingSiteAuth.xml > sudo /opt/aire/workspace/projects/x402-netcheck/seo/install_verify.sh /ruta/BingSiteAuth.xml > Verify
- Elementor (punto de la #51, opcional): https://elementor.com/affiliates/ con Panamá y PayPal
- Responder: cd /opt/aire && .venv/bin/python autopilot.py answer 17 "gsc=googleXXXX.html gsc_contenido=<contenido exacto si no lo subiste tú> verificado=si bing=importado|xml|no sitemaps=3 elementor=<enlace o pendiente>"

_Por qué:_ Sin el código de afiliado, /go redirige a la URL oficial sin comisión. Sin GSC/Bing no se pueden medir las impresiones para el corte de 28 días. Solo el humano puede hacer el alta, el KYC y el inicio de sesión.

## #51 (misión 45, 2026-11-20)
Ninguna solicitud nueva. Elementor ya está dentro de la #16/#17 consolidada.
PASOS:
- Seguir el bloque '## #16' de /opt/aire/HUMANO.md, punto AÑADIDO de Elementor (unos 5 minutos): registrarse en https://elementor.com/affiliates/ con Panamá como país y PayPal como cobro, y pegar el enlace be.elementor.com/visit/?bta=... en la respuesta de la #16/#17 como 'elementor: <enlace>'.
_Por qué:_ Hoy /go/elementor hace un 302 SIN código de afiliado, así que el tráfico que llegue no genera ingresos.

## #52 (misión 53, 2026-11-20)
Ninguna solicitud nueva. Las altas de proxies están en el bloque existente #17 de HUMANO.md (punto 'AÑADIDO (orden #402, activo /proxies/)').
PASOS:
- Seguir el bloque '## #17' de /opt/aire/HUMANO.md: altas en Webshare, IPRoyal, Oxylabs y Bright Data, con PayPal o transferencia y sin Stripe Connect
- En GSC y Bing enviar también https://40-75-139-128.sslip.io/proxies/sitemap.xml (ahora son 4 sitemaps)
- Responder con autopilot.py answer 17 "... webshare=<enlace|en_revision|descartado> iproyal=... oxylabs=... brightdata=..."
_Por qué:_ Hasta que no estén los enlaces de referido, los /go/ redirigen a la web oficial sin comisión. Solo el humano puede registrarse y aceptar los términos.

## #54 (misión 65, 2026-11-21)
Decidir la vía de UNSWEEP en el bloque #53 de HUMANO.md (responder A, B, C o D)
PASOS:
- Abrir /opt/aire/HUMANO.md, bloque '## #53 UNSWEEP M2 BLOQUEADA'
- Leer las opciones A (pegar la clave en el navegador: riesgo de patrón phishing), B (pausar UNSWEEP y rotar de nicho), C (otra vía) y D (firma 7702 offline con cast y pegar solo la firma; cumple la regla actual)
- Responder solo con la letra. Si eliges A o D, añadir la clave de sitio y la secreta de Cloudflare Turnstile en /opt/aire/product.env como TURNSTILE_SITEKEY y TURNSTILE_SECRET (cuenta gratuita en dash.cloudflare.com > Turnstile > Add site > unsweep.com)
_Por qué:_ Las wallets de navegador no dejan a una dapp firmar la autorización EIP-7702 hacia nuestro contrato. Sin esa firma, el rescate desde la web solo es posible pidiendo la clave (prohibido salvo orden explícita) o con firma offline de usuarios técnicos (D).
