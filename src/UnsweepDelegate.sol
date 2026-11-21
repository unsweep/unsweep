// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {UnsweepConfig} from "./UnsweepConfig.sol";

interface IERC20Min {
    function balanceOf(address) external view returns (uint256);
}

interface IERC2612Min {
    function permit(address owner, address spender, uint256 value, uint256 deadline, uint8 v, bytes32 r, bytes32 s) external;
}

interface IERC721Min {
    function transferFrom(address from, address to, uint256 id) external;
}

/// @title UNSWEEP M1.1 - delegado EIP-7702 (sin oraculo, comision en especie, storage ERC-7201)
/// @notice Solo la EOA firma (EIP-712, dominio verifyingContract = EOA). ERC-20: feeBps de cada token en
///         especie. NFT/ENS: tarifa fija en nftFeeToken pagada por la wallet segura via permit EIP-2612 en la
///         misma tx; si el permit o el cobro fallan, revierte todo. Nonces sin orden (bitmap, aleatorios).
/// @custom:storage-location erc7201:unsweep.storage.v1
contract UnsweepDelegate {
    struct Call { address target; uint256 value; bytes data; }
    struct Nft { address token; uint256 id; }
    struct Rescue {
        address safe;
        Call[] calls;
        address[] tokens;
        Nft[] nfts;
        uint256 maxNftFee;
        uint256 nonce;
        uint256 deadline;
    }
    struct Permit { uint256 value; uint256 deadline; uint8 v; bytes32 r; bytes32 s; }

    /// @custom:storage-location erc7201:unsweep.storage.v1
    struct Store { mapping(uint256 => uint256) nonceBitmap; }

    bytes32 public constant RESCUE_TYPEHASH = keccak256(
        "Rescue(address safe,bytes32 callsHash,bytes32 tokensHash,bytes32 nftsHash,uint256 maxNftFee,uint256 nonce,uint256 deadline)"
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
    error NftFeeTooHigh();
    error NftFeeFailed();
    error NothingRescued();

    constructor(UnsweepConfig _config) { config = _config; }

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
        return keccak256(abi.encode(DOMAIN_TYPEHASH, keccak256("Unsweep"), keccak256("1"), block.chainid, address(this)));
    }

    function rescueDigest(Rescue calldata r) public view returns (bytes32) {
        bytes32 sh = keccak256(abi.encode(RESCUE_TYPEHASH, r.safe, keccak256(abi.encode(r.calls)),
            keccak256(abi.encode(r.tokens)), keccak256(abi.encode(r.nfts)), r.maxNftFee, r.nonce, r.deadline));
        return keccak256(abi.encodePacked("\x19\x01", domainSeparator(), sh));
    }

    function rescue(Rescue calldata r, Permit calldata p, uint8 v, bytes32 rr, bytes32 ss) external {
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

        // la tarifa NFT se cobra ANTES de mover nada: la wallet segura paga con saldo propio previo
        _collectNftFee(r, p);
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
        address feeTok = config.nftFeeToken();
        uint256[] memory before = new uint256[](r.tokens.length);
        for (uint256 j; j < r.tokens.length; ++j) before[j] = IERC20Min(r.tokens[j]).balanceOf(address(this));
        for (uint256 i; i < n; ++i) {
            Call calldata c = r.calls[i];
            if (c.value != 0 || !config.claimTarget(c.target) || c.target == feeTok || c.target == address(this)) {
                revert ForbiddenCall(i);
            }
            for (uint256 j; j < r.tokens.length; ++j) if (c.target == r.tokens[j]) revert ForbiddenCall(i);
            for (uint256 j; j < r.nfts.length; ++j) if (c.target == r.nfts[j].token) revert ForbiddenCall(i);
            (bool ok, bytes memory ret) = c.target.call(c.data);
            if (!ok) revert CallFailed(i, ret);
        }
        for (uint256 j; j < r.tokens.length; ++j) {
            if (IERC20Min(r.tokens[j]).balanceOf(address(this)) < before[j]) revert BalanceDropped(r.tokens[j]);
        }
    }

    function _sweepTokens(Rescue calldata r) private returns (uint256 items) {
        address feeTo = config.feeRecipient();
        uint256 bps = config.feeBps();
        for (uint256 j; j < r.tokens.length; ++j) {
            address t = r.tokens[j];
            uint256 bal = IERC20Min(t).balanceOf(address(this));
            if (bal == 0) continue;
            uint256 fee = bal * bps / 10_000;
            if (fee != 0) {
                _transfer(t, feeTo, fee);
                emit FeePaid(t, feeTo, fee);
            }
            _transfer(t, r.safe, bal - fee);
            ++items;
        }
    }

    function _collectNftFee(Rescue calldata r, Permit calldata p) private {
        uint256 n = r.nfts.length;
        if (n == 0) return;
        uint256 fee = config.nftFlatFee() * n;
        if (fee > r.maxNftFee) revert NftFeeTooHigh();
        if (fee == 0) return;
        address ft = config.nftFeeToken();
        address feeTo = config.feeRecipient();
        // el permit lo firma la WALLET SEGURA; spender = esta EOA delegada. Sin try/catch: si falla, revierte todo.
        IERC2612Min(ft).permit(r.safe, address(this), p.value, p.deadline, p.v, p.r, p.s);
        (bool ok, bytes memory ret) = ft.call(abi.encodeWithSelector(0x23b872dd, r.safe, feeTo, fee));
        if (!ok || (ret.length != 0 && !abi.decode(ret, (bool)))) revert NftFeeFailed();
        emit FeePaid(ft, feeTo, fee);
    }

    function _sweepNfts(Rescue calldata r) private returns (uint256) {
        uint256 n = r.nfts.length;
        for (uint256 i; i < n; ++i) IERC721Min(r.nfts[i].token).transferFrom(address(this), r.safe, r.nfts[i].id);
        return n;
    }

    function _transfer(address t, address to, uint256 a) private {
        (bool ok, bytes memory ret) = t.call(abi.encodeWithSelector(0xa9059cbb, to, a));
        if (!ok || (ret.length != 0 && !abi.decode(ret, (bool)))) revert TransferFailed(t);
    }
}
