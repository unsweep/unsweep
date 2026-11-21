// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {UnsweepBase} from "./UnsweepBase.sol";
import {UnsweepConfig} from "../src/UnsweepConfig.sol";
import {UnsweepDelegate} from "../src/UnsweepDelegate.sol";
import {MockAirdrop, EvilClaim, DrainClaim} from "./Mocks.sol";

/// Tests M1 adaptados a M1.1 (sin oraculo, sin cap on-chain, comision en especie)
contract UnsweepTest is UnsweepBase {
    function _expectRescueRevert(UnsweepDelegate.Rescue memory r, uint256 pk, bytes memory err) internal {
        (uint8 v, bytes32 a, bytes32 b) = _prep(r, pk);
        vm.prank(sponsor);
        vm.expectRevert(err);
        UnsweepDelegate(payable(victim)).rescue(r, v, a, b);
    }

    function test_erc20_split_85_15() public {
        usdc.mint(victim, 400e6);
        _rescue(_base());
        assertEq(usdc.balanceOf(safe), 340e6);
        assertEq(usdc.balanceOf(feeTo), 60e6);
        assertEq(usdc.balanceOf(victim), 0);
    }

    /// antes test_over_cap_reverts: el limite de beta (500 USD) vive en el relayer, no en cadena
    function test_no_onchain_cap() public {
        usdc.mint(victim, 10_000e6);
        _rescue(_base());
        assertEq(usdc.balanceOf(safe), 8_500e6);
        assertEq(usdc.balanceOf(feeTo), 1_500e6);
    }

    /// antes test_unpriced_token_reverts: cualquier ERC-20 paga 15 % en especie, sin lista de precios
    function test_fee_in_kind_any_token() public {
        junk.mint(victim, 1000e18);
        UnsweepDelegate.Rescue memory r = _base();
        r.tokens[0] = address(junk);
        _rescue(r);
        assertEq(junk.balanceOf(safe), 850e18);
        assertEq(junk.balanceOf(feeTo), 150e18);
    }

    function test_third_party_signature_rejected() public {
        usdc.mint(victim, 100e6);
        _expectRescueRevert(_base(), attackerPk, abi.encodeWithSelector(UnsweepDelegate.BadSig.selector));
    }

    function test_tampered_safe_rejected() public {
        usdc.mint(victim, 100e6);
        UnsweepDelegate.Rescue memory r = _base();
        (uint8 v, bytes32 a, bytes32 b) = _prep(r, victimPk);
        r.safe = attacker;
        vm.prank(sponsor);
        vm.expectRevert(UnsweepDelegate.BadSig.selector);
        UnsweepDelegate(payable(victim)).rescue(r, v, a, b);
    }

    function test_nonce_replay_and_expiry() public {
        usdc.mint(victim, 100e6);
        UnsweepDelegate.Rescue memory r = _base();
        (uint8 v, bytes32 a, bytes32 b) = _prep(r, victimPk);
        vm.prank(sponsor);
        UnsweepDelegate(payable(victim)).rescue(r, v, a, b);
        usdc.mint(victim, 100e6);
        vm.prank(sponsor);
        vm.expectRevert(UnsweepDelegate.NonceUsed.selector);
        UnsweepDelegate(payable(victim)).rescue(r, v, a, b);
        UnsweepDelegate.Rescue memory r2 = _base();
        r2.nonce = n1 + 7;
        r2.deadline = block.timestamp + 10;
        vm.warp(block.timestamp + 11);
        _expectRescueRevert(r2, victimPk, abi.encodeWithSelector(UnsweepDelegate.Expired.selector));
    }

    function test_airdrop_claim_plus_nft() public {
        UnsweepDelegate.Rescue memory r = _nftRescue(1);
        r.tokens = new address[](1);
        r.tokens[0] = address(gov);
        r.calls = new UnsweepDelegate.Call[](1);
        r.calls[0] = UnsweepDelegate.Call(address(drop), 0, abi.encodeCall(MockAirdrop.claim, ()));
        _rescue(r);
        assertEq(gov.balanceOf(safe), 850e18);
        assertEq(gov.balanceOf(feeTo), 150e18);
        assertEq(nft.ownerOf(100), safe);
        assertEq(nft.ownerOf(100), safe); // NFT viaja gratis: sin tarifa NFT
        assertEq(usdc.balanceOf(safe), 0);
    }

    /// el sweeper roba el ETH de gas enviado a la victima; el rescate 7702 no necesita ETH en la victima
    function test_sweeper_classic_fails_7702_succeeds() public {
        usdc.mint(victim, 400e6);
        vm.deal(victim, 0.01 ether);
        vm.prank(victim);
        (bool ok,) = attacker.call{value: 0.01 ether}("");
        assertTrue(ok);
        assertEq(victim.balance, 0);
        _rescue(_base());
        assertEq(usdc.balanceOf(safe), 340e6);
    }

    function test_call_to_basket_token_forbidden() public {
        _allow(address(gov));
        gov.mint(victim, 1e18);
        UnsweepDelegate.Rescue memory r = _base();
        r.tokens[0] = address(gov);
        r.calls = new UnsweepDelegate.Call[](1);
        r.calls[0] = UnsweepDelegate.Call(address(gov), 0, "");
        _expectRescueRevert(r, victimPk, abi.encodeWithSelector(UnsweepDelegate.ForbiddenCall.selector, 0));
    }

    function test_call_unlisted_or_value_forbidden() public {
        usdc.mint(victim, 100e6);
        UnsweepDelegate.Rescue memory r = _base();
        r.calls = new UnsweepDelegate.Call[](1);
        r.calls[0] = UnsweepDelegate.Call(address(junk), 0, "");
        _expectRescueRevert(r, victimPk, abi.encodeWithSelector(UnsweepDelegate.ForbiddenCall.selector, 0));
        r.calls[0] = UnsweepDelegate.Call(address(drop), 1, abi.encodeCall(MockAirdrop.claim, ()));
        _expectRescueRevert(r, victimPk, abi.encodeWithSelector(UnsweepDelegate.ForbiddenCall.selector, 0));
    }

    function test_claim_target_cannot_drain_basket() public {
        DrainClaim dc = new DrainClaim();
        _allow(address(dc));
        usdc.mint(victim, 100e6);
        vm.prank(victim);
        usdc.approve(address(dc), type(uint256).max);
        UnsweepDelegate.Rescue memory r = _base();
        r.calls = new UnsweepDelegate.Call[](1);
        r.calls[0] = UnsweepDelegate.Call(address(dc), 0, abi.encodeCall(DrainClaim.claim, (usdc, attacker)));
        _expectRescueRevert(r, victimPk, abi.encodeWithSelector(UnsweepDelegate.BalanceDropped.selector, address(usdc)));
    }

    /// antes test_claim_target_cannot_be_priced_asset

    function test_reentrancy_blocked() public {
        EvilClaim ev = new EvilClaim();
        _allow(address(ev));
        usdc.mint(victim, 100e6);
        UnsweepDelegate.Rescue memory r = _base();
        r.calls = new UnsweepDelegate.Call[](1);
        r.calls[0] = UnsweepDelegate.Call(address(ev), 0, abi.encodeCall(EvilClaim.claim, ()));
        _expectRescueRevert(
            r,
            victimPk,
            abi.encodeWithSelector(
                UnsweepDelegate.CallFailed.selector, 0, abi.encodeWithSelector(UnsweepDelegate.Reentrant.selector)
            )
        );
    }
}
