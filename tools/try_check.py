#!/usr/bin/env python3
"""Run one "Try it yourself" auction end to end on the visitor contract, the
way a visitor does on the site, and record every transaction.

    python tools/try_check.py <story> <contract> <out.json>

Three throwaway Studio accounts (creditor, two bidders) funded from Studio's
faucet; keys kept outside the repository, never printed. The slot is the
first one at least 6 minutes away. Readings: one after D + 3 and one 130 s
later; for paid/default, one after D + 10 and one 130 s later; then settle()
if needed and the withdrawals. Every name and figure is fictional.
"""
import json
import os
import sys
import time
from pathlib import Path

from genlayer_py import create_account, create_client
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionStatus

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_try_pages as tp  # noqa: E402

G = 10**18
SITE = "https://brilliantnodes.github.io/auction-deposit"
story, addr, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
REC = {"story": story, "contract": addr, "steps": []}


def save():
    out.write_text(json.dumps(REC, indent=1))


def log(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


ACC = {}
keys = {}
for role in ("creditor", "bidder1", "bidder2"):
    a = create_account()
    c = create_client(chain=studionet, account=a)
    for _ in range(8):
        try:
            c.provider.make_request(method="sim_fundAccount", params=[a.address, 20 * G])
            break
        except Exception:
            time.sleep(10)
    ACC[role] = (c, a)
    keys[role] = a.key.hex() if hasattr(a.key, "hex") else str(a.key)
kd = Path(os.environ.get("LIVE_KEY_DIR", "/home/claude/keys"))
kd.mkdir(parents=True, exist_ok=True)
(kd / f"studio-ad-try-{out.stem}.json").write_text(json.dumps(keys))
os.chmod(kd / f"studio-ad-try-{out.stem}.json", 0o600)
REC["accounts"] = {r: a.address for r, (c, a) in ACC.items()}


def result(r):
    cd = r.get("consensus_data") or {}
    lr = cd.get("leader_receipt")
    lr = lr[0] if isinstance(lr, list) and lr else lr
    lr = lr if isinstance(lr, dict) else {}
    res = lr.get("result") or {}
    p = res.get("payload") if isinstance(res, dict) else None
    if isinstance(p, dict) and "readable" in p:
        try:
            p = json.loads(p["readable"])
        except Exception:
            p = p["readable"]
    return r.get("status_name"), p


def send(role, fn, args, value=0):
    c, a = ACC[role]
    t0 = time.time()
    tx = c.write_contract(address=addr, function_name=fn, args=args, value=value)
    r = c.wait_for_transaction_receipt(transaction_hash=tx, status=TransactionStatus.ACCEPTED, interval=3000, retries=400)
    st, p = result(r)
    REC["steps"].append({"role": role, "call": fn, "tx": tx, "status": st, "sent": int(t0), "secs": round(time.time() - t0),
                         "result": p if fn != "open_auction" else {"id": (p or {}).get("id")}})
    save()
    log(f"{role} {fn} -> {st} ({round(time.time() - t0)} s) {tx}")
    return p


def view(fn, args):
    return ACC["creditor"][0].read_contract(address=addr, function_name=fn, args=args)


def until(t):
    while time.time() < t:
        time.sleep(min(15, max(1, t - time.time())))


now = int(time.time())
d = ((now + 6 * 60) // tp.SLOT + 1) * tp.SLOT
c = tp.case(story, d)
url = f"{SITE}/record/try/{story}/{c['auction_id'].lower()}.html"
REC.update({"deposits_close": d, "auction_id": c["auction_id"], "record_url": url})
log(f"slot {d} {c['auction_id']} {url}")
p = send("creditor", "open_auction", [c["auction_id"], c["property"], url, G, 120, d, 900, d + 40 * 60])
aid = p["id"]
REC["id"] = aid
digest = view("get_auction", [aid])["digest"]
send("bidder1", "deposit", [aid, tp.WINNER, digest], G)
send("bidder2", "deposit", [aid, tp.OTHER, digest], G)
until(d + 60 * tp.RESULT_MIN + 20)
send("bidder2", "read_record", [aid])
until(REC["steps"][-1]["sent"] + REC["steps"][-1]["secs"] + 130)
send("bidder2", "read_record", [aid])
if story != "cancelled":
    until(max(d + 60 * tp.CHANGE_MIN + 20, time.time()))
    send("bidder2", "read_record", [aid])
    until(REC["steps"][-1]["sent"] + REC["steps"][-1]["secs"] + 130)
    send("bidder2", "read_record", [aid])
a = view("get_auction", [aid])
if a["state"] not in ("SETTLED", "CANCELLED"):
    send("bidder2", "settle", [aid])
    a = view("get_auction", [aid])
for role, (cl, ac) in ACC.items():
    if int(view("get_claimable", [ac.address])) > 0:
        send(role, "withdraw", [0])
REC["final"] = {"state": a["state"], "winner": a["winner"], "money": a["money"], "reason": a["settled_reason"],
                "totals": view("totals", [])}
save()
log(json.dumps(REC["final"]))
