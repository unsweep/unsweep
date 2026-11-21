// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {UnsweepConfig} from "./UnsweepConfig.sol";
import {IERC20, SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

interface IERC20Min {
    function balanceOf(address) external view returns (uint256);
}

interface IERC721Min {
    function transferFrom(address from, address to, uint256 id) external;
    function ownerOf(uint256 id) external view returns (address);
}

/// @title UNSWEEP M1.1 - delegado EIP-7702 (sin oraculo, comision en especie, storage ERC-7201)
/// @notice Solo la EOA firma (EIP-712, dominio verifyingContract = EOA). ERC-20: feeBps de cada token en
///         especie. NFT/ENS: sin tarifa (viajan gratis con el rescate);
///         la wallet segura nunca paga nada. Nonces sin orden (bitmap, aleatorios).
/// @custom:storage-location erc7201:unsweep.storage.v1
contract UnsweepDelegate {
    using SafeERC20 for IERC20;

    /// techo inmutable del 15 %: ninguna firma ni configuracion puede superarlo
    uint16 public constant MAX_FEE_BPS = 1500;

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
        uint16 maxFeeBps;
        uint256[] minFees;
        uint256 nonce;
        uint256 deadline;
    }

    /// @custom:storage-location erc7201:unsweep.storage.v1
    struct Store {
        mapping(uint256 => uint256) nonceBitmap;
    }

    bytes32 public constant RESCUE_TYPEHASH = keccak256(
        "Rescue(address safe,bytes32 callsHash,bytes32 tokensHash,bytes32 nftsHash,uint16 maxFeeBps,bytes32 minFeesHash,uint256 nonce,uint256 deadline)"
    );
    bytes32 private constant DOMAIN_TYPEHASH =
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");
    // keccak256(abi.encode(uint256(keccak256("unsweep.storage.v1")) - 1)) & ~bytes32(uint256(0xff)); verificado en test
    bytes32 public constant STORE_SLOT = 0xc075d8c65341425dcb0b8e255f5a592d82b769884da2368a1922eb0178af1f00;
    uint256 private constant HALF_N = 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0;
    uint256 private constant LOCK_TSLOT = uint256(keccak256("unsweep.lock.v1"));

    UnsweepConfig public immutable config;

    event Rescued(address indexed account, address indexed safe, uint256 nonce, uint256 items);
    event FeePaid(address indexed token, address indexed to, uint256 amount);

    error Expired();
    error BadSafe();
    error NonceUsed();
    error BadSig();
    error Reentrant();
    error NotSelf();
    error CallFailed(uint256 index, bytes ret);
    error ForbiddenCall(uint256 index);
    error BalanceDropped(address token);
    error TransferFailed(address token);
    error NftMoved(address token, uint256 id);
    error NothingRescued();
    error BadFeeRecipient();
    error BadMinFees();
    error FeeAboveSigned(address token);
    error BadConfig();

    constructor(UnsweepConfig _config) {
        if (address(_config) == address(0)) revert BadConfig();
        config = _config;
    }

    receive() external payable {}

    function onERC721Received(address, address, uint256, bytes calldata) external pure returns (bytes4) {
        return this.onERC721Received.selector;
    }

    function _s() private pure returns (Store storage st) {
        bytes32 slot = STORE_SLOT;
        assembly { st.slot := slot }
    }

    function nonceUsed(uint256 nonce) public view returns (bool) {
        return _s().nonceBitmap[nonce >> 8] & (1 << (nonce & 0xff)) != 0;
    }

    /// la propia EOA puede invalidar un nonce enviandose una tx a si misma
    function invalidateNonce(uint256 nonce) external {
        if (msg.sender != address(this)) revert NotSelf();
        _s().nonceBitmap[nonce >> 8] |= 1 << (nonce & 0xff);
    }

    function domainSeparator() public view returns (bytes32) {
        return
            keccak256(abi.encode(DOMAIN_TYPEHASH, keccak256("Unsweep"), keccak256("1"), block.chainid, address(this)));
    }

    function rescueDigest(Rescue calldata r) public view returns (bytes32) {
        bytes32 sh = keccak256(
            abi.encode(
                RESCUE_TYPEHASH,
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
        return keccak256(abi.encodePacked("\x19\x01", domainSeparator(), sh));
    }

    function rescue(Rescue calldata r, uint8 v, bytes32 rr, bytes32 ss) external {
        uint256 lk = LOCK_TSLOT;
        uint256 locked;
        assembly { locked := tload(lk) }
        if (locked != 0) revert Reentrant();
        assembly { tstore(lk, 1) }

        if (block.timestamp > r.deadline) revert Expired();
        if (r.safe == address(0) || r.safe == address(this)) revert BadSafe();
        {
            uint256 w = r.nonce >> 8;
            uint256 bit = 1 << (r.nonce & 0xff);
            Store storage st = _s();
            if (st.nonceBitmap[w] & bit != 0) revert NonceUsed();
            st.nonceBitmap[w] |= bit;
        }
        if (uint256(ss) > HALF_N) revert BadSig();
        address signer = ecrecover(rescueDigest(r), v, rr, ss);
        if (signer == address(0) || signer != address(this)) revert BadSig();

        _runCalls(r);
        uint256 items = _sweepTokens(r);
        items += _sweepNfts(r);
        if (items == 0) revert NothingRescued();

        emit Rescued(address(this), r.safe, r.nonce, items);
        assembly { tstore(lk, 0) }
    }

    function _runCalls(Rescue calldata r) private {
        uint256 n = r.calls.length;
        if (n == 0) return;
        uint256[] memory before = new uint256[](r.tokens.length);
        for (uint256 j; j < r.tokens.length; ++j) before[j] = IERC20Min(r.tokens[j]).balanceOf(address(this));
        for (uint256 i; i < n; ++i) {
            Call calldata c = r.calls[i];
            if (c.value != 0 || !config.claimTarget(c.target) || c.target == address(this)) {
                revert ForbiddenCall(i);
            }
            for (uint256 j; j < r.tokens.length; ++j) if (c.target == r.tokens[j]) revert ForbiddenCall(i);
            for (uint256 j; j < r.nfts.length; ++j) if (c.target == r.nfts[j].token) revert ForbiddenCall(i);
            (bool ok, bytes memory ret) = c.target.call(c.data);
            if (!ok) revert CallFailed(i, ret);
        }
        // ninguna llamada de reclamo puede sacar un NFT de la cesta
        for (uint256 j; j < r.nfts.length; ++j) {
            if (IERC721Min(r.nfts[j].token).ownerOf(r.nfts[j].id) != address(this)) {
                revert NftMoved(r.nfts[j].token, r.nfts[j].id);
            }
        }
        for (uint256 j; j < r.tokens.length; ++j) {
            if (IERC20Min(r.tokens[j]).balanceOf(address(this)) < before[j]) revert BalanceDropped(r.tokens[j]);
        }
    }

    function _effBps(uint16 signed) private view returns (uint256 b) {
        b = config.feeBps();
        if (signed < b) b = signed;
        if (b > MAX_FEE_BPS) b = MAX_FEE_BPS;
    }

    function _sweepTokens(Rescue calldata r) private returns (uint256 items) {
        address feeTo = config.feeRecipient();
        if (feeTo == address(0)) revert BadFeeRecipient();
        if (r.minFees.length != 0 && r.minFees.length != r.tokens.length) revert BadMinFees();
        uint256 bps = _effBps(r.maxFeeBps);
        for (uint256 j; j < r.tokens.length; ++j) {
            IERC20 t = IERC20(r.tokens[j]);
            uint256 bal = t.balanceOf(address(this));
            if (bal == 0) continue;
            uint256 minFee = r.minFees.length == 0 ? 0 : r.minFees[j];
            uint256 fee = bal * bps / 10_000;
            if (fee < minFee) fee = minFee;
            if (fee > bal) fee = bal;
            uint256 fGot;
            if (fee != 0) {
                uint256 f0 = t.balanceOf(feeTo);
                t.safeTransfer(feeTo, fee);
                fGot = t.balanceOf(feeTo) - f0;
            }
            uint256 sGot;
            uint256 rest = t.balanceOf(address(this));
            if (rest != 0) {
                uint256 s0 = t.balanceOf(r.safe);
                t.safeTransfer(r.safe, rest);
                sGot = t.balanceOf(r.safe) - s0;
            }
            // comision sobre lo realmente transferido: nunca mas que el % firmado del total recibido (+1 redondeo),
            // salvo la tarifa minima firmada por la victima
            if (fGot > minFee && fGot * 10_000 > (fGot + sGot) * bps + 10_000) revert FeeAboveSigned(address(t));
            if (fGot != 0) emit FeePaid(address(t), feeTo, fGot);
            ++items;
        }
    }

    function _sweepNfts(Rescue calldata r) private returns (uint256) {
        uint256 n = r.nfts.length;
        for (uint256 i; i < n; ++i) IERC721Min(r.nfts[i].token).transferFrom(address(this), r.safe, r.nfts[i].id);
        return n;
    }
}
