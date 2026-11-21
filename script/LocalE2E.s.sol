// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {UnsweepConfig} from "../src/UnsweepConfig.sol";
import {UnsweepDelegate} from "../src/UnsweepDelegate.sol";

contract E2EToken {
    mapping(address => uint256) public balanceOf;
    uint8 public constant decimals = 6;

    function mint(address to, uint256 a) external {
        balanceOf[to] += a;
    }

    function transfer(address to, uint256 a) external returns (bool) {
        balanceOf[msg.sender] -= a;
        balanceOf[to] += a;
        return true;
    }
}

/// SOLO red local (anvil --hardfork prague). Claves de prueba.
contract LocalE2E is Script {
    address constant FEE_TO = 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B;
    bytes32 constant RESCUE_TYPEHASH = keccak256(
        "Rescue(address safe,bytes32 callsHash,bytes32 tokensHash,bytes32 nftsHash,uint256 maxNftFee,uint256 nonce,uint256 deadline)"
    );
    bytes32 constant DOMAIN_TYPEHASH =
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");

    function setupLocal() external {
        uint256 sponsorPk = vm.envUint("SPONSOR_PK");
        address victim = vm.addr(vm.envUint("VICTIM_PK"));
        vm.startBroadcast(sponsorPk);
        E2EToken usdc = new E2EToken();
        UnsweepConfig cfg = new UnsweepConfig(FEE_TO, 1500, address(usdc), 5e6);
        UnsweepDelegate impl = new UnsweepDelegate(cfg);
        usdc.mint(victim, 400e6);
        vm.stopBroadcast();
        console.log("CFG", address(cfg));
        console.log("IMPL", address(impl));
        console.log("USDC", address(usdc));
    }

    function rescueLocal() external {
        uint256 sponsorPk = vm.envUint("SPONSOR_PK");
        uint256 victimPk = vm.envUint("VICTIM_PK");
        address victim = vm.addr(victimPk);
        address impl = vm.envAddress("IMPL");
        address usdc = vm.envAddress("USDC");

        UnsweepDelegate.Rescue memory r;
        r.safe = vm.envAddress("SAFE");
        r.calls = new UnsweepDelegate.Call[](0);
        r.tokens = new address[](1);
        r.tokens[0] = usdc;
        r.nfts = new UnsweepDelegate.Nft[](0);
        r.maxNftFee = 0;
        r.nonce = uint256(keccak256(abi.encode("e2e", block.timestamp)));
        r.deadline = block.timestamp + 1 hours;

        bytes32 ds = keccak256(abi.encode(DOMAIN_TYPEHASH, keccak256("Unsweep"), keccak256("1"), block.chainid, victim));
        bytes32 sh = keccak256(
            abi.encode(
                RESCUE_TYPEHASH,
                r.safe,
                keccak256(abi.encode(r.calls)),
                keccak256(abi.encode(r.tokens)),
                keccak256(abi.encode(r.nfts)),
                r.maxNftFee,
                r.nonce,
                r.deadline
            )
        );
        (uint8 v, bytes32 rr, bytes32 ss) = vm.sign(victimPk, keccak256(abi.encodePacked("\x19\x01", ds, sh)));

        vm.startBroadcast(sponsorPk);
        vm.signAndAttachDelegation(impl, victimPk);
        UnsweepDelegate.Permit memory p;
        UnsweepDelegate(payable(victim)).rescue(r, p, v, rr, ss);
        vm.stopBroadcast();
    }
}
