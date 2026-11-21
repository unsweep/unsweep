// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {UnsweepBase} from "./UnsweepBase.sol";
import {UnsweepDelegate} from "../src/UnsweepDelegate.sol";
import {UnsweepConfig} from "../src/UnsweepConfig.sol";
import {NftGrabClaim} from "./Mocks.sol";

/// Ordenes #718/#719: owner frio, sin tarifa NFT, NFTs de la cesta protegidos frente a claim targets
contract M4cTest is UnsweepBase {
    function test_owner_is_cold_wallet() public {
        assertEq(cfg.owner(), COLD);
        // quien despliega nunca es owner, aunque sea otra cuenta
        vm.prank(attacker);
        UnsweepConfig c2 = new UnsweepConfig(COLD, feeTo, 1500, new address[](0));
        assertEq(c2.owner(), COLD);
        assertTrue(c2.owner() != attacker);
        assertTrue(cfg.claimTarget(address(drop))); // allowlist inicial via constructor
    }

    function test_owner_transfer_is_two_step() public {
        vm.prank(COLD);
        cfg.transferOwnership(attacker);
        assertEq(cfg.owner(), COLD); // nada cambia hasta aceptar
        vm.prank(sponsor);
        vm.expectRevert(UnsweepConfig.NotPendingOwner.selector);
        cfg.acceptOwnership();
        vm.prank(attacker);
        cfg.acceptOwnership();
        assertEq(cfg.owner(), attacker);
    }

    function test_third_party_cannot_set_allowlist() public {
        vm.prank(attacker);
        vm.expectRevert(UnsweepConfig.NotOwner.selector);
        cfg.setClaimTarget(attacker, true);
        // ni siquiera quien desplego el contrato
        vm.expectRevert(UnsweepConfig.NotOwner.selector);
        cfg.setClaimTarget(attacker, true);
        vm.prank(attacker);
        vm.expectRevert(UnsweepConfig.NotOwner.selector);
        cfg.transferOwnership(attacker);
        assertFalse(cfg.claimTarget(attacker));
    }

    function test_safe_wallet_never_debited() public {
        usdc.mint(safe, 50e6);
        usdc.mint(victim, 100e6);
        UnsweepDelegate.Rescue memory r = _nftRescue(1);
        r.tokens = new address[](1);
        r.tokens[0] = address(usdc);
        _rescue(r);
        assertEq(usdc.balanceOf(safe), 50e6 + 85e6); // saldo previo intacto + rescate neto
        assertEq(usdc.balanceOf(feeTo), 15e6);
        assertEq(nft.ownerOf(100), safe);
    }

    function test_nft_rides_free_with_erc20() public {
        usdc.mint(victim, 100e6);
        UnsweepDelegate.Rescue memory r = _nftRescue(2);
        r.tokens = new address[](1);
        r.tokens[0] = address(usdc);
        _rescue(r);
        assertEq(nft.ownerOf(100), safe);
        assertEq(nft.ownerOf(101), safe);
        assertEq(usdc.balanceOf(feeTo), 15e6); // solo el % del ERC-20, nada por los NFTs
        assertEq(usdc.balanceOf(safe), 85e6);
    }

    function test_claim_target_cannot_move_basket_nft() public {
        NftGrabClaim grab = new NftGrabClaim();
        _allow(address(grab));
        usdc.mint(victim, 100e6);
        UnsweepDelegate.Rescue memory r = _nftRescue(1);
        r.tokens = new address[](1);
        r.tokens[0] = address(usdc);
        vm.prank(victim);
        nft.setApprovalForAll(address(grab), true); // aprobacion dejada por la clave comprometida
        r.calls = new UnsweepDelegate.Call[](1);
        r.calls[0] = UnsweepDelegate.Call(address(grab), 0, abi.encodeCall(NftGrabClaim.claim, (nft, 100, attacker)));
        (uint8 v, bytes32 a, bytes32 b) = _prep(r, victimPk);
        vm.prank(sponsor);
        vm.expectRevert(abi.encodeWithSelector(UnsweepDelegate.NftMoved.selector, address(nft), uint256(100)));
        UnsweepDelegate(payable(victim)).rescue(r, v, a, b);
        assertEq(nft.ownerOf(100), victim);
        assertEq(usdc.balanceOf(victim), 100e6);
    }
}
