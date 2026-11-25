"""ORDEN #2236 fase A: OP Mainnet (chainId 10), SOLO diagnostico read-only.

El rescate en OP queda DESHABILITADO por bandera mientras no exista UnsweepDelegate
desplegado y verificado en OP (NO_DISPONIBLE). relayer.ACTIVE_MAINNETS y policy.MAINNETS
no incluyen 10, asi que cualquier intento de firma/envio en OP sigue rechazado.
Assets y oraculos de OP: NO_DISPONIBLE (no hay assets_10.json; ver docs/OP_MAINNET_PLAN.md).
"""
import os

CHAIN_ID = 10
CHAIN_HEX = '0xa'
NAME = 'optimism'
RPC_ENV = 'OP_RPC_URL'  # solo el nombre; el valor nunca se registra
EXPLORER = 'https://optimistic.etherscan.io/address/'
EXPLORER_TX = 'https://optimistic.etherscan.io/tx/'
UNSWEEP_DELEGATE = None  # NO_DISPONIBLE: sin despliegue verificado en OP
RESCUE_ENABLED = False   # bandera dura; no se activa por variable de entorno


def rpc_configured() -> bool:
    v = os.environ.get(RPC_ENV, '').strip().strip(chr(34)).strip(chr(39))
    return bool(v)


def rescue_enabled() -> bool:
    """True solo si la bandera esta activa Y hay delegate verificado. Hoy: siempre False."""
    return bool(RESCUE_ENABLED and UNSWEEP_DELEGATE)
