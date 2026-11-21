// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console2} from "forge-std/Script.sol";
import {UnsweepConfig} from "../src/UnsweepConfig.sol";
import {UnsweepDelegate} from "../src/UnsweepDelegate.sol";

/// Despliegue M4c en Base Sepolia. Owner frio por constructor (nunca quien despliega).
/// Env: OPS_PK (deployer), CLAIM_TARGETS (lista de direcciones separada por comas, puede estar vacia).
contract DeployBaseSep is Script {
    address constant OWNER = 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B;
    address constant FEE_TO = 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B;
    uint16 constant FEE_BPS = 1500;

    function run() external returns (UnsweepConfig cfg, UnsweepDelegate impl) {
        address[] memory claims = vm.envOr("CLAIM_TARGETS", ",", new address[](0));
        vm.startBroadcast(vm.envUint("OPS_PK"));
        cfg = new UnsweepConfig(OWNER, FEE_TO, FEE_BPS, claims);
        impl = new UnsweepDelegate(cfg);
        vm.stopBroadcast();
        console2.log("CFG", address(cfg));
        console2.log("IMPL", address(impl));
        console2.log("claimTargets", claims.length);
    }
}
