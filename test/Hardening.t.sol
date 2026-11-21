// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {UnsweepBase} from "./UnsweepBase.sol";
import {UnsweepDelegate} from "../src/UnsweepDelegate.sol";
import {GarbageWriter, AttackerSweeper} from "./Mocks.sol";

/// Tests nuevos M1.1
contract HardeningTest is UnsweepBase {
    function _try(UnsweepDelegate.Rescue memory r, bytes memory err) internal {
        (uint8 v, bytes32 a, bytes32 b) = _prep(r, victimPk);
        vm.prank(sponsor);
        vm.expectRevert(err);
        UnsweepDelegate(payable(victim)).rescue(r, v, a, b);
    }

    // ---- 3) ERC-7201 + nonces bitmap: basura del atacante y nonces marcados ----
    function test_garbage_storage_and_marked_nonces_do_not_block() public {
        usdc.mint(victim, 400e6);
        GarbageWriter g = new GarbageWriter();
        bytes32 ns = impl.STORE_SLOT();
        bytes32[] memory slots = new bytes32[](6);
        slots[0] = bytes32(0);
        slots[1] = bytes32(uint256(1));
        slots[2] = ns;
        slots[3] = keccak256(abi.encode(n1 >> 8, ns)); // palabra del bitmap de n1
        slots[4] = bytes32(uint256(keccak256("unsweep.lock.v1"))); // mismo indice que el lock transitorio
        slots[5] = keccak256(abi.encode(uint256(0), ns)); // palabra 0 del bitmap (nonces 0..255)
        vm.signAndAttachDelegation(address(g), victimPk);
        vm.prank(victim);
        GarbageWriter(victim).scribble(slots, bytes32(type(uint256).max));

        // el nonce marcado por el atacante queda inutilizable...
        _try(_base(), abi.encodeWithSelector(UnsweepDelegate.NonceUsed.selector));
        assertTrue(UnsweepDelegate(payable(victim)).nonceUsed(n1)); // la basura marco n1 (leido ya con impl delegado)
        // ...pero un nonce aleatorio nuevo funciona (el atacante no puede marcar 2^256)
        UnsweepDelegate.Rescue memory r = _base();
        r.nonce = uint256(keccak256("fresh-random-nonce"));
        _rescue(r);
        assertEq(usdc.balanceOf(safe), 340e6);
        assertEq(usdc.balanceOf(feeTo), 60e6);
    }

    function test_unordered_nonces() public {
        UnsweepDelegate.Rescue memory r = _base();
        r.nonce = 999;
        usdc.mint(victim, 100e6);
        _rescue(r);
        r.nonce = 3; // menor que el anterior: valido
        usdc.mint(victim, 100e6);
        _rescue(r);
        assertTrue(UnsweepDelegate(payable(victim)).nonceUsed(999));
        assertTrue(UnsweepDelegate(payable(victim)).nonceUsed(3));
        assertFalse(UnsweepDelegate(payable(victim)).nonceUsed(4));
    }

    function test_invalidate_nonce_only_self() public {
        _prep(_base(), victimPk);
        vm.prank(attacker);
        vm.expectRevert(UnsweepDelegate.NotSelf.selector);
        UnsweepDelegate(payable(victim)).invalidateNonce(n1);
        vm.prank(victim);
        UnsweepDelegate(payable(victim)).invalidateNonce(n1);
        assertTrue(UnsweepDelegate(payable(victim)).nonceUsed(n1));
    }

    // ---- 4) rescate de valor 0 revierte ----
    function test_rescue_zero_reverts() public {
        _try(_base(), abi.encodeWithSelector(UnsweepDelegate.NothingRescued.selector));
        UnsweepDelegate.Rescue memory r = _base();
        r.tokens = new address[](0);
        _try(r, abi.encodeWithSelector(UnsweepDelegate.NothingRescued.selector));
    }

    // ---- 7) re-delegacion: la EOA estaba delegada al sweeper del atacante ----
    function test_redelegation_from_attacker_sweeper() public {
        AttackerSweeper sw = new AttackerSweeper();
        vm.signAndAttachDelegation(address(sw), victimPk);
        usdc.mint(victim, 50e6);
        AttackerSweeper(victim).sweep(usdc, attacker); // el sweeper funciona mientras esta delegado
        assertEq(usdc.balanceOf(attacker), 50e6);
        usdc.mint(victim, 400e6);
        _rescue(_base()); // nueva delegacion + rescate en la misma llamada
        assertEq(usdc.balanceOf(safe), 340e6);
        assertEq(usdc.balanceOf(victim), 0);
        bytes memory code = victim.code;
        assertEq(code.length, 23);
        address delegated;
        assembly { delegated := shr(96, mload(add(code, 35))) }
        assertEq(delegated, address(impl));
    }
}
