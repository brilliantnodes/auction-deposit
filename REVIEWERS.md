# AuctionDeposit: start here (for reviewers, 5 minutes)

**What it is, in plain words:** an escrow for bid deposits at a distressed-property auction. Every bidder's deposit waits in one contract and moves only on what GenLayer validators read on the auction's official record page: the status, the winning bidder and the balance. Losers are refunded; the winner's deposit goes to the creditor as part of the price once the balance shows paid, or as the penalty if the winner defaults; a cancelled, suspended or bid-less auction refunds everyone. Market: nearly 300,000 property auctions waiting in Greece, about 1 in 5 succeeds ([euro2day](https://www.euro2day.gr/en2/article/2358318/nearly-300000-properties-in-line-for-auction), citing IOBE and Cepal, Q1 2026, and the IMF).

## 1. How consensus binds the money

- **The model copies; code decides.** Each validator fetches the record page itself; its model only copies the status, winner and balance lines, each with its label. Plain Python checks every copy against the validator's own copy of the page (a value must be printed after its own label, `_unlabel` in v1.1), maps status and balance through closed phrase tables (anything else is `UNCLEAR` and moves nothing) and never asks the model who should be paid. Phrase tables and labels: `get_rules()`.
- **Exact agreement on everything that moves money.** A validator accepts the leader's result only if the kind, status, winning bidder code and balance equal its own (`_same_outcome` in [`contracts/auction_deposit.py`](contracts/auction_deposit.py)). There is no tolerance, so two accepted readings can never pay differently. A `NO_READING` binds nothing; anyone may read again.
- **Nothing moves on one look.** A state counts only when seen twice, in readings sent at least `confirm_seconds` apart, after deposits close and before the deadline that applies. A planted line or a page shown for a moment cannot move money.
- **Every amount is integer code.** Each deposit is either refunded, paid to the creditor or still held; `totals()` reconciles the balance as `locked + credited`.
- **No stuck money.** `settle()` applies the deadlines without a model: no confirmed payment within the winner's payment window forfeits its deposit; no confirmed outcome by `refund_by` refunds everyone.
- **Payouts are credits.** Each address calls `withdraw()` for its own money.

## 2. Check it in five steps

1. **Try it yourself:** https://brilliantnodes.github.io/auction-deposit/app/ (free temporary Studio accounts for a creditor and two bidders; a paid, defaulted or cancelled outcome; about 20 to 35 minutes). It runs on the v1.1 visitor contract: [explorer](https://explorer-studio.genlayer.com/address/0x01bdF97620fFdAe7391df6f98ba8889604d852F0) or [import it into GenLayer Studio](https://studio.genlayer.com/?import-contract=0x01bdF97620fFdAe7391df6f98ba8889604d852F0).
2. Call `get_rules()` on that contract to see the frozen record host, the minimum confirmation time, the phrase tables and the agreement rule.
3. Open the replay of the live runs: https://brilliantnodes.github.io/auction-deposit/ (ten fictional auctions, three bidders each; every case ended as planned).
4. Testnet Bradbury run b1: [contract](https://scan.bradbury.genlayer.com/address/0x719bF130757Ba445DcB33C33AE8EF154004831b4), 78 transactions, all finalized; the independent check [`examples/live-bradbury-b1-check.json`](examples/live-bradbury-b1-check.json) re-reads every transaction from the chain, and the contract's balance, locked and credited amounts are all zero at the end. Two readings in that run reached no agreement (one no majority, one majority disagree): nothing moved on them, and the spare readings in the plan settled both cases as expected.
5. GenLayer Studio run s1: [contract](https://explorer-studio.genlayer.com/address/0x3601d146F5AcdAf022Db51E7DB121E2c9ce890B1), the same ten cases, all as planned ([`examples/live-studio-s1.json`](examples/live-studio-s1.json)).

## 3. Tests

- 259 tests pass on GenVM v0.2 (Studio) and the same 259 on GenVM v0.6 (Bradbury, packed build), 28 skipped on each (drops of a third or fourth reading in two-reading cases). Commands: README, [Tests](README.md#tests).
- `tools/mutate.py` breaks the contract on purpose 150 ways; the tests catch all 150.
- The ten cases include a record page with a planted line naming another winner, and a link that shows another auction's result.

## 4. Links

- Source: [`contracts/auction_deposit.py`](contracts/auction_deposit.py)
- Demo video file: [`docs/auctiondeposit-demo.mp4`](docs/auctiondeposit-demo.mp4)
- Limits, stated plainly: README, [Limits](README.md#limits-stated-plainly)

*Fictional platform, creditor, properties and bidders; test GEN only. Not legal advice.*
