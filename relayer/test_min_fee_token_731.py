"""#731: token del minFee en Ethereum: (a) USDC/WETH/DAI/USDT > (b) mayor valor sin FOT > (c) nunca FOT; si no, no viable."""
import pytest

import policy as P

ETH = P.ETH_MAINNET
USDC = '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
WETH = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
DAI = '0x6b175474e89094c44da98b954eedeac495271d0f'
X1 = '0x00000000000000000000000000000000000000a1'
X2 = '0x00000000000000000000000000000000000000a2'
FOT = '0x00000000000000000000000000000000000000f0'


def tk(a, usd, fot=False):
    return {'address': a, 'value_usd': usd, 'fee_on_transfer': fot}


def test_a_preferido_aunque_haya_otro_de_mas_valor():
    toks = [tk(X1, 1000), tk(USDC.upper().replace('0X', '0x'), 100)]
    assert P.pick_min_fee_token(ETH, toks, 50, 1500) == (1, 'a')


def test_a_respeta_orden_weth_antes_que_dai():
    toks = [tk(DAI, 500), tk(WETH, 400)]
    assert P.pick_min_fee_token(ETH, toks, 50, 1500) == (1, 'a')


def test_a_preferido_sin_saldo_suficiente_pasa_a_b():
    # USDC no cubre el minimo por si solo; X1 si -> regla (b)
    toks = [tk(USDC, 1), tk(X1, 200)]
    assert P.pick_min_fee_token(ETH, toks, 150, 0) == (1, 'b')


def test_b_mayor_valor_sin_fot_nunca_el_fot():
    toks = [tk(X1, 300), tk(X2, 500), tk(FOT, 5000, fot=True)]
    assert P.pick_min_fee_token(ETH, toks, 100, 1500) == (1, 'b')


def test_c_nunca_fot_ni_no_verificado():
    toks = [tk(FOT, 5000, fot=True), {'address': X1, 'value_usd': 4000}]  # X1 sin verificar
    with pytest.raises(P.NotViableOnEthereum):
        P.pick_min_fee_token(ETH, toks, 100, 1500)


def test_c_preferido_marcado_fot_se_excluye():
    toks = [tk(USDC, 1000, fot=True), tk(X1, 300)]
    assert P.pick_min_fee_token(ETH, toks, 100, 1500) == (1, 'b')


def test_no_viable_sugiere_base_o_arbitrum():
    toks = [tk(USDC, 10), tk(X1, 5)]
    with pytest.raises(P.NotViableOnEthereum) as e:
        P.pick_min_fee_token(ETH, toks, 100, 1500)
    msg = str(e.value)
    assert 'no viable en Ethereum' in msg and 'Base' in msg and 'Arbitrum' in msg
