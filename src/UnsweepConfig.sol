// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title UNSWEEP M1.1 - configuracion on-chain minima (sin oraculo, sin precios, sin limite en USD)
/// @notice La comision ERC-20 se cobra en especie (feeBps de cada token rescatado). El limite de beta
///         (500 USD por defecto) y el filtro "comision >= gas x3" viven en el relayer, fuera de cadena.
///         NFTs/ENS (ERC-721): tarifa fija por item en nftFeeToken (USDC con EIP-2612) pagada por la
///         WALLET SEGURA via permit dentro de la misma transaccion.
contract UnsweepConfig {
    address public owner;
    address public immutable feeRecipient;
    uint16 public immutable feeBps; // 1500 = 15 %
    address public immutable nftFeeToken; // USDC (EIP-2612)
    uint256 public nftFlatFee; // unidades de nftFeeToken por NFT/ENS; la victima firma un maximo
    mapping(address => bool) public claimTarget; // contratos de reclamo (airdrop) permitidos en r.calls

    event OwnerChanged(address indexed owner);
    event NftFlatFeeChanged(uint256 fee);
    event ClaimTargetSet(address indexed target, bool allowed);

    error NotOwner();
    error BadParam();

    constructor(address _feeRecipient, uint16 _feeBps, address _nftFeeToken, uint256 _nftFlatFee) {
        if (_feeRecipient == address(0) || _nftFeeToken == address(0) || _feeBps > 3000) revert BadParam();
        owner = msg.sender;
        feeRecipient = _feeRecipient;
        feeBps = _feeBps;
        nftFeeToken = _nftFeeToken;
        nftFlatFee = _nftFlatFee;
        emit OwnerChanged(msg.sender);
        emit NftFlatFeeChanged(_nftFlatFee);
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    function setNftFlatFee(uint256 fee) external onlyOwner {
        nftFlatFee = fee;
        emit NftFlatFeeChanged(fee);
    }

    function setClaimTarget(address target, bool allowed) external onlyOwner {
        if (target == address(0) || target == nftFeeToken) revert BadParam();
        claimTarget[target] = allowed;
        emit ClaimTargetSet(target, allowed);
    }

    function transferOwnership(address o) external onlyOwner {
        if (o == address(0)) revert BadParam();
        owner = o;
        emit OwnerChanged(o);
    }
}
