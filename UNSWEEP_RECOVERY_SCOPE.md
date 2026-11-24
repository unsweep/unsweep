# UNSWEEP Recovery Scope & Limitations

Last updated: 2026-11-24. UNSWEEP has not yet undergone an independent security audit; all operations are non-custodial and carry risk.

## 1. Supported Networks & Assets
- **Base Mainnet (chainId `8453`):** Rescue supported for 16 verified ERC-20 tokens listed in `relayer/data/assets_8453.json`.
- **Arbitrum One (chainId `42161`):** Rescue supported for 12 verified ERC-20 tokens listed in `relayer/data/assets_42161.json`.
- **Ethereum Mainnet (chainId `1`):** Read-only diagnostic only (delegation status, nonce, balances, and approvals); no rescue execution on chain `1`.
- **Additional ERC-20 tokens:** Other ERC-20 tokens detected during scanning may be selectable by the user at the same success fee tier, with **no guarantee** of execution or value valuation.
- **Per-rescue cap:** Up to `100,000 USD` per rescue (with extra price/stability checks above `10,000 USD` on mainnets).

## 2. Situations UNSWEEP Cannot Resolve
- **Funds already stolen:** Assets already drained from the compromised wallet cannot be recovered.
- **NFTs (ERC-721 / ERC-1155):** Not supported for automated rescue.
- **Custom airdrops, vesting schedules, or non-standard claim contracts:** Not guaranteed; reviewed case-by-case via `support@unsweep.com` (never send private keys or seed phrases).
- **Wallets where the attacker already has full control and out-races every transaction:** A fast sweeper or conflicting delegation/nonce state may prevent successful execution.

## 3. When Simulation Fails
- If the pre-execution simulation reverts or fails policy/eligibility checks, the rescue is not submitted on-chain.
- Common causes include insufficient token balance, unsupported token behavior, policy/cap restrictions, stale quote/deadline, or conflicting wallet state/nonce.
- You can adjust token selection, re-scan, or stop without paying a success fee.

## 4. Costs & Fee Structure
- **Diagnostic and simulation:** Free.
- **Upfront payment:** `$0` — UNSWEEP does not charge upfront fees and never asks you to send ETH to the compromised wallet.
- **Success fee (deducted in-transaction from rescued tokens only if executed):**
  - Below `$1,000` rescued value: `15%`
  - `$1,000` to `$10,000` rescued value: `10%`
  - Above `$10,000` rescued value: `5%`
  - Contract hard maximum fee cap: `15%` (`1500` bps).

## 5. Remaining Risks
- **No independent third-party audit yet:** Smart contracts, frontend local signing, and relayer services have not been audited by an external security firm.
- **Sweeper race / MEV / network congestion:** An active sweeper bot may still compete for block inclusion or gas priority.
- **Client & network environment risks:** Compromised local devices, browser extensions, malicious networks, or RPC issues can affect execution.

## 6. If a Transaction Does Not Confirm
- Because the relayer sponsors gas, a failed or unconfirmed submission does not charge a success fee to your safe wallet.
- Check the transaction hash or wallet state on the block explorer (Basescan / Arbiscan) and re-run a read-only scan before retrying.
- Do not repeatedly send funds into a compromised wallet or trust unsolicited DMs claiming to be UNSWEEP support.
