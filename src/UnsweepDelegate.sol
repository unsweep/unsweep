// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {UnsweepConfig} from "./UnsweepConfig.sol";

interface IERC20Min {
    function balanceOf(address) external view returns (uint256);
    function decimals() external view returns (uint8);
}

interface IERC721Min {
    function transferFrom(address from, address to, uint256 id) external;
}

/// @title UNSWEEP M1 - delegado EIP-7702 para rescatar una EOA comprometida
/// @notice La EOA delega su codigo aqui. Cualquiera (patrocinador de gas) puede llamar rescue(),
///         pero solo con firma EIP-712 de la propia EOA. Reparto atomico: (10000-feeBps)/10000 a
///         la wallet segura y feeBps/10000 al feeRecipient inmutable. Sin custodia ni claves.
/// @dev callsHash = keccak256(abi.encode(calls)); tokensHash = keccak256(abi.encode(tokens));
///      nftsHash = keccak256(abi.encode(nfts)). Dominio: name "Unsweep", version "1",
///      chainId, verifyingContract = EOA rescatada.
contract UnsweepDelegate {
    struct Call {
        address target;
        uint256 value;
        bytes data;
    }

    struct Nft {
        address token;
        uint256 id;
    }

    struct Rescue {
        address safe;
        Call[] calls;
        address[] tokens;
        Nft[] nfts;
        uint256 nonce;
        uint256 deadline;
    }

    bytes32 public constant RESCUE_TYPEHASH = keccak256(
        "Rescue(address safe,bytes32 callsHash,bytes32 tokensHash,bytes32 nftsHash,uint256 nonce,uint256 deadline)"
    );
    bytes32 private constant DOMAIN_TYPEHASH =
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");
    bytes32 private constant NONCE_NS = keccak256("unsweep.v1.usedNonces");
    uint256 private constant HALF_N = 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0;

    UnsweepConfig public immutable config;

    event Rescued(address indexed account, address indexed safe, uint256 nonce, uint256 totalUsd8);
    event FeePaid(address indexed token, address indexed to, uint256 amount);

    error Expired();
    error BadSafe();
    error NonceUsed();
    error BadSig();
    error CallFailed(uint256 index, bytes ret);
    error Unpriced(address token);
    error OverCap(uint256 totalUsd8, uint256 capUsd8);
    error NftFeeNeedsToken();
    error NftFeeTooHigh();
    error TransferFailed(address token);

    constructor(UnsweepConfig _config) {
        config = _config;
    }

    receive() external payable {}

    function onERC721Received(address, address, uint256, bytes calldata) external pure returns (bytes4) {
        return 0x150b7a02;
    }

    function onERC1155Received(address, address, uint256, uint256, bytes calldata) external pure returns (bytes4) {
        return 0xf23a6e61;
    }

    function domainSeparator() public view returns (bytes32) {
        return keccak256(abi.encode(DOMAIN_TYPEHASH, keccak256("Unsweep"), keccak256("1"), block.chainid, address(this)));
    }

    function rescueDigest(Rescue calldata r) public view returns (bytes32) {
        bytes32 structHash = keccak256(
            abi.encode(
                RESCUE_TYPEHASH,
                r.safe,
                keccak256(abi.encode(r.calls)),
                keccak256(abi.encode(r.tokens)),
                keccak256(abi.encode(r.nfts)),
                r.nonce,
                r.deadline
            )
        );
        return keccak256(abi.encodePacked("\x19\x01", domainSeparator(), structHash));
    }

    function nonceUsed(uint256 nonce) public view returns (bool used) {
        bytes32 slot = keccak256(abi.encode(NONCE_NS, nonce));
        assembly {
            used := sload(slot)
        }
    }

    function rescue(Rescue calldata r, uint8 v, bytes32 rs, bytes32 ss) external {
        if (block.timestamp > r.deadline) revert Expired();
        if (r.safe == address(0) || r.safe == address(this)) revert BadSafe();
        if (nonceUsed(r.nonce)) revert NonceUsed();
        if (uint256(ss) > HALF_N || (v != 27 && v != 28)) revert BadSig();
        address signer = ecrecover(rescueDigest(r), v, rs, ss);
        if (signer == address(0) || signer != address(this)) revert BadSig();
        bytes32 slot = keccak256(abi.encode(NONCE_NS, r.nonce));
        assembly {
            sstore(slot, 1)
        }

        // 1) reclamos (airdrops) firmados por la victima
        for (uint256 i; i < r.calls.length; ++i) {
            (bool ok, bytes memory ret) = r.calls[i].target.call{value: r.calls[i].value}(r.calls[i].data);
            if (!ok) revert CallFailed(i, ret);
        }

        // 2) valoracion de la cesta y limite
        UnsweepConfig c = config;
        uint256 n = r.tokens.length;
        uint256[] memory bals = new uint256[](n);
        uint256[] memory units = new uint256[](n);
        uint256 total;
        for (uint256 i; i < n; ++i) {
            address t = r.tokens[i];
            for (uint256 j; j < i; ++j) {
                if (r.tokens[j] == t) revert Unpriced(t); // duplicado
            }
            uint256 p = c.tokenPriceUsd8(t);
            if (p == 0) revert Unpriced(t);
            bals[i] = IERC20Min(t).balanceOf(address(this));
            units[i] = 10 ** IERC20Min(t).decimals();
            total += bals[i] * p / units[i];
        }
        uint256 nftUsd;
        for (uint256 i; i < r.nfts.length; ++i) {
            uint256 val = c.nftValueUsd8(r.nfts[i].token);
            if (val == 0) revert Unpriced(r.nfts[i].token);
            nftUsd += val;
        }
        total += nftUsd;
        uint256 cap = c.capUsd8();
        if (total > cap) revert OverCap(total, cap);

        // 3) reparto atomico
        address feeTo = c.feeRecipient();
        uint256 bps = c.feeBps();
        uint256 nftFeeTok;
        if (nftUsd > 0) {
            if (n == 0) revert NftFeeNeedsToken();
            nftFeeTok = nftUsd * bps * units[0] / (10000 * c.tokenPriceUsd8(r.tokens[0]));
        }
        for (uint256 i; i < n; ++i) {
            uint256 fee = bals[i] * bps / 10000;
            if (i == 0 && nftFeeTok > 0) {
                if (fee + nftFeeTok > bals[0]) revert NftFeeTooHigh();
                fee += nftFeeTok;
            }
            if (fee > 0) {
                _send(r.tokens[i], feeTo, fee);
                emit FeePaid(r.tokens[i], feeTo, fee);
            }
            if (bals[i] > fee) _send(r.tokens[i], r.safe, bals[i] - fee);
        }
        for (uint256 i; i < r.nfts.length; ++i) {
            IERC721Min(r.nfts[i].token).transferFrom(address(this), r.safe, r.nfts[i].id);
        }
        emit Rescued(address(this), r.safe, r.nonce, total);
    }

    function _send(address token, address to, uint256 amt) private {
        (bool ok, bytes memory ret) = token.call(abi.encodeWithSelector(0xa9059cbb, to, amt));
        if (!ok || (ret.length > 0 && !abi.decode(ret, (bool)))) revert TransferFailed(token);
    }
}
