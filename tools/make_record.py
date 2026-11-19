#!/usr/bin/env python3
"""Write the fictional auction platform's record pages for one live run.

    python tools/make_record.py <tag> <D_unix> <out_dir> [--bradbury]

D is when deposits close and the auction starts. Each page is one auction's
official record on the fictional Kestrel Notarial e-Auctions platform. A page
carries its own schedule and shows the record as it stands at the reader's
clock, so validators reading at different moments see it change the way a real
one does (minutes after D, from examples/cases.json "timing"):

  until D + 3          Scheduled, no winner
  from  D + 3          the result: completed with a winner and "Awaiting
                       payment", or cancelled, suspended, adjourned, no bids
  from  D + 40         the second state, where a case has one (balance paid,
                       buyer in default, or the adjourned auction completed);
                       D + 50 with --bradbury, where readings queue

The live script reads well away from those change times. Pages go to
<out_dir>/record/<tag>/<auction id in lower case>.html. Every name, auction,
property and figure is fictional.

The same module gives the plain text a reader sees at any moment
(text_lines), the on-chain terms of each case (terms) and the deposit in wei,
so the tests, the page check and the live script all use one schedule.
"""
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "examples" / "cases.json").read_text())
G = 10**18
SCHEDULED = {"status": "Scheduled", "winner": "-", "bid": "-", "balance": "-"}
PUBLISHED_BEFORE = 6 * 3600  # the record is published this long before the auction
NOTE = ("Bidder codes are given by the notary on registration. "
        "Losing bidders' deposits are returned after the auction.")
FOOTER = ("Fictional platform, creditor, property and bidders, published for a GenLayer "
          "AuctionDeposit demonstration by Brilliant Nodes. Not a real auction record.")

STYLE = """body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:780px;margin:32px auto;padding:0 18px;color:#1d2a26;background:#f6f8f7}
.bar{background:#1f4a3f;color:#fff;padding:14px 18px;border-radius:6px}.bar b{font-size:19px}.bar span{display:block;font-size:13px;opacity:.8}
.notice{margin:16px 0 0;padding:10px 14px;border:1px solid #d9c27a;background:#fff8e1;border-radius:6px;font-size:14px}
h1{font-size:22px;margin:22px 0 14px}.row{padding:9px 0;border-bottom:1px solid #dbe3df}.k{display:inline-block;min-width:170px;color:#55635e}
.v{font-weight:600}.note{font-size:13px;color:#66736e;margin-top:18px}footer{margin-top:34px;font-size:12px;color:#8a9691}"""


def eur(n) -> str:
    return f"EUR {int(n):,}"


def utc(t: int) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def case_by_key(key: str) -> dict:
    return next(c for c in CASES["cases"] if c["key"] == key)


def deposit_wei(case: dict, net: str) -> int:
    per = CASES["eur_per_gen"][net]
    w, r = divmod(case["deposit_eur"] * G, per)
    assert r == 0, "deposit must convert to a whole number of wei"
    return w


def terms(case: dict, d: int, net: str) -> dict:
    """The terms the creditor freezes on chain (record_url apart)."""
    dl = {**CASES["deadlines"], **case.get("deadlines", {})}
    return {"auction_id": case["auction_id"], "property_ref": case["property"], "deposit": deposit_wei(case, net),
            "confirm_seconds": CASES["confirm_seconds"], "deposits_close": d,
            "balance_seconds": 60 * dl["balance_minutes"], "refund_by": d + 60 * dl["refund_by"]}


def page_path(tag: str, case: dict) -> str:
    return f"record/{tag}/{case['auction_id'].lower()}.html"


def _fields(r: dict) -> dict:
    return {"status": r["status"], "winner": r.get("winner") or "-",
            "bid": eur(r["bid_eur"]) if r.get("bid_eur") else "-", "balance": r.get("balance") or "-"}


def states(case: dict, d: int, net: str) -> list:
    """The record's states, each from a unix time on."""
    tm = CASES["timing"][net]
    s = [{"from": d - PUBLISHED_BEFORE, **SCHEDULED}]
    s.append({"from": d + 60 * tm["result"], **_fields(case["record"]["result"])})
    if "change" in case["record"]:
        s.append({"from": d + 60 * tm["change"], **_fields(case["record"]["change"])})
    return s


def state_at(case: dict, d: int, net: str, t: int) -> dict:
    cur = None
    for st in states(case, d, net):
        if cur is None or st["from"] <= t:
            cur = st
    return cur


def _shown(case: dict) -> dict:
    """What the page's fixed rows show: the case's own auction, or, on the
    wrong page, another one."""
    return {**case, **case.get("shows", {})}


def static_rows(case: dict, d: int) -> list:
    sh = _shown(case)
    return [("Auction", sh["auction_id"]), ("Property", sh["property"]), ("Creditor", CASES["creditor_name"]),
            ("Auction date", utc(d)), ("Starting price", eur(sh["starting_price_eur"])), ("Bid deposit", eur(sh["deposit_eur"]))]


def text_lines(case: dict, d: int, net: str, t: int) -> list:
    """The page's text at time t, one entry per non-empty line, as a reader
    rendering it in a browser sees it."""
    st = state_at(case, d, net, t)
    out = [CASES["platform"], "Electronic property auctions (fictional)"]
    if case.get("notice"):
        out.append(case["notice"])
    out.append("Official auction record")
    rows = static_rows(case, d) + [("Status", st["status"]), ("Winning bidder", st["winner"]),
                                    ("Winning bid", st["bid"]), ("Balance", st["balance"]), ("Last updated", utc(st["from"]))]
    out += [f"{k}: {v}" for k, v in rows]
    return out + [NOTE, FOOTER]


def page_html(case: dict, d: int, net: str) -> str:
    sched = json.dumps(states(case, d, net))
    sh = _shown(case)
    fixed = "\n".join(f'<div class="row"><span class="k">{k}:</span> <span class="v">{html.escape(v)}</span></div>'
                      for k, v in static_rows(case, d))
    live = "\n".join(f'<div class="row"><span class="k">{k}:</span> <span class="v" id="{i}"></span></div>'
                     for k, i in (("Status", "status"), ("Winning bidder", "winner"), ("Winning bid", "bid"),
                                  ("Balance", "balance"), ("Last updated", "updated")))
    notice = f'<p class="notice">{html.escape(case["notice"])}</p>\n' if case.get("notice") else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Auction {html.escape(sh["auction_id"])} - Official auction record - {html.escape(CASES["platform"])}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="bar"><b>{html.escape(CASES["platform"])}</b><span>Electronic property auctions (fictional)</span></div>
{notice}<h1>Official auction record</h1>
<div id="entry" hidden>
{fixed}
{live}
</div>
<noscript><p>This record needs JavaScript to show the current entry.</p></noscript>
<p class="note">{html.escape(NOTE)}</p>
<footer>{html.escape(FOOTER)}</footer>
<script>
(function () {{
  var s = {sched};
  var now = Date.now() / 1000, cur = s[0];
  for (var i = 0; i < s.length; i++) if (s[i].from <= now) cur = s[i];
  ["status", "winner", "bid", "balance"].forEach(function (k) {{ document.getElementById(k).textContent = cur[k]; }});
  document.getElementById("updated").textContent = new Date(cur.from * 1000).toISOString().slice(0, 16).replace("T", " ") + " UTC";
  document.getElementById("entry").hidden = false;
}})();
</script>
</body>
</html>
"""


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    tag, d, out = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
    net = "bradbury" if "--bradbury" in sys.argv[4:] else "studio"
    for case in CASES["cases"]:
        p = out / page_path(tag, case)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(page_html(case, d, net))
    print(json.dumps({"tag": tag, "d": d, "net": net, "pages": len(CASES["cases"]), "dir": str(out / "record" / tag)}))


if __name__ == "__main__":
    main()
