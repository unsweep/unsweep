// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title UNSWEEP M1 - configuracion (comision inmutable, limite y precios permitidos)
contract UnsweepConfig {
    address public owner;
    address public immutable feeRecipient;
    uint16 public immutable feeBps; // 1500 = 15 %
    uint256 public capUsd8; // limite por rescate en USD con 8 decimales (500e8)
    mapping(address => uint256) public tokenPriceUsd8; // USD (8 dec) por 1 token entero; 0 = no permitido
    mapping(address => uint256) public nftValueUsd8; // USD (8 dec) por NFT; 0 = no permitido
    mapping(address => bool) public claimTarget; // contratos de reclamo (airdrop) permitidos en r.calls

    event OwnerChanged(address indexed owner);
    event CapChanged(uint256 capUsd8);
    event TokenPriceSet(address indexed token, uint256 priceUsd8);
    event NftValueSet(address indexed collection, uint256 valueUsd8);
    event ClaimTargetSet(address indexed target, bool allowed);

    error NotOwner();
    error BadParam();

    constructor(address _feeRecipient, uint16 _feeBps, uint256 _capUsd8) {
        if (_feeRecipient == address(0) || _feeBps > 3000) revert BadParam();
        owner = msg.sender;
        feeRecipient = _feeRecipient;
        feeBps = _feeBps;
        capUsd8 = _capUsd8;
        emit OwnerChanged(msg.sender);
        emit CapChanged(_capUsd8);
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    function setCap(uint256 c) external onlyOwner {
        capUsd8 = c;
        emit CapChanged(c);
    }

    function setTokenPrice(address token, uint256 priceUsd8) external onlyOwner {
        tokenPriceUsd8[token] = priceUsd8;
        emit TokenPriceSet(token, priceUsd8);
    }

    function setNftValue(address collection, uint256 valueUsd8) external onlyOwner {
        nftValueUsd8[collection] = valueUsd8;
        emit NftValueSet(collection, valueUsd8);
    }

    function setClaimTarget(address target, bool allowed) external onlyOwner {
        if (tokenPriceUsd8[target] != 0 || nftValueUsd8[target] != 0) revert BadParam();
        claimTarget[target] = allowed;
        emit ClaimTargetSet(target, allowed);
    }

    function transferOwnership(address o) external onlyOwner {
        if (o == address(0)) revert BadParam();
        owner = o;
        emit OwnerChanged(o);
    }
}
