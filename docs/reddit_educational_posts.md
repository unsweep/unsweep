# Reddit educational drafts (DRAFTS ONLY)

Status: drafts. AIRE does not post anything. The human decides whether to publish, after reading each subreddit's rules (self-promotion limits, flair, disclosure). Do not cross-post the same text on the same day. Reply only in public threads; never DM users first.

---

## 1. r/Base

**Title:** Why ETH you send to a hacked wallet for gas disappears in seconds (and what EIP-7702 changes)

**Body:**

A common pattern after a wallet is drained: there are still tokens left (USDC, WETH...), but no ETH for gas. You send a little ETH to move them and it's gone within seconds.

That's a *sweeper bot*. The attacker holds the private key and runs a script that watches the address. Any incoming ETH gets moved out as soon as it lands, often in the next block, before you can use it.

Things worth knowing:

- Sending more ETH rarely helps: you are racing a bot that already has the key.
- Check whether the address has code: `cast code <address> --rpc-url https://mainnet.base.org`. `0x` means a plain EOA. `0xef0100…` means it has an EIP-7702 delegation, which you should look at carefully.
- With EIP-7702, a third party can submit a transaction that pays the gas, so the compromised wallet never has to hold ETH. The owner still signs locally.
- Whatever has already been moved out cannot be recovered. Treat the wallet as permanently unsafe afterwards.
- Anyone who DMs you offering recovery, or asking for your seed phrase, is a scammer.

Longer explanation: https://unsweep.com/guides/why-eth-for-gas-gets-stolen-immediately.html

Full disclosure: I built UNSWEEP, a non-custodial tool that uses sponsored EIP-7702 transactions to try to move remaining tokens out of compromised wallets on Base and Arbitrum. It charges a success fee taken from rescued tokens. It does not always work, and the free diagnostic is read-only. Happy to answer technical questions here.

---

## 2. r/arbitrum

**Title:** Hacked wallet on Arbitrum with tokens left but no ETH: what's going on and what to check first

**Body:**

If your wallet on Arbitrum One was compromised and every bit of ETH you send vanishes, you are probably dealing with a sweeper bot: an automated script run by someone who has your private key.

First steps I'd suggest:

1. Stop sending ETH to the compromised address.
2. Create a new wallet with a new seed phrase, on a device you trust, and move everything you can from other accounts to it.
3. Revoke token approvals from the compromised address if you can do it safely.
4. Check whether the address has an EIP-7702 delegation: `cast code <address> --rpc-url https://arb1.arbitrum.io/rpc`. `0xef0100<addr>` means it is delegated to `<addr>`.
5. Write down which tokens remain and their contract addresses.

Tokens that are still in the wallet can sometimes be moved with a sponsored transaction (EIP-7702), so that the compromised address never holds ETH. There is no guarantee, and funds already taken cannot be recovered.

Guide: https://unsweep.com/guides/rescue-tokens-hacked-wallet-arbitrum.html

Full disclosure: I built UNSWEEP, a non-custodial EIP-7702 rescue tool for Base and Arbitrum with a success fee. Never share your seed phrase with anyone, including me. I won't DM anyone.

---

## 3. r/ethereum

**Title:** Sweeper bots vs malicious EIP-7702 delegations: two different ways a compromised wallet gets drained

**Body:**

Since Pectra I've seen both of these come up in help threads, and they get mixed up:

**Sweeper bot (off-chain).** The attacker has the key and runs a script. The account still has no code. Incoming ETH is moved out as soon as it arrives.

**Malicious EIP-7702 delegation (on-chain).** The EOA has been set to delegate to attacker-controlled contract code (`eth_getCode` returns `0xef0100<address>`). Funds can then be moved according to that code's logic, in some cases without a separate signature from the owner each time.

Why it matters:

- The diagnostics differ. One is visible on-chain with `eth_getCode`; the other only shows up as a transaction pattern.
- The mitigations differ. A delegation can be changed by a new signed authorization, but if the attacker still has the key they can set it again.
- In both cases, a new wallet is the only safe long-term answer.

Comparison: https://unsweep.com/guides/sweeper-bot-vs-eip-7702-delegation.html
Spec: https://eips.ethereum.org/EIPS/eip-7702

Full disclosure: I built UNSWEEP, a non-custodial tool that uses sponsored EIP-7702 transactions to try to rescue remaining tokens on Base and Arbitrum (Ethereum mainnet is read-only diagnostic only). Corrections are welcome.

---

## 4. r/ethdev

**Title:** Using sponsored EIP-7702 transactions to move tokens out of a key-compromised EOA: design notes

**Body:**

Sharing design notes from a non-custodial rescue flow, in case it's useful or someone spots a problem.

Problem: the EOA's key is compromised, a sweeper bot drains any incoming ETH, but ERC-20 balances remain.

Approach:

- The user signs an EIP-7702 authorization plus a rescue intent **in the browser**. The key is never sent to a server.
- A relayer submits one type-4 transaction and pays the gas. In the same transaction, the EOA is delegated to a minimal delegate contract and tokens are transferred to a user-chosen safe address. A capped fee (max 1500 bps in the config contract) is taken from the rescued tokens.
- No ETH ever lands on the compromised address, so there is nothing for the bot to sweep.
- Before signing, a simulation shows the exact amounts.

Open issues and caveats:

- The attacker can race with their own 7702 authorization or token transfers. The rescue is a race, not a guarantee.
- Tokens with transfer hooks, blacklists or pausing behave differently; only an explicit list is treated as verified (16 on Base, 12 on Arbitrum).
- Same CREATE2 addresses on both chains, verified on Basescan and Arbiscan: delegate `0x38bcF425bC4d13624734e09376F2fafc799fA8c8`, config `0x56a345661e3999F2b20f1E069aAC14097Fa0D118`.

How to verify: https://unsweep.com/guides/how-to-check-if-wallet-has-sweeper-bot.html

Full disclosure: I built UNSWEEP, and this is how it works. It charges a success fee. Feedback on the threat model is very welcome.
