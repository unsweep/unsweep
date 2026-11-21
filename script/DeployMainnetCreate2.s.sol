// SPDX-License-Identifier: MIT
pragma solidity 0.8.39;

import {Script, console2} from "forge-std/Script.sol";
import {UnsweepConfig} from "../src/UnsweepConfig.sol";
import {UnsweepDelegate} from "../src/UnsweepDelegate.sol";

/// UNSWEEP FASE 2 PASO 2 (#737): despliegue CREATE2 idempotente (misma direccion en Base y Arbitrum).
/// Usa el CREATE2 Deployer determinista 0x4e59b44847b379578588920cA78FbF26c0B4956C (por defecto en forge).
/// Si la direccion predicha ya tiene codigo, NO redespliega. Env: OPS_PK (deployer; nunca se imprime).
contract DeployMainnetCreate2 is Script {
    address constant FACTORY = 0x4e59b44847b379578588920cA78FbF26c0B4956C;
    address constant OWNER = 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B;
    address constant FEE_TO = 0x7E26916f1FF93FcF6CCd7eAaa0561007783FDA1B;
    uint16 constant FEE_BPS = 1500;
    bytes32 constant SALT_CFG = keccak256("unsweep.mainnet.v1.config");
    bytes32 constant SALT_IMPL = keccak256("unsweep.mainnet.v1.delegate");

    function _pred(bytes32 salt, bytes memory initCode) internal pure returns (address) {
        return address(uint160(uint256(keccak256(abi.encodePacked(bytes1(0xff), FACTORY, salt, keccak256(initCode))))));
    }

    function predict() public pure returns (address cfg, address impl) {
        address[] memory claims = new address[](0);
        cfg = _pred(
            SALT_CFG, abi.encodePacked(type(UnsweepConfig).creationCode, abi.encode(OWNER, FEE_TO, FEE_BPS, claims))
        );
        impl = _pred(SALT_IMPL, abi.encodePacked(type(UnsweepDelegate).creationCode, abi.encode(cfg)));
    }

    function run() external returns (address cfg, address impl) {
        require(FACTORY.code.length > 0, "CREATE2 factory ausente");
        (address pc, address pi) = predict();
        address[] memory claims = new address[](0);
        vm.startBroadcast(vm.envUint("OPS_PK"));
        if (pc.code.length == 0) {
            cfg = address(new UnsweepConfig{salt: SALT_CFG}(OWNER, FEE_TO, FEE_BPS, claims));
        } else {
            cfg = pc;
            console2.log("CFG ya desplegado, se omite");
        }
        if (pi.code.length == 0) {
            impl = address(new UnsweepDelegate{salt: SALT_IMPL}(UnsweepConfig(cfg)));
        } else {
            impl = pi;
            console2.log("IMPL ya desplegado, se omite");
        }
        vm.stopBroadcast();
        require(cfg == pc && impl == pi, "direccion distinta de la predicha");
        UnsweepConfig c = UnsweepConfig(cfg);
        require(c.owner() == OWNER && c.feeRecipient() == FEE_TO && c.feeBps() == FEE_BPS, "params");
        require(address(UnsweepDelegate(payable(impl)).config()) == cfg, "config");
        console2.log("CFG", cfg);
        console2.log("IMPL", impl);
        console2.log("chainId", block.chainid);
    }
}
