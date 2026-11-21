// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {UnsweepBase} from "./UnsweepBase.sol";
import {UnsweepDelegate} from "../src/UnsweepDelegate.sol";
import {UnsweepConfig} from "../src/UnsweepConfig.sol";
import {NoBoolToken, FeeOnTransferToken, GarbageWriter} from "./Mocks.sol";

contract M4Test is UnsweepBase {
    // (1) comision <= la firmada
    function test_fee_le_signed_maxFeeBps() public {
        usdc.mint(victim, 1000e6);
        UnsweepDelegate.Rescue memory r = _base();
        r.maxFeeBps = 500;
        _rescue(r);
        assertEq(usdc.balanceOf(feeTo), 50e6);
        assertEq(usdc.balanceOf(safe), 950e6);
    }

    function test_signed_above_cap_is_capped_at_1500() public {
        usdc.mint(victim, 1000e6);
        UnsweepDelegate.Rescue memory r = _base();
        r.maxFeeBps = 9000;
        _rescue(r);
        assertEq(usdc.balanceOf(feeTo), 150e6);
        assertEq(usdc.balanceOf(safe), 850e6);
        assertEq(impl.MAX_FEE_BPS(), 1500);
    }

    function test_zero_signed_fee_bps_no_fee() public {
        usdc.mint(victim, 1000e6);
        UnsweepDelegate.Rescue memory r = _base();
        r.maxFeeBps = 0;
        _rescue(r);
        assertEq(usdc.balanceOf(feeTo), 0);
        assertEq(usdc.balanceOf(safe), 1000e6);
    }

    // (2) USDT sin bool
    function test_usdt_no_bool() public {
        NoBoolToken t = new NoBoolToken();
        t.mint(victim, 1000e6);
        UnsweepDelegate.Rescue memory r = _base();
        r.tokens[0] = address(t);
        _rescue(r);
        assertEq(t.balanceOf(feeTo), 150e6);
        assertEq(t.balanceOf(safe), 850e6);
        assertEq(t.balanceOf(victim), 0);
    }

    // (3) token con comision al transferir: la comision de UNSWEEP nunca supera el % firmado de lo realmente recibido
    function test_fee_on_transfer_token() public {
        FeeOnTransferToken t = new FeeOnTransferToken();
        t.mint(victim, 1000e18);
        UnsweepDelegate.Rescue memory r = _base();
        r.tokens[0] = address(t);
        _rescue(r);
        uint256 f = t.balanceOf(feeTo);
        uint256 s = t.balanceOf(safe);
        assertGt(s, 0);
        assertLe(f * 10_000, (f + s) * 1500);
        assertEq(t.balanceOf(victim), 0);
    }

    // (4) minFeeAmount > porcentaje (Ethereum)
    function test_min_fee_above_percentage() public {
        usdc.mint(victim, 400e6);
        UnsweepDelegate.Rescue memory r = _base();
        r.minFees = new uint256[](1);
        r.minFees[0] = 100e6; // 15 % = 60e6 < 100e6
        _rescue(r);
        assertEq(usdc.balanceOf(feeTo), 100e6);
        assertEq(usdc.balanceOf(safe), 300e6);
    }

    function test_min_fees_length_mismatch_reverts() public {
        usdc.mint(victim, 400e6);
        UnsweepDelegate.Rescue memory r = _base();
        r.minFees = new uint256[](2);
        (uint8 v, bytes32 a, bytes32 b) = _prep(r, victimPk);
        vm.prank(sponsor);
        vm.expectRevert(UnsweepDelegate.BadMinFees.selector);
        UnsweepDelegate(payable(victim)).rescue(r, v, a, b);
    }

    // (5) firma de Base rechazada en Arbitrum y Ethereum con la misma direccion CREATE2
    function test_base_signature_rejected_on_other_chains_same_create2() public {
        bytes32 salt = keccak256("unsweep.v1");
        UnsweepDelegate d = new UnsweepDelegate{salt: salt}(cfg);
        impl = d; // misma direccion de implementacion en las 3 cadenas
        usdc.mint(victim, 400e6);
        UnsweepDelegate.Rescue memory r = _base();
        vm.chainId(8453);
        (uint8 v, bytes32 a, bytes32 b) = vm.sign(victimPk, _digest(r));
        uint64[2] memory others = [uint64(42161), uint64(1)];
        for (uint256 i; i < 2; ++i) {
            vm.chainId(others[i]);
            vm.signAndAttachDelegation(address(d), victimPk);
            vm.prank(sponsor);
            vm.expectRevert(UnsweepDelegate.BadSig.selector);
            UnsweepDelegate(payable(victim)).rescue(r, v, a, b);
        }
        vm.chainId(8453);
        vm.signAndAttachDelegation(address(d), victimPk);
        vm.prank(sponsor);
        UnsweepDelegate(payable(victim)).rescue(r, v, a, b);
        assertEq(usdc.balanceOf(safe), 340e6);
    }

    // (6) re-delegacion con almacenamiento ensuciado y parametros nuevos
    function test_redelegation_garbage_storage_new_params() public {
        GarbageWriter g = new GarbageWriter();
        vm.signAndAttachDelegation(address(g), victimPk);
        bytes32[] memory slots = new bytes32[](4);
        slots[0] = bytes32(0);
        slots[1] = bytes32(uint256(1));
        slots[2] = keccak256("unsweep.store");
        slots[3] = bytes32(uint256(keccak256("unsweep.store")) - 1);
        GarbageWriter(victim).scribble(slots, bytes32(type(uint256).max));
        usdc.mint(victim, 1000e6);
        UnsweepDelegate.Rescue memory r = _base();
        r.maxFeeBps = 1000;
        r.minFees = new uint256[](1);
        r.minFees[0] = 1e6;
        _rescue(r);
        assertEq(usdc.balanceOf(feeTo), 100e6);
        assertEq(usdc.balanceOf(safe), 900e6);
    }

    // (7) guardias de address(0)
    function test_zero_safe_reverts() public {
        usdc.mint(victim, 400e6);
        UnsweepDelegate.Rescue memory r = _base();
        r.safe = address(0);
        (uint8 v, bytes32 a, bytes32 b) = _prep(r, victimPk);
        vm.prank(sponsor);
        vm.expectRevert(UnsweepDelegate.BadSafe.selector);
        UnsweepDelegate(payable(victim)).rescue(r, v, a, b);
    }

    function test_config_zero_fee_recipient_reverts() public {
        vm.expectRevert(UnsweepConfig.BadParam.selector);
        new UnsweepConfig(COLD, address(0), 1500, new address[](0));
    }

    function test_config_zero_owner_reverts() public {
        vm.expectRevert(UnsweepConfig.BadParam.selector);
        new UnsweepConfig(address(0), feeTo, 1500, new address[](0));
    }

    function test_delegate_zero_config_reverts() public {
        vm.expectRevert(UnsweepDelegate.BadConfig.selector);
        new UnsweepDelegate(UnsweepConfig(address(0)));
    }
}
