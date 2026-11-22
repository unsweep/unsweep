# UNSWEEP Security Referral Partners — DRAFT (not published)

> Internal draft for order #1290. Not deployed, not linked from web/*. Every statement carries a tag:
> [HECHO] = verified in this repo (file cited); [HIPOTESIS] = proposal, not implemented; [NO_DISPONIBLE] = does not exist today.

## How it would work (self-service)

- [HIPOTESIS] The program is fully self-service. A partner (wallet security blog, community moderator, tool author) reads these public terms and links to the free diagnostic. There is no application call, no negotiation and no custom deal. Support, if any, is written and asynchronous only.
- [HECHO] The free diagnostic is the address scan on the homepage, https://unsweep.com/ (web/index.html: "Scan your address above to see what is left").
- [HIPOTESIS] Partners must not spam, cold-message victims or use the UNSWEEP name in ads. Linking from their own content is the only permitted channel.

## Fees the user pays (unchanged by referrals)

- [HECHO] Success fee tiers by rescued value: 15 % (< 1,000 USD), 10 % (1,000–10,000 USD), 5 % (> 10,000 USD). Source: relayer/policy.py, `tier_bps`.
- [HECHO] On Ethereum (chain 1) the fee is max(tier, estimated gas x 1.5). It never exceeds the 15 % contract ceiling; if it would, the rescue is rejected. Source: relayer/policy.py (`MAX_FEE_BPS = 1500`, `ETH_GAS_MULT = 1.5`).
- [HIPOTESIS] A referral never increases the fee paid by the user.

## The $100,000 figure

- [HECHO] 100,000 USD is the automatic per-rescue **eligibility limit** on supported mainnets (1, 8453, 42161). Rescues above it are refused. Source: relayer/policy.py, `CAP_INITIAL_USD` / `cap_usd` / `check_cap`.
- [HECHO] Above 10,000 USD extra price and token checks apply, and a rescue can be refused if they fail. Source: relayer/policy.py, `check_high_value`.
- [HECHO] 100,000 USD is **not a guarantee**: it does not promise that any amount will be recovered, or that a given rescue is possible. Outcome depends on what remains in the wallet and on on-chain conditions.

## Partner commission

- [NO_DISPONIBLE] There is no referral attribution or commission split today. The relayer and the contracts contain no referral or partner logic (repo grep at f813907). A partner payout cannot work without changing the relayer and/or the contracts, so **no partner commission is offered**.
- [HIPOTESIS] If it were built later, it could be an on-chain share of the UNSWEEP fee (taken from the 15/10/5 fee, never added on top), paid automatically in the same transaction to an address embedded in the referral link. Percentage: NO_DISPONIBLE (not decided).
- [NO_DISPONIBLE] Payout schedule, minimums and tracking dashboard.

## Notes for reviewers

- [HECHO] The header comment in relayer/policy.py still says "10,000 / 50,000 USD". The code returns 100,000 (#927). The comment is stale; it was not changed in this order.
