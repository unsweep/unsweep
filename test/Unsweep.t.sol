// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {UnsweepConfig} from "../src/UnsweepConfig.sol";
import {UnsweepDelegate} from "../src/UnsweepDelegate.sol";

contract MockERC20 {
    mapping(address => uint256) public balanceOf;
    uint8 public decimals;
    constructor(uint8 d) { decimals = d; }
    function mint(address to, uint256 a) external { balanceOf[to] += a; }
    function transfer(address to, uint256 a) external returns (bool) {
        balanceOf[msg.sender] -= a; balanceOf[to] += a; return true;
    }
    /// mock deliberadamente inseguro: mueve saldo ajeno sin autorizacion (peor caso de token/claim)
    function burnFrom(address from, address to, uint256 a) external {
        balanceOf[from] -= a; balanceOf[to] += a;
    }
}

interface MockERC20Burn { function burnFrom(address, address, uint256) external; }

contract MockERC721 {
    mapping(uint256 => address) public ownerOf;
    function mint(address to, uint256 id) external { ownerOf[id] = to; }
    function transferFrom(address from, address to, uint256 id) external {
        require(ownerOf[id] == from && msg.sender == from, "nft auth");
        ownerOf[id] = to;
    }
}

contract MockAirdrop {
    MockERC20 public token;
    mapping(address => bool) public claimed;
    constructor(MockERC20 t) { token = t; }
    function claim() external {
        require(!claimed[msg.sender], "claimed");
        claimed[msg.sender] = true;
        token.mint(msg.sender, 100e6);
    }
}

contract UnsweepTest is Test {
    address constant FEE_TO = 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B;
    bytes32 constant RESCUE_TYPEHASH = keccak256(
        "Rescue(address safe,bytes32 callsHash,bytes32 tokensHash,bytes32 nftsHash,uint256 nonce,uint256 deadline)"
    );
    bytes32 constant DOMAIN_TYPEHASH =
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");

    UnsweepConfig cfg;
    UnsweepDelegate impl;
    MockERC20 usdc;
    MockERC20 junk;
    MockERC721 nft;
    MockAirdrop drop;

    uint256 victimPk = 0xA11CE;
    address victim;
    address safe = address(0x5AFE);
    address sponsor = address(0xB0B);
    address attacker = address(0xBAD);

    function setUp() public {
        victim = vm.addr(victimPk);
        cfg = new UnsweepConfig(FEE_TO, 1500, 500e8);
        impl = new UnsweepDelegate(cfg);
        usdc = new MockERC20(6);
        junk = new MockERC20(18);
        nft = new MockERC721();
        drop = new MockAirdrop(usdc);
        cfg.setTokenPrice(address(usdc), 1e8);
        cfg.setNftValue(address(nft), 100e8);
        cfg.setClaimTarget(address(drop), true);
    }

    function _empty() internal pure returns (UnsweepDelegate.Rescue memory r) {
        r.calls = new UnsweepDelegate.Call[](0);
        r.tokens = new address[](0);
        r.nfts = new UnsweepDelegate.Nft[](0);
    }

    function _base() internal view returns (UnsweepDelegate.Rescue memory r) {
        r = _empty();
        r.safe = safe;
        r.tokens = new address[](1);
        r.tokens[0] = address(usdc);
        r.nonce = 1;
        r.deadline = block.timestamp + 1 hours;
    }

    function _digest(UnsweepDelegate.Rescue memory r) internal view returns (bytes32) {
        bytes32 ds = keccak256(abi.encode(DOMAIN_TYPEHASH, keccak256("Unsweep"), keccak256("1"), block.chainid, victim));
        bytes32 sh = keccak256(abi.encode(RESCUE_TYPEHASH, r.safe, keccak256(abi.encode(r.calls)),
            keccak256(abi.encode(r.tokens)), keccak256(abi.encode(r.nfts)), r.nonce, r.deadline));
        return keccak256(abi.encodePacked("\x19\x01", ds, sh));
    }

    /// patrocinador envia UNA tx tipo 4: delegacion firmada por la victima + rescue
    function _rescue(UnsweepDelegate.Rescue memory r, uint256 signerPk) internal {
        (uint8 v, bytes32 rr, bytes32 ss) = vm.sign(signerPk, _digest(r));
        vm.signAndAttachDelegation(address(impl), victimPk);
        vm.prank(sponsor);
        UnsweepDelegate(payable(victim)).rescue(r, v, rr, ss);
    }

    function test_erc20_split_85_15() public {
        usdc.mint(victim, 400e6);
        _rescue(_base(), victimPk);
        assertEq(usdc.balanceOf(safe), 340e6);
        assertEq(usdc.balanceOf(FEE_TO), 60e6);
        assertEq(usdc.balanceOf(victim), 0);
    }

    function test_over_cap_reverts() public {
        usdc.mint(victim, 501e6);
        UnsweepDelegate.Rescue memory r = _base();
        (uint8 v, bytes32 rr, bytes32 ss) = vm.sign(victimPk, _digest(r));
        vm.signAndAttachDelegation(address(impl), victimPk);
        vm.expectRevert(abi.encodeWithSelector(UnsweepDelegate.OverCap.selector, 501e8, 500e8));
        UnsweepDelegate(payable(victim)).rescue(r, v, rr, ss);
    }

    function test_third_party_signature_rejected() public {
        usdc.mint(victim, 100e6);
        UnsweepDelegate.Rescue memory r = _base();
        r.safe = attacker;
        (uint8 v, bytes32 rr, bytes32 ss) = vm.sign(0xDEAD, _digest(r));
        vm.signAndAttachDelegation(address(impl), victimPk);
        vm.expectRevert(UnsweepDelegate.BadSig.selector);
        UnsweepDelegate(payable(victim)).rescue(r, v, rr, ss);
    }

    function test_tampered_safe_rejected() public {
        usdc.mint(victim, 100e6);
        UnsweepDelegate.Rescue memory r = _base();
        (uint8 v, bytes32 rr, bytes32 ss) = vm.sign(victimPk, _digest(r));
        r.safe = attacker; // relayer intenta desviar
        vm.signAndAttachDelegation(address(impl), victimPk);
        vm.expectRevert(UnsweepDelegate.BadSig.selector);
        UnsweepDelegate(payable(victim)).rescue(r, v, rr, ss);
    }

    function test_nonce_replay_and_expiry() public {
        usdc.mint(victim, 100e6);
        UnsweepDelegate.Rescue memory r = _base();
        _rescue(r, victimPk);
        (uint8 v, bytes32 rr, bytes32 ss) = vm.sign(victimPk, _digest(r));
        vm.expectRevert(UnsweepDelegate.NonceUsed.selector);
        UnsweepDelegate(payable(victim)).rescue(r, v, rr, ss);
        r.nonce = 2;
        r.deadline = block.timestamp - 1;
        (v, rr, ss) = vm.sign(victimPk, _digest(r));
        vm.expectRevert(UnsweepDelegate.Expired.selector);
        UnsweepDelegate(payable(victim)).rescue(r, v, rr, ss);
    }

    function test_unpriced_token_reverts() public {
        junk.mint(victim, 1e18);
        UnsweepDelegate.Rescue memory r = _base();
        r.tokens[0] = address(junk);
        (uint8 v, bytes32 rr, bytes32 ss) = vm.sign(victimPk, _digest(r));
        vm.signAndAttachDelegation(address(impl), victimPk);
        vm.expectRevert(abi.encodeWithSelector(UnsweepDelegate.Unpriced.selector, address(junk)));
        UnsweepDelegate(payable(victim)).rescue(r, v, rr, ss);
    }

    function test_airdrop_claim_plus_nft() public {
        usdc.mint(victim, 100e6);
        nft.mint(victim, 7);
        UnsweepDelegate.Rescue memory r = _base();
        r.calls = new UnsweepDelegate.Call[](1);
        r.calls[0] = UnsweepDelegate.Call(address(drop), 0, abi.encodeCall(MockAirdrop.claim, ()));
        r.nfts = new UnsweepDelegate.Nft[](1);
        r.nfts[0] = UnsweepDelegate.Nft(address(nft), 7);
        _rescue(r, victimPk);
        // cesta: 200 USDC (100 + 100 airdrop) + NFT 100 USD = 300 USD; fee 15 % = 45 USDC
        assertEq(usdc.balanceOf(FEE_TO), 45e6);
        assertEq(usdc.balanceOf(safe), 155e6);
        assertEq(nft.ownerOf(7), safe);
        assertTrue(drop.claimed(victim));
    }

    /// Sweeper: cualquier ETH que llegue a la victima lo barre el atacante antes de usarlo.
    /// Via clasica (enviar gas) pierde el ETH; via 7702 patrocinada rescata sin ETH en la victima.
    function test_sweeper_classic_fails_7702_succeeds() public {
        usdc.mint(victim, 400e6);
        vm.deal(sponsor, 1 ether);
        vm.prank(sponsor);
        (bool ok,) = victim.call{value: 0.01 ether}("");
        assertTrue(ok);
        vm.prank(victim);
        (ok,) = attacker.call{value: 0.01 ether}(""); // sweeper barre el gas
        assertTrue(ok);
        assertEq(victim.balance, 0);
        assertEq(usdc.balanceOf(victim), 400e6); // tokens siguen atrapados

        _rescue(_base(), victimPk); // tx unica patrocinada: delega + rescata
        assertEq(victim.balance, 0);
        assertEq(usdc.balanceOf(safe), 340e6);
        assertEq(usdc.balanceOf(FEE_TO), 60e6);
        assertEq(attacker.balance, 0.01 ether);
    }

    /// bypass M1 original: llamada firmada token.transfer(safe, todo) antes de valorar -> sin fee ni limite
    function test_call_to_basket_token_forbidden() public {
        usdc.mint(victim, 400e6);
        UnsweepDelegate.Rescue memory r = _base();
        r.calls = new UnsweepDelegate.Call[](1);
        r.calls[0] = UnsweepDelegate.Call(address(usdc), 0, abi.encodeCall(MockERC20.transfer, (safe, 400e6)));
        (uint8 v, bytes32 rr, bytes32 ss) = vm.sign(victimPk, _digest(r));
        vm.signAndAttachDelegation(address(impl), victimPk);
        vm.expectRevert(abi.encodeWithSelector(UnsweepDelegate.ForbiddenCall.selector, 0));
        UnsweepDelegate(payable(victim)).rescue(r, v, rr, ss);
    }

    /// llamada a un token no listado (fuera de la cesta) o con ETH: rechazada
    function test_call_unlisted_or_value_forbidden() public {
        usdc.mint(victim, 100e6);
        junk.mint(victim, 1e18);
        UnsweepDelegate.Rescue memory r = _base();
        r.calls = new UnsweepDelegate.Call[](1);
        r.calls[0] = UnsweepDelegate.Call(address(junk), 0, abi.encodeCall(MockERC20.transfer, (safe, 1e18)));
        (uint8 v, bytes32 rr, bytes32 ss) = vm.sign(victimPk, _digest(r));
        vm.signAndAttachDelegation(address(impl), victimPk);
        vm.expectRevert(abi.encodeWithSelector(UnsweepDelegate.ForbiddenCall.selector, 0));
        UnsweepDelegate(payable(victim)).rescue(r, v, rr, ss);
        r.calls[0] = UnsweepDelegate.Call(address(drop), 1, abi.encodeCall(MockAirdrop.claim, ()));
        (v, rr, ss) = vm.sign(victimPk, _digest(r));
        vm.expectRevert(abi.encodeWithSelector(UnsweepDelegate.ForbiddenCall.selector, 0));
        UnsweepDelegate(payable(victim)).rescue(r, v, rr, ss);
    }

    /// claim autorizado pero malicioso que intenta sacar saldo de la cesta: revierte por BalanceDropped
    function test_claim_target_cannot_drain_basket() public {
        usdc.mint(victim, 400e6);
        EvilClaim evil = new EvilClaim();
        cfg.setClaimTarget(address(evil), true);
        UnsweepDelegate.Rescue memory r = _base();
        r.calls = new UnsweepDelegate.Call[](1);
        r.calls[0] = UnsweepDelegate.Call(address(evil), 0, abi.encodeCall(EvilClaim.claim, (address(usdc), safe, 400e6)));
        (uint8 v, bytes32 rr, bytes32 ss) = vm.sign(victimPk, _digest(r));
        vm.signAndAttachDelegation(address(impl), victimPk);
        vm.expectRevert(abi.encodeWithSelector(UnsweepDelegate.BalanceDropped.selector, address(usdc)));
        UnsweepDelegate(payable(victim)).rescue(r, v, rr, ss);
    }

    function test_claim_target_cannot_be_priced_asset() public {
        vm.expectRevert(UnsweepConfig.BadParam.selector);
        cfg.setClaimTarget(address(usdc), true);
    }
}

/// contrato de reclamo que, via callback a la EOA delegada, no puede mover saldo: la EOA solo ejecuta
/// rescue firmado. Simulamos el peor caso: el token se mueve con transferencia del propio token (mock sin auth)
contract EvilClaim {
    function claim(address token, address to, uint256 amt) external {
        MockERC20Burn(token).burnFrom(msg.sender, to, amt);
    }
}
