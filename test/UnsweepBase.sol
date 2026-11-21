// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {UnsweepConfig} from "../src/UnsweepConfig.sol";
import {UnsweepDelegate} from "../src/UnsweepDelegate.sol";
import {MockToken, MockERC721, MockAirdrop} from "./Mocks.sol";

abstract contract UnsweepBase is Test {
    UnsweepConfig cfg;
    UnsweepDelegate impl;
    MockToken usdc;
    MockToken gov;
    MockToken junk;
    MockERC721 nft;
    MockAirdrop drop;
    uint256 victimPk = 0xA11CE;
    uint256 safePk = 0x5AFE;
    uint256 attackerPk = 0xBAD;
    address victim;
    address safe;
    address attacker;
    address feeTo = address(0xFEE);
    address sponsor = address(0x5905);
    /// owner de UnsweepConfig en TODOS los despliegues: wallet fria del humano
    address constant COLD = 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B;
    uint256 n1 = uint256(keccak256("random-nonce-1"));

    function setUp() public virtual {
        victim = vm.addr(victimPk);
        safe = vm.addr(safePk);
        attacker = vm.addr(attackerPk);
        usdc = new MockToken(6);
        gov = new MockToken(18);
        junk = new MockToken(18);
        nft = new MockERC721();
        drop = new MockAirdrop(gov);
        address[] memory targets = new address[](1);
        targets[0] = address(drop);
        cfg = new UnsweepConfig(COLD, feeTo, 1500, targets);
        impl = new UnsweepDelegate(cfg);
    }

    /// alta en la allowlist firmada por el owner (wallet fria)
    function _allow(address t) internal {
        vm.prank(COLD);
        cfg.setClaimTarget(t, true);
    }

    function _base() internal view returns (UnsweepDelegate.Rescue memory r) {
        r.safe = safe;
        r.tokens = new address[](1);
        r.tokens[0] = address(usdc);
        r.nonce = n1;
        r.deadline = block.timestamp + 1 hours;
        r.maxFeeBps = 1500;
    }

    function _digest(UnsweepDelegate.Rescue memory r) internal view returns (bytes32) {
        bytes32 ds = keccak256(
            abi.encode(
                keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
                keccak256("Unsweep"),
                keccak256("1"),
                block.chainid,
                victim
            )
        );
        bytes32 sh = keccak256(
            abi.encode(
                impl.RESCUE_TYPEHASH(),
                r.safe,
                keccak256(abi.encode(r.calls)),
                keccak256(abi.encode(r.tokens)),
                keccak256(abi.encode(r.nfts)),
                r.maxFeeBps,
                keccak256(abi.encode(r.minFees)),
                r.nonce,
                r.deadline
            )
        );
        return keccak256(abi.encodePacked("\x19\x01", ds, sh));
    }

    function _prep(UnsweepDelegate.Rescue memory r, uint256 pk) internal returns (uint8 v, bytes32 a, bytes32 b) {
        (v, a, b) = vm.sign(pk, _digest(r));
        vm.signAndAttachDelegation(address(impl), victimPk);
    }

    function _rescue(UnsweepDelegate.Rescue memory r) internal {
        (uint8 v, bytes32 a, bytes32 b) = _prep(r, victimPk);
        vm.prank(sponsor);
        UnsweepDelegate(payable(victim)).rescue(r, v, a, b);
    }

    function _nftRescue(uint256 count) internal returns (UnsweepDelegate.Rescue memory r) {
        r = _base();
        r.tokens = new address[](0);
        r.nfts = new UnsweepDelegate.Nft[](count);
        for (uint256 i; i < count; ++i) {
            nft.mint(victim, 100 + i);
            r.nfts[i] = UnsweepDelegate.Nft(address(nft), 100 + i);
        }
    }
}
