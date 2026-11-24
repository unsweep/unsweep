# UNSWEEP

Non-custodial rescue of ERC-20 tokens left in a compromised wallet (sweeper bot and/or malicious EIP-7702 delegation), **without sending ETH for gas to the compromised address**.

Website: https://unsweep.com/ · Free read-only diagnostic: https://unsweep.com/

> UNSWEEP never DMs first and never asks for a seed phrase. A rescue only uses the key of the already-compromised wallet, which you type yourself on unsweep.com and which never leaves your browser. Nothing here is a guarantee of success. Funds already moved out of a wallet cannot be recovered.

<!-- UNSWEEP-TRUST-2A -->
## Symptoms this is for (plain words)
- "My funds disappear as soon as they arrive in my wallet."
- "I can't pay for gas because any ETH I send is taken instantly."
- "My wallet was hacked and I can't get my tokens out."

These usually mean a sweeper bot and/or a malicious EIP-7702 delegation controls the wallet. UNSWEEP rescues the ERC-20 tokens still in it without you sending ETH for gas to that wallet.

## Open source and contract
- Source code: https://github.com/unsweep/unsweep
- Rescue contract (same address on Base and Arbitrum): `0x38bcF425bC4d13624734e09376F2fafc799fA8c8`
- Source verified on Sourcify (exact match): Base https://repo.sourcify.dev/8453/0x38bcF425bC4d13624734e09376F2fafc799fA8c8 · Arbitrum https://repo.sourcify.dev/42161/0x38bcF425bC4d13624734e09376F2fafc799fA8c8
- Basescan: https://basescan.org/address/0x38bcF425bC4d13624734e09376F2fafc799fA8c8#code

## Your key never leaves your browser
A rescue uses only the private key of the wallet that is already compromised (the attacker already has it), never your seed phrase and never the key of your safe wallet. It is signed 100% locally in your browser and the key is never sent to UNSWEEP or to any server; only signatures are sent. Proof: the exact signing code at https://github.com/unsweep/unsweep/blob/8d820edde5e120cbe86d965676af81f0b07d5537/web/assets/app.js#L240-L285 . Check it yourself: DevTools Network shows only signatures in the request to /api/rescue; the delegate contract 0x38bcF425bC4d13624734e09376F2fafc799fA8c8 is verified at https://basescan.org/address/0x38bcF425bC4d13624734e09376F2fafc799fA8c8#code ; UNSWEEP never writes to you first.

## We never DM you
UNSWEEP never contacts anyone by DM, Telegram or Discord. Anyone who contacts you there claiming to be UNSWEEP is a scammer. The only contact is support@unsweep.com, and it only replies to emails you send.

## What it costs and when
- Free diagnostic. No upfront payment.
- A success fee is charged only if the rescue transaction executes, in the same transaction, taken from the rescued tokens: 15% below 1,000 USD, 10% from 1,000 to 10,000 USD, 5% above 10,000 USD.
- The contract has a hard 15% maximum. The exact amounts you receive and the fee are shown in a simulation before you sign.

## What it cannot rescue
- Funds already taken out of the wallet: they cannot be recovered.
- NFTs.
- Anything on Ethereum mainnet (read-only diagnostic only).
- Tokens outside the verified lists (16 on Base, 12 on Arbitrum) may be detected, but without guarantee.
- Nothing is a guarantee of success; a 100,000 USD per-rescue eligibility limit applies.
<!-- /UNSWEEP-TRUST-2A -->

## Architecture (non-custodial)

1. **Diagnostic (read-only).** The user enters only the public address. The relayer reads balances of the verified token list, the account code (`eth_getCode`, to detect an EIP-7702 delegation `0xef0100…`) and returns what is in scope. No keys, no signatures.
2. **Simulation.** Before any signature the user sees the exact amounts to be received at the safe address and the fee, from a simulation of the rescue transaction.
3. **Local signature.** The EIP-7702 authorization and the rescue intent are signed in the browser. The private key never leaves the browser and is never sent to the server.
4. **Sponsored execution.** A relayer submits a single EIP-7702 (type 4) transaction and pays the gas. The compromised wallet is delegated to the UNSWEEP delegate contract within the same transaction, the tokens are transferred to the user's safe address and the fee is paid out of the rescued tokens.
5. **No custody.** Tokens go directly from the compromised wallet to the user's address in the same transaction; UNSWEEP never holds user funds.

Repository layout:

- `src/` – Solidity contracts (delegate + config), built with Foundry (`forge build`, `forge test`).
- `relayer/` – Python relayer and diagnostic API; verified asset lists in `relayer/data/assets_<chainId>.json`.
- `web/` – static site (no build step) and guides in `web/guides/`.
- `deployments/` – deployment records.
- `deploy/deploy_static.sh` – static site deploy with backup and hash verification.

## Verified scope by network

| Network | Chain id | Rescue | Verified tokens |
|---|---|---|---|
| Base | 8453 | Yes | 16 (`relayer/data/assets_8453.json`) |
| Arbitrum One | 42161 | Yes | 12 (`relayer/data/assets_42161.json`) |
| Ethereum | 1 | No (read-only diagnostic only) | – |

Other ERC-20 tokens may be detected during the scan and can be selected to attempt a rescue at the same fee percentage, without guarantee. NFTs are not rescued yet.

## Success fee

A share of the value rescued, taken from the rescued tokens in the same transaction and shown in the simulation before signing:

- 15% below 1,000 USD
- 10% from 1,000 to 10,000 USD
- 5% above 10,000 USD

No upfront payment is required from the user.

## Verify on-chain

Contracts are deployed with CREATE2 at the same addresses on Base and Arbitrum:

- Delegate: `0x38bcF425bC4d13624734e09376F2fafc799fA8c8`
- Config: `0x56a345661e3999F2b20f1E069aAC14097Fa0D118`

Explorers:

- Base: https://basescan.org/address/0x38bcF425bC4d13624734e09376F2fafc799fA8c8 · https://basescan.org/address/0x56a345661e3999F2b20f1E069aAC14097Fa0D118
- Arbitrum: https://arbiscan.io/address/0x38bcF425bC4d13624734e09376F2fafc799fA8c8 · https://arbiscan.io/address/0x56a345661e3999F2b20f1E069aAC14097Fa0D118

With Foundry:

```bash
# code exists at the same address on both networks
cast code 0x38bcF425bC4d13624734e09376F2fafc799fA8c8 --rpc-url https://mainnet.base.org
cast code 0x38bcF425bC4d13624734e09376F2fafc799fA8c8 --rpc-url https://arb1.arbitrum.io/rpc

# is a wallet delegated (EIP-7702)? 0x = no; 0xef0100<address> = delegated to <address>
cast code <WALLET_ADDRESS> --rpc-url https://mainnet.base.org
```

Compare the deployed bytecode with a local `forge build` of `src/` (compiler version recorded in `deployments/mainnet.txt`). For any rescue, inspect the type-4 transaction in the explorer: the token `Transfer` events show the amount sent to the safe address and the fee.

## Guides

- [Why ETH sent for gas gets stolen immediately](https://unsweep.com/guides/why-eth-for-gas-gets-stolen-immediately.html)
- [Rescue USDC and WETH from a hacked wallet on Base](https://unsweep.com/guides/rescue-usdc-weth-hacked-metamask-base.html)
- [Rescue tokens from a hacked wallet on Arbitrum](https://unsweep.com/guides/rescue-tokens-hacked-wallet-arbitrum.html)
- [Sweeper bot vs malicious EIP-7702 delegation](https://unsweep.com/guides/sweeper-bot-vs-eip-7702-delegation.html)
- [How to check if a wallet has a sweeper bot](https://unsweep.com/guides/how-to-check-if-wallet-has-sweeper-bot.html)
- [What to do in the first 5 minutes after a wallet hack](https://unsweep.com/guides/what-to-do-first-5-minutes-after-wallet-hack.html)
- [Sweeper bot on a hacked wallet](https://unsweep.com/guides/sweeper-bot-hacked-wallet.html)
- [Malicious EIP-7702 delegation](https://unsweep.com/guides/eip-7702-malicious-delegation.html)
- [Step-by-step rescue](https://unsweep.com/guides/rescue-tokens-sweeper-bot-base-arbitrum.html)
- [What can and cannot be rescued](https://unsweep.com/guides/what-can-and-cannot-be-rescued.html)

MetaMask is referenced descriptively in one guide title; UNSWEEP is not affiliated with MetaMask or Consensys.

## Development

```bash
forge build && forge test                # contracts
python -m pytest relayer/test_portada.py # site checks
```

Secrets (RPC keys, relayer keys) are read from environment files that are not part of this repository. Never commit them.

## Contact

support@unsweep.com (replies only to emails you send).
