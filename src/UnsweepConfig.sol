// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title UNSWEEP - configuracion on-chain minima (sin oraculo, sin precios, sin limite en USD)
/// @notice La comision ERC-20 se cobra en especie (feeBps de cada token rescatado, techo 15 %). Los NFTs
///         viajan gratis junto a un rescate de ERC-20 (no hay tarifa NFT). El owner es SIEMPRE una wallet
///         fria indicada en el constructor (nunca quien despliega); el cambio de owner es en dos pasos.
contract UnsweepConfig {
    address public owner;
    address public pendingOwner;
    address public immutable feeRecipient;
    uint16 public immutable feeBps; // 1500 = 15 %
    mapping(address => bool) public claimTarget; // contratos de reclamo (airdrop) autorizados en r.calls

    event OwnershipTransferStarted(address indexed previousOwner, address indexed newOwner);
    event OwnerChanged(address indexed owner);
    event ClaimTargetSet(address indexed target, bool allowed);

    error NotOwner();
    error NotPendingOwner();
    error BadParam();

    constructor(address _owner, address _feeRecipient, uint16 _feeBps, address[] memory _claimTargets) {
        if (_owner == address(0) || _feeRecipient == address(0) || _feeBps > 1500) revert BadParam();
        owner = _owner;
        feeRecipient = _feeRecipient;
        feeBps = _feeBps;
        emit OwnerChanged(_owner);
        for (uint256 i; i < _claimTargets.length; ++i) {
            address t = _claimTargets[i];
            if (t == address(0)) revert BadParam();
            claimTarget[t] = true;
            emit ClaimTargetSet(t, true);
        }
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    function setClaimTarget(address target, bool allowed) external onlyOwner {
        if (target == address(0)) revert BadParam();
        claimTarget[target] = allowed;
        emit ClaimTargetSet(target, allowed);
    }

    /// paso 1: el owner actual propone; nada cambia hasta que el nuevo owner acepte
    function transferOwnership(address o) external onlyOwner {
        if (o == address(0)) revert BadParam();
        pendingOwner = o;
        emit OwnershipTransferStarted(owner, o);
    }

    /// paso 2: el owner propuesto acepta desde su propia wallet
    function acceptOwnership() external {
        if (msg.sender != pendingOwner) revert NotPendingOwner();
        owner = msg.sender;
        pendingOwner = address(0);
        emit OwnerChanged(owner);
    }
}
