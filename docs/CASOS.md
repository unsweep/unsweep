# UNSWEEP - Casos de tokens no soportados

Registro de solicitudes de rescate de tokens fuera de la lista de Base (8453).

NUNCA incluir aquí claves privadas, frases semilla, firmas, autorizaciones 7702 ni datos personales.
Solo datos públicos: red, dirección del contrato del token, símbolo y fecha.

Criterio de alta: el token necesita un feed oficial de Chainlink en Base, verificado en cadena y no desactualizado.
Si no tiene feed, el caso queda registrado pero no se soporta.

| Fecha (UTC) | Red | Token (contrato) | Símbolo | ¿Feed Chainlink oficial? | Estado |
|---|---|---|---|---|---|

## Politica de precios por encima de 10.000 USD (#927 con #98)

- Antiguedad maxima: el heartbeat de CADA feed Chainlink usado (relayer/data/assets_8453.json). En precios compuestos (wstETH/ETH, weETH/ETH, etc. multiplicados por ETH/USD) se comprueba cada feed con su propio heartbeat. Sustituye al antiguo limite fijo de 1 h.
- Lista de alto valor (#927.2): USDC, USDT, DAI, EURC, WETH, wstETH, weETH, cbETH y cbBTC; el resto suma como maximo 10.000 USD.
- Ademas (#98): USDC, USDT, DAI, GHO y sUSDe se rechazan si su precio esta fuera de 0,98-1,02 USD; EURC se rechaza si se aleja mas de un 2 % del feed EUR/USD, solo si ese feed esta configurado (eur_usd_feed; hoy NO lo esta, asi que la regla de EURC no se aplica).
- La #98 solo anade condiciones: USDC, USDT y DAI siguen permitidos por encima de 10.000 USD si estan en banda (compatible con #927.2).
- Precio y antiguedad se releen en el servidor desde el oraculo; cualquier error del oraculo rechaza el rescate (fail-closed).
