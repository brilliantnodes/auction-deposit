#!/usr/bin/env python3
"""Write the record pages for the site's "Try it yourself" section.

    python tools/make_try_pages.py <out_dir> [--days 10] [--from <unix>]

A visitor runs one fictional auction on GenLayer Studio. Deposits close at a
slot D (every 15 minutes, UTC) and the page for that slot changes on its own
clock, the way the live runs' pages do:

  until D + 3     Scheduled, no winner
  from  D + 3     the result: completed, winner B-201, "Awaiting payment"
                  (stories paid and default), or "Cancelled" (story cancelled)
  from  D + 10    the second state: "Paid in full" or "Buyer in default"

Pages go to <out_dir>/record/try/<story>/<auction id, lower case>.html, one per
story and slot, from the next slot for --days days. The visitor contract
confirms a state seen twice at least 120 s apart, so a whole auction settles
about 15 minutes after D. Every name, auction, property and figure is
fictional.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_record as mr  # noqa: E402

SLOT = 15 * 60
RESULT_MIN, CHANGE_MIN = 3, 10
WINNER, OTHER = "B-201", "B-202"
STORIES = {
    "paid": {"letter": "P", "property": "Flat 2, 7 Marigold Lane, Velmora", "starting_price_eur": 52000, "deposit_eur": 5200,
             "result": {"status": "Completed", "winner": WINNER, "bid_eur": 58750, "balance": "Awaiting payment"},
             "change": {"status": "Completed", "winner": WINNER, "bid_eur": 58750, "balance": "Paid in full"}},
    "default": {"letter": "D", "property": "Shop 1, 30 Thistledown Road, Velmora", "starting_price_eur": 71000, "deposit_eur": 7100,
                "result": {"status": "Completed", "winner": WINNER, "bid_eur": 76200, "balance": "Awaiting payment"},
                "change": {"status": "Completed", "winner": WINNER, "bid_eur": 76200, "balance": "Buyer in default"}},
    "cancelled": {"letter": "C", "property": "House, 4 Orchard Close, Brindlemere", "starting_price_eur": 118000, "deposit_eur": 11800,
                  "result": {"status": "Cancelled"}},
}


def auction_id(story: str, d: int) -> str:
    return f"TRY-{STORIES[story]['letter']}-" + datetime.fromtimestamp(d, timezone.utc).strftime("%y%m%d%H%M")


def case(story: str, d: int) -> dict:
    s = STORIES[story]
    rec = {"result": s["result"]}
    if "change" in s:
        rec["change"] = s["change"]
    return {"auction_id": auction_id(story, d), "property": s["property"], "starting_price_eur": s["starting_price_eur"],
            "deposit_eur": s["deposit_eur"], "record": rec}


def states(c: dict, d: int, _net: str = "") -> list:
    out = [{"from": d - mr.PUBLISHED_BEFORE, **mr.SCHEDULED},
           {"from": d + 60 * RESULT_MIN, **mr._fields(c["record"]["result"])}]
    if "change" in c["record"]:
        out.append({"from": d + 60 * CHANGE_MIN, **mr._fields(c["record"]["change"])})
    return out


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    out = Path(a[0])
    days = int(a[a.index("--days") + 1]) if "--days" in a else 10
    start = int(a[a.index("--from") + 1]) if "--from" in a else int(datetime.now(timezone.utc).timestamp())
    first = (start // SLOT + 1) * SLOT
    mr.states = states  # page_html builds its schedule from this
    n = 0
    for d in range(first, first + days * 86400, SLOT):
        for story in STORIES:
            c = case(story, d)
            p = out / "record" / "try" / story / f"{c['auction_id'].lower()}.html"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(mr.page_html(c, d, "studio"))
            n += 1
    print(json.dumps({"pages": n, "first_slot": first, "last_slot": first + days * 86400 - SLOT}))


if __name__ == "__main__":
    main()
