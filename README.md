# AuctionDeposit

**A safe way to put down a bid deposit at a distressed-property auction.**

When a bank or loan servicer auctions a repossessed property, every bidder must first lodge a deposit. Unsuccessful bidders wait for their money back, auctions are often cancelled or suspended, and some winners walk away without paying the rest of the price. AuctionDeposit holds every bidder's deposit in one escrow on [GenLayer](https://genlayer.com). The money moves only on what the official auction record says: losers are refunded, the winner's deposit goes to the creditor as part of the price once the record shows the balance paid, and it goes to the creditor as a penalty if the winner defaults. A cancelled or suspended auction refunds everyone, the winner too if the award is annulled or suspended after the win.

**Why it matters:** nearly **300,000** property auctions are waiting in Greece, and only about **1 in 5** succeeds (auction listings: unsold properties are listed again; [euro2day](https://www.euro2day.gr/en/article/2358318/nearly-300000-properties-are-awaiting-auction), citing IOBE and Cepal, Q1 2026, and the IMF). Europe's largest banks hold **€373bn** of bad loans (gross non-performing exposures of EU significant banks, Q2 2025, [Banca Ifis Market Watch NPL 2025](https://www.bancaifis.it/app/uploads/2025/09/MW_Npl_Sep25_ENG_20250926.pdf)).

Status: **work in progress** (contract v1.1, the ten demo cases, 259 tests on GenVM v0.2 and v0.6, every mutant caught).

**Try it yourself:** https://brilliantnodes.github.io/auction-deposit/app/ runs your own fictional auction on GenLayer Studio with free temporary accounts (creditor and two bidders; the record shows a paid, defaulted or cancelled outcome; about 20 to 35 minutes). Everything in the demo is fictional: the auction platform, creditor, properties and bidders. Test GEN only. Not legal advice.

**The article:** [Who holds the deposit? A proposal for settling property-auction deposits from the official auction record](https://brilliantnodes.github.io/auction-deposit/article.html). **For reviewers:** [REVIEWERS.md](REVIEWERS.md).

## How it decides
- Validators read the auction's record page; the model only **copies** the status, winning bidder and balance lines with their labels.
- Plain code checks every copy against the validator's own copy of the page, uses closed phrase tables (anything else is UNCLEAR and moves nothing), and validators must agree **exactly**.
- A state counts only when it is **seen twice**, in two readings sent at least `confirm_seconds` apart, after deposits close and before the deadline that applies.
- Deadlines settle by code alone: no confirmed payment within the winner's payment window (`balance_seconds`, counted from its confirmed win, so an adjourned auction still gets the full window) forfeits the winner's deposit; no confirmed outcome by `refund_by` refunds everyone.
- Payouts are credits; each address withdraws its own.

## The ten demo cases
Each case is one auction with three bidders, on a fictional auction platform. Time is compressed: what takes days at a real auction takes minutes here. The cases and the live-run timetable are in [`examples/cases.json`](examples/cases.json): two rounds of readings, a spare reading for any case not yet where it should be, two more rounds and a spare for the four-reading cases, then settle calls. The tests run the plan on both timetables (Studio and Bradbury) and drop each scheduled reading in turn: every case still ends as expected.

| # | Case | What the record shows | Who gets the money |
|---|---|---|---|
| 1 | Won, balance paid in full | Completed, winner B-1102, balance "Awaiting payment", later "Paid in full" | The two losing bidders get their deposits back; the winner's deposit goes to the creditor as part of the price. |
| 2 | Won, then the winner defaulted | Completed, winner B-1201, "Awaiting payment", later "Buyer in default" | The losing bidders get their deposits back; the winner did not pay the rest, so its deposit goes to the creditor as the penalty. |
| 3 | Won, balance never shown paid | Completed, winner B-1303, "Awaiting payment" | The losing bidders get their deposits back; no payment shows within the winner's payment window, so its deposit is forfeited to the creditor. |
| 4 | Auction cancelled | Cancelled | Every bidder gets its deposit back. |
| 5 | Auction suspended by the court | Suspended by court order | Every bidder gets its deposit back. |
| 6 | Adjourned, then won and paid | Adjourned, later Completed, winner B-1601, "Paid in full" | Nothing moves while the auction is adjourned; once it is won and paid, unsuccessful bidders are refunded and the winner's deposit goes to the creditor. |
| 7 | No bids | No bids | Nobody bid, so every bidder gets its deposit back. |
| 8 | Won by a bidder who did not use the escrow | Completed, winner B-1899, "Awaiting payment" | The winner lodged its deposit elsewhere, so everyone who used the escrow lost and gets its deposit back. |
| 9 | Page with a planted instruction | Completed, winner B-1902, "Paid in full", plus a planted line saying B-1901 won | The planted line tries to make B-1901 the winner; the contract follows the record, so B-1902 wins and the others are refunded. |
| 10 | The link shows another auction | Another auction's record (EA-24230), completed | Nothing moves on another auction's result; at the refund deadline every bidder gets its deposit back. |

## Limits, stated plainly
- The contract trusts one record page whose host the deployment trusts. In real life the record is kept by the auction platform (notaries or the state), not by the creditor; a creditor that controlled the page could lie.
- The creditor is whoever opens the auction, and anyone may open one for any auction id: a bidder must check the creditor's address before lodging.
- A bidder code links an address to a bidder only because the bidder says so. Someone can take a code first (and withdraw it before close): that blocks the real bidder from the escrow but gains nothing.
- "Seen twice" is measured by when readings are sent, not by when validators looked at the page.
- After a winner is confirmed, a payment shown in words outside the phrase table, or a record page that goes offline, counts as no payment: the winner's deposit is forfeited when its payment window closes.
- An auction takes at most 40 bidders, one deposit per address: someone who pays a full deposit from each of 40 addresses blocks everyone else from that escrow. It gains nothing; its deposits follow the record like anyone else's.
- The phrase tables are English and bidder codes are A to Z, digits and hyphens: a record in Greek would read UNCLEAR and refund everyone at `refund_by`. Records laid out with labels and values separated only by spaces are not checked for a second, planted line.
- Test GEN only; fictional demo; not legal advice.

## v1.1 (21 Nov 2026): a value copied with its label

The v1 prompt asked for the whole text on each line, and probe renders on GenLayer Studio (21 Nov 2026) showed that some models then copy the line's label into its value (`"value": "Status: Completed"`). v1 then found no such value after the label on the page and refused the reading (`N2_NOT_ANCHORED`): nothing moved, but the reading had to be repeated (in the two live runs, six readings were refused as not anchored: five in s1, one in b1). v1.1 does two things:

- `_unlabel`: when a copied value starts with its own copied label followed by `:`, `|` or `=`, only what follows is kept. The rest must still be anchored after that label on the validator's own copy of the page, so the reading is no looser: a value under another label, or one the page does not print on the label's line, is still refused.
- The prompt now asks for the text after the label, without the label.

The live runs s1 (Studio, [contract](https://explorer-studio.genlayer.com/address/0x3601d146F5AcdAf022Db51E7DB121E2c9ce890B1), record [`examples/live-studio-s1.json`](examples/live-studio-s1.json)) and b1 (Bradbury, [contract](https://scan.bradbury.genlayer.com/address/0x719bF130757Ba445DcB33C33AE8EF154004831b4), records [`examples/live-bradbury-b1.json`](examples/live-bradbury-b1.json) and [`examples/live-bradbury-b1-check.json`](examples/live-bradbury-b1-check.json)) ran contract v1; their replay is at https://brilliantnodes.github.io/auction-deposit/. The "Try it yourself" page uses the v1.1 visitor contract [`0x01bd…52F0`](https://explorer-studio.genlayer.com/address/0x01bdF97620fFdAe7391df6f98ba8889604d852F0) (record host brilliantnodes.github.io, minimum confirmation 60 s, `tools/deploy_visitor.py`; record pages `tools/make_try_pages.py`). Tests: `tests/direct/test_auction_deposit_v11.py`.

## Record pages
Each page shows the record as it stands at the reader's clock, so validators reading at different moments see it change the way a real record does.
```
python3 tools/make_record.py <tag> <D_unix> docs [--bradbury]     # D: when deposits close and the auction starts
python3 tools/check_pages.py <tag> <D_unix> docs [--bradbury]     # renders every page in Chromium at each reading time
```

## Tests
```
python3 -m venv venv && venv/bin/pip install -r requirements.txt
PYTHONPATH=. venv/bin/pytest tests/direct -q                 # 259 passed, 28 skipped (GenVM v0.2)
PYTHONPATH=. venv/bin/python tools/mutate.py                 # 150 of 150 mutants caught
tools/test_v6.sh /path/to/v6-venv                            # the same 259 on GenVM v0.6, packed Bradbury build
```
- `tests/direct/test_demo_cases.py` runs the ten cases on the exact page text, on both timetables, alone and all together in one contract, with each scheduled reading dropped in turn, plus the planted-instruction and wrong-page attacks. The skipped tests are drops of a third or fourth reading in two-reading cases.
- `tests/direct/test_auction_deposit_review1.py` holds the tests for the fixes after the first independent review.
- `tests/direct/test_auction_deposit_more.py` holds the tests added for every break the first mutation check found uncaught.
- `tools/mutate.py` breaks the contract on purpose, one change at a time (150 changes), and checks that the tests catch each one; three further changes are listed as equivalent, with the reasons.
- GenVM v0.6 (Testnet Bradbury): `bradbury/port.py` makes `bradbury/build/auction_deposit.py` and the compressed `auction_deposit_packed.py` (12.3 KB; ClaimEscrow's 15.5 KB packed build deployed on Bradbury where its 42.7 KB plain build did not); `tools/test_v6.sh` runs the unchanged tests against either with genlayer-test 0.30.0rc2 (`pip install --pre genlayer-test==0.30.0rc2`) and `tests/conftest_v6.py`.
