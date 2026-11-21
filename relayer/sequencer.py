"""Chainlink L2 Sequencer Uptime Feed (#1011/#1012). FAIL-CLOSED, solo lectura.

Antes de calcular precios y comisiones de un rescate en una L2 se comprueba el feed:
- answer == 1 -> secuenciador caido: se rechaza.
- now - startedAt < GRACE_PERIOD_S -> periodo de gracia tras volver a estar activo: se rechaza.
- cualquier error al leer el feed o el bloque, answer distinto de 0/1 o startedAt == 0: se rechaza.
La hora se toma SIEMPRE del ultimo bloque (nunca del reloj local).
Direcciones (proxy): https://docs.chain.link/data-feeds/l2-sequencer-feeds
"""
from web3 import Web3

from policy import PolicyError

FEEDS = {
    8453: '0xBCF85224fc0756B9Fa45aA7892530B47e10b6433',   # Base mainnet
    42161: '0xFdB631F5EE196F0ed6FAa767959853A9F217697D',  # Arbitrum One
}
GRACE_PERIOD_S = 3600
SEQ_ABI = [
    {'name': 'latestRoundData', 'type': 'function', 'stateMutability': 'view', 'inputs': [],
     'outputs': [{'name': 'roundId', 'type': 'uint80'}, {'name': 'answer', 'type': 'int256'},
                 {'name': 'startedAt', 'type': 'uint256'}, {'name': 'updatedAt', 'type': 'uint256'},
                 {'name': 'answeredInRound', 'type': 'uint80'}]},
]


class SequencerError(PolicyError):
    pass


def validate(answer, started_at, now, grace=GRACE_PERIOD_S):
    """Validacion pura; lanza SequencerError."""
    answer, started_at, now = int(answer), int(started_at), int(now)
    if answer == 1:
        raise SequencerError('secuenciador de la L2 caido (Chainlink Sequencer Uptime Feed): '
                             'rescates pausados, reintenta mas tarde')
    if answer != 0:
        raise SequencerError('estado del secuenciador desconocido (answer=%d): rescate rechazado' % answer)
    if started_at == 0:
        raise SequencerError('estado del secuenciador no disponible (startedAt=0): rescate rechazado')
    since = now - started_at
    if since < grace:
        raise SequencerError('secuenciador recien restablecido (%ds < %ds de gracia): rescates pausados, '
                             'reintenta mas tarde' % (max(since, 0), grace))


def check(w3, chain_id, grace=GRACE_PERIOD_S):
    """Comprueba el feed de la cadena. Sin feed configurado (L1, testnets, anvil) no aplica."""
    feed = FEEDS.get(int(chain_id))
    if feed is None:
        return None
    try:
        c = w3.eth.contract(address=Web3.to_checksum_address(feed), abi=SEQ_ABI)
        _rid, answer, started_at, _upd, _air = c.functions.latestRoundData().call()
        now = int(w3.eth.get_block('latest')['timestamp'])
    except Exception as e:
        raise SequencerError('no se pudo leer el estado del secuenciador (%s): rescate rechazado'
                             % type(e).__name__) from None
    validate(answer, started_at, now, grace)
    return {'answer': int(answer), 'startedAt': int(started_at), 'now': now}
