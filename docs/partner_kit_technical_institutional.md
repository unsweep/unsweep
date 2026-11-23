# UNSWEEP Partner Kit: Technical and Institutional Reference

Status: public reference material for wallet support desks, security teams, incident responders, educators and tool authors who want to point users to UNSWEEP. It is not an offer, not a contract and not a contact template. UNSWEEP does not send unsolicited messages to victims or organisations, and asks anyone who links to it to follow the same rule.

Website: https://unsweep.com/

## 1. What UNSWEEP does

UNSWEEP helps people whose wallet has been compromised, typically by a sweeper bot that drains any incoming gas or by a malicious EIP-7702 delegation, move the ERC-20 tokens that still remain in that wallet to a safe address they control. The user starts with a free diagnostic on the homepage: they enter the compromised address and see what is left and whether it falls within the supported scope.

## 2. Current scope

| Network | Status | Verified tokens |
|---|---|---|
| Base | Operational for rescue | 16 verified ERC-20 tokens |
| Arbitrum | Operational for rescue | 12 verified ERC-20 tokens |
| Ethereum | read-only (diagnostic only, no rescue) | Not applicable |

- Other ERC-20 tokens on Base or Arbitrum may be included in a rescue, but they are unverified and there is no guarantee that they can be moved or priced correctly.
- Ethereum mainnet is read-only today: the diagnostic can show balances, but UNSWEEP does not execute rescues there.

## 3. Security model

- The private key of the compromised wallet is used to sign locally in the user's browser. It is not sent to UNSWEEP servers. Technically minded users can confirm this with the Network tab of their browser's DevTools while they use the site.
- UNSWEEP never asks for a seed phrase by email, chat or any other channel. Anyone who asks for one in UNSWEEP's name is not UNSWEEP.
- Tokens are sent to a destination address chosen by the user. UNSWEEP does not hold user funds.

## 4. What UNSWEEP cannot do

- It does not rescue NFTs.
- It cannot recover funds that have already been stolen or moved out of the wallet.
- It does not execute rescues on Ethereum mainnet (read-only).
- It cannot promise any outcome for unverified tokens.
- It does not revoke a compromise. Users must stop using the compromised address after the rescue.

## 5. Fees

The diagnostic is free. A success fee is charged only when a rescue completes, and it is taken from the rescued value according to these tiers:

- 15% for rescues under 1,000 USD
- 10% for rescues from 1,000 to 10,000 USD
- 5% for rescues above 10,000 USD

There are no subscriptions, retainers or upfront payments.

## 6. The $100,000 figure

100,000 USD is the automatic per-rescue eligibility limit. Rescues above it are refused by the automated flow. Above 10,000 USD, additional price and token checks apply, and a rescue may be refused if those checks fail. The figure is an eligibility limit, not a guarantee of recovery: results depend on what remains in the wallet and on on-chain conditions at the time of the rescue.

## 7. What we do not claim

To keep references accurate, please do not attribute any of the following to UNSWEEP:

- No third-party security audit is claimed.
- No formal alliances, endorsements or institutional relationships are claimed.
- No client names, testimonials or recovery statistics are published in this kit.
- No recovery percentage or success rate is promised.

If you need a fact that is not in this document or on unsweep.com, treat it as unavailable.

## 8. How to reference UNSWEEP

- Link to the free diagnostic at https://unsweep.com/ or to the relevant guide below.
- Describe it as a self-service, non-custodial tool for moving remaining ERC-20 tokens out of a compromised wallet on Base or Arbitrum.
- Mention the exclusions (NFTs, already-stolen funds, Ethereum rescues) whenever you mention the service.
- Do not use the UNSWEEP name in paid ads, and do not send the link in unsolicited direct messages.

## 9. Published guides

- Rescue tokens from a sweeper bot on Base and Arbitrum: https://unsweep.com/guides/rescue-tokens-sweeper-bot-base-arbitrum.html
- What can and cannot be rescued: https://unsweep.com/guides/what-can-and-cannot-be-rescued.html
- Sweeper bot on a hacked wallet: https://unsweep.com/guides/sweeper-bot-hacked-wallet.html
- Malicious EIP-7702 delegation: https://unsweep.com/guides/eip-7702-malicious-delegation.html

## 10. Support

Support is written and asynchronous only. There are no calls, demos or custom agreements.

-- Founder, UNSWEEP
