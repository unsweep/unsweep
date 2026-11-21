// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {UnsweepDelegate} from "../src/UnsweepDelegate.sol";

/// ERC-20 con permit EIP-2612 (USDC y token generico)
contract MockToken {
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    mapping(address => uint256) public nonces;
    uint8 public decimals;
    bytes32 public DOMAIN_SEPARATOR;
    bytes32 public constant PERMIT_TYPEHASH =
        keccak256("Permit(address owner,address spender,uint256 value,uint256 nonce,uint256 deadline)");

    constructor(uint8 d) {
        decimals = d;
        DOMAIN_SEPARATOR = keccak256(
            abi.encode(
                keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
                keccak256("Mock"),
                keccak256("2"),
                block.chainid,
                address(this)
            )
        );
    }

    function mint(address to, uint256 a) external {
        balanceOf[to] += a;
    }

    function transfer(address to, uint256 a) external returns (bool) {
        balanceOf[msg.sender] -= a;
        balanceOf[to] += a;
        return true;
    }

    function approve(address sp, uint256 a) external returns (bool) {
        allowance[msg.sender][sp] = a;
        return true;
    }

    function transferFrom(address f, address to, uint256 a) external returns (bool) {
        uint256 al = allowance[f][msg.sender];
        if (al != type(uint256).max) allowance[f][msg.sender] = al - a;
        balanceOf[f] -= a;
        balanceOf[to] += a;
        return true;
    }

    function permit(address o, address s, uint256 v, uint256 dl, uint8 pv, bytes32 pr, bytes32 ps) external {
        require(block.timestamp <= dl, "permit expired");
        bytes32 d = keccak256(
            abi.encodePacked(
                "\x19\x01", DOMAIN_SEPARATOR, keccak256(abi.encode(PERMIT_TYPEHASH, o, s, v, nonces[o]++, dl))
            )
        );
        address rec = ecrecover(d, pv, pr, ps);
        require(rec != address(0) && rec == o, "bad permit");
        allowance[o][s] = v;
    }
}

contract MockERC721 {
    mapping(uint256 => address) public ownerOf;

    function mint(address to, uint256 id) external {
        ownerOf[id] = to;
    }

    function transferFrom(address f, address to, uint256 id) external {
        require(ownerOf[id] == f && msg.sender == f, "nft auth");
        ownerOf[id] = to;
    }
}

contract MockAirdrop {
    MockToken public immutable gov;

    constructor(MockToken g) {
        gov = g;
    }

    function claim() external {
        gov.mint(msg.sender, 1000e18);
    }
}

/// claim target malicioso: intenta reentrar en rescue()
contract EvilClaim {
    function claim() external {
        UnsweepDelegate.Rescue memory r;
        UnsweepDelegate.Permit memory p;
        UnsweepDelegate(payable(msg.sender)).rescue(r, p, 0, bytes32(0), bytes32(0));
    }
}

/// claim target que intenta vaciar un token de la cesta
contract DrainClaim {
    function claim(MockToken t, address to) external {
        t.transferFrom(msg.sender, to, t.balanceOf(msg.sender));
    }
}

/// codigo que el atacante delego antes en la EOA: escribe basura en slots arbitrarios
contract GarbageWriter {
    function scribble(bytes32[] calldata slots, bytes32 val) external {
        for (uint256 i; i < slots.length; ++i) {
            bytes32 s = slots[i];
            assembly { sstore(s, val) }
        }
    }
}

/// sweeper del atacante delegado en la EOA
contract AttackerSweeper {
    function sweep(MockToken t, address to) external {
        t.transfer(to, t.balanceOf(address(this)));
    }
}
