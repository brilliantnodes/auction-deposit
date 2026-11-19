# AuctionDeposit

**A safe way to put down a bid deposit at a distressed-property auction.**

When a bank or loan servicer auctions a repossessed property, every bidder must first lodge a deposit. Losing bidders wait for their money back, auctions are often cancelled or suspended, and some winners walk away without paying the rest of the price. AuctionDeposit holds every bidder's deposit in one escrow on [GenLayer](https://genlayer.com). The money moves only on what the official auction record says: losers are refunded, the winner's deposit goes to the creditor as part of the price once the record shows the balance paid, and it goes to the creditor as a penalty if the winner defaults. A cancelled or suspended auction refunds everyone.

**Why it matters:** Europe's largest banks hold **€373bn** of bad loans ([Banca Ifis Market Watch NPL 2025](https://www.bancaifis.it/app/uploads/2025/09/MW_Npl_Sep25_ENG_20250926.pdf), Q2 2025). In Greece alone, nearly **300,000** property auctions are waiting, and only about **1 in 5** auctions succeeds ([euro2day](https://www.euro2day.gr/en2/article/2358318/nearly-300000-properties-in-line-for-auction), citing IOBE and Cepal, Q1 2026, and the IMF).

Status: **work in progress** (contract v0, the ten demo cases and 85 tests). Everything in the demo is fictional: the auction platform, creditor, properties and bidders. Test GEN only. Not legal advice.

## How it decides
- Validators read the auction's record page; the model only **copies** the status, winning bidder and balance lines with their labels.
- Plain code checks every copy against the validator's own copy of the page, uses closed phrase tables (anything else is UNCLEAR and moves nothing), and validators must agree **exactly**.
- A state counts only when it is **seen twice**, at least `confirm_seconds` apart, after deposits close.
- Deadlines settle by code alone: no confirmed payment by `balance_by` forfeits the winner's deposit; no confirmed outcome by `refund_by` refunds everyone.
- Payouts are credits; each address withdraws its own.

## The ten demo cases
Each case is one auction with three bidders, on a fictional auction platform. Time is compressed: what takes days at a real auction takes minutes here. The cases are in [`examples/cases.json`](examples/cases.json).

| # | Case | What the record shows | Who gets the money |
|---|---|---|---|
| 1 | Won, balance paid in full | Completed, winner B-1102, balance "Awaiting payment", later "Paid in full" | The two losing bidders get their deposits back; the winner's deposit goes to the creditor as part of the price. |
| 2 | Won, then the winner defaulted | Completed, winner B-1201, "Awaiting payment", later "Buyer in default" | The losing bidders get their deposits back; the winner did not pay the rest, so its deposit goes to the creditor as the penalty. |
| 3 | Won, balance never shown paid | Completed, winner B-1303, "Awaiting payment" | The losing bidders get their deposits back; no payment shows by the balance deadline, so the winner's deposit is forfeited to the creditor. |
| 4 | Auction cancelled | Cancelled | Every bidder gets its deposit back. |
| 5 | Auction suspended by the court | Suspended by court order | Every bidder gets its deposit back. |
| 6 | Adjourned, then won and paid | Adjourned, later Completed, winner B-1601, "Paid in full" | Nothing moves while the auction is adjourned; once it is won and paid, the losers are refunded and the winner's deposit goes to the creditor. |
| 7 | No bids | No bids | Nobody bid, so every bidder gets its deposit back. |
| 8 | Won by a bidder who did not use the escrow | Completed, winner B-1899, "Awaiting payment" | The winner lodged its deposit elsewhere, so everyone who used the escrow lost and gets its deposit back. |
| 9 | Page with a planted instruction | Completed, winner B-1902, "Paid in full", plus a planted line saying B-1901 won | The planted line tries to make B-1901 the winner; the contract follows the record, so B-1902 wins and the others are refunded. |
| 10 | The link shows another auction | Another auction's record (EA-24230), completed | Nothing moves on another auction's result; at the refund deadline every bidder gets its deposit back. |

## Record pages
Each page shows the record as it stands at the reader's clock, so validators reading at different moments see it change the way a real record does.
```
python3 tools/make_record.py <tag> <D_unix> docs [--bradbury]     # D: when deposits close and the auction starts
python3 tools/check_pages.py <tag> <D_unix> docs [--bradbury]     # renders every page in Chromium at each reading time
```

## Tests
```
python3 -m venv venv && venv/bin/pip install -r requirements.txt
PYTHONPATH=. venv/bin/pytest tests/direct -q
```
`tests/direct/test_demo_cases.py` runs the ten cases on the exact page text, alone and all together in one contract the way the live run will, plus the planted-instruction and wrong-page attacks.
