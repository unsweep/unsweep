"""ORDEN #2236 fase A: OP Mainnet (chainId 10), SOLO diagnostico read-only.

El rescate en OP queda DESHABILITADO por bandera mientras no exista UnsweepDelegate
desplegado y verificado en OP (NO_DISPONIBLE). relayer.ACTIVE_MAINNETS y policy.MAINNETS
no incluyen 10, asi que cualquier intento de firma/envio en OP sigue rechazado.
Fase B: assets_10.json con 8 tokens y feeds Chainlink verificados por eth_call (tools/gen_assets_10.py).
UnsweepDelegate 0x38bcF425... tiene 0 bytes en OP: rescate NO_DISPONIBLE (ver docs/OP_MAINNET_PLAN.md).
Actualizacion #159-A/#162-A/#163-A: UnsweepDelegate desplegado en OP; RESCUE_ENABLED=True y 10 en
relayer.ACTIVE_MAINNETS y policy.MAINNETS (lo anterior sobre NO_DISPONIBLE queda como historia).
"""
import os

CHAIN_ID = 10
CHAIN_HEX = '0xa'
NAME = 'optimism'
RPC_ENV = 'OP_RPC_URL'  # solo el nombre; el valor nunca se registra
EXPLORER = 'https://optimistic.etherscan.io/address/'
EXPLORER_TX = 'https://optimistic.etherscan.io/tx/'
UNSWEEP_DELEGATE = '0x38bcF425bC4d13624734e09376F2fafc799fA8c8'  # #159-A desplegado en OP; #162-A activado
RESCUE_ENABLED = True    # #162-A; bandera dura, no se activa por variable de entorno


def rpc_configured() -> bool:
    v = os.environ.get(RPC_ENV, '').strip().strip(chr(34)).strip(chr(39))
    return bool(v)


def rescue_enabled() -> bool:
    """True solo si la bandera esta activa Y hay delegate verificado (#162-A: activo)."""
    return bool(RESCUE_ENABLED and UNSWEEP_DELEGATE)
