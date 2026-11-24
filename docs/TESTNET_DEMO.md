# UNSWEEP Testnet Demonstration Record (Base Sepolia — Non-Real Funds)

> **Testnet demonstration only:** This document is for Base Sepolia (`chainId 84532`) test wallets and mock tokens only. It is **not** a real-funds recovery or a mainnet production rescue claim.

## 1. Testnet Reference Environment (`deployments/base-sepolia.txt`)
- **Network:** Base Sepolia (`chainId 84532`)
- **Compiler:** `solc` `0.8.39` (`prague`, `via_ir`, `200` runs)
- **Testnet `UnsweepConfig`:** `0x2421aa3a6c473fD7ccA6be9bF4024E92CE80176d` (deploy tx: `0x6f31ad6c45c2261dcf26d051a674576970deed2bc485a7fa3fc2ae89e8067b81`)
- **Testnet `UnsweepDelegate`:** `0xBe5a2F788fa56DeCc7b13a20F45429d167a8080e` (deploy tx: `0x7f109d845f092273fd4aee64cd5e71d9a66e9e48990158c2b208524e3c2ac87c`)
- **Mock test tokens on Base Sepolia:**
  - `TEST_USDC_MOCK`: `0x7E8Ea2A6220595980A334d922168Dc411f32C87f`
  - `TEST_GOV_MOCK`: `0xBC8d360e40f2728b2eDB1AC3Ba4d1E310FE80E47`
  - `TEST_AIRDROP_MOCK`: `0x86E7675e4aB5CF25B85445d7514bE2f427a79AfA`
  - `TEST_NFT_MOCK`: `0xA01B2D7352966494c95aDB724373C04d9aB8c483`
- **Test sweeper script:** `scripts/sweeper_sepolia.sh` (test wallets only; reads `VICTIM_PK` from a test keyfile, never CLI arguments).

## 2. Testnet Run Log Template (Populate From Actual Testnet Execution)
- **Run date (UTC):** pending execution
- **Test victim address (testnet only):** `0x...`
- **Test safe destination address (testnet only):** `0x...`
- **Simulated output & fee:** pending run (expected amount to safe address and simulated fee breakdown)
- **Local signatures generated:** EIP-7702 authorization + EIP-712 rescue intent (signed locally on test key; private key never sent to server)
- **Testnet transaction hash:** `0x...` (verify on `https://sepolia.basescan.org/tx/...`)
- **Final on-chain outcome:** pending run (token `Transfer` events to safe address and fee recipient)
