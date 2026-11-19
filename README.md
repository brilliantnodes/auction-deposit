# AuctionDeposit

**A safe way to put down a bid deposit at a distressed-property auction.**

When a bank or loan servicer auctions a repossessed property, every bidder must first lodge a deposit. Losing bidders wait for their money back, auctions are often cancelled or suspended, and some winners walk away without paying the rest of the price. AuctionDeposit holds every bidder's deposit in one escrow on [GenLayer](https://genlayer.com). The money moves only on what the official auction record says: losers are refunded, the winner's deposit goes to the creditor as part of the price once the record shows the balance paid, and it goes to the creditor as a penalty if the winner defaults. A cancelled or suspended auction refunds everyone.

Status: **work in progress** (contract v0 and its first tests). Everything in the demo is fictional: the auction platform, creditor, properties and bidders. Test GEN only. Not legal advice.

## How it decides
- Validators read the auction's record page; the model only **copies** the status, winning bidder and balance lines with their labels.
- Plain code checks every copy against the validator's own copy of the page, uses closed phrase tables (anything else is UNCLEAR and moves nothing), and validators must agree **exactly**.
- A state counts only when it is **seen twice**, at least `confirm_seconds` apart, after deposits close.
- Deadlines settle by code alone: no confirmed payment by `balance_by` forfeits the winner's deposit; no confirmed outcome by `refund_by` refunds everyone.
- Payouts are credits; each address withdraws its own.

## Tests
```
python3 -m venv venv && venv/bin/pip install -r requirements.txt
PYTHONPATH=. venv/bin/pytest tests/direct -q
```
