#!/usr/bin/env python3
"""Run the ten fictional AuctionDeposit cases live on GenLayer Studio or
Testnet Bradbury, side by side, and record every transaction.

    python tools/live.py <tag> <D_unix> [--net studio|bradbury] [--contract 0x.. [--deploy-tx 0x..]]

D is when deposits close and every auction starts. The record pages must
already be live at <AD_SITE>/record/<tag>/<auction id>.html
(tools/make_record.py <tag> <D> docs [--bradbury], pushed to GitHub Pages).
The timetable is examples/cases.json "timing" (minutes after D):

  D - 50 .. D - 15  deploy, one refused open (host not on the list), ten opens,
                    thirty deposits (one refused first: not exactly the deposit),
                    then a check that every bidder is registered (else stop)
  reads[0], [1]     rounds 1 and 2 (the result shows from D + result)
  spares[0]         a spare reading for any case not yet in its after_first state
  reads[2], [3]     rounds 3 and 4, four-reading cases (second state from D + change)
  spares[1]         a spare for any four-reading case not yet settled
  settle            settle() for the deadline cases
  final_settle      settle() for anything still open (skipped if nothing is)
  then              withdrawals by all four parties; totals and the contract's
                    balance reconciled; every case checked against "expect"

A second reading of a run waits confirm_seconds + 60 s after the first one's
receipt came back, not after it was queued, so "seen twice" holds even when a
transaction waited in a wallet queue.

Studio: throwaway accounts funded from Studio's faucet, one reader account per
case. Bradbury: four test wallets (creditor, three bidders) whose key files are
in BRADBURY_KEY_DIR (never printed); readings are spread over the four.
Every name, auction and figure is fictional; only test GEN moves.
"""
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import make_record as mr  # noqa: E402

G = 10**18
SITE = os.environ.get("AD_SITE", "https://brilliantnodes.github.io/auction-deposit").rstrip("/")
HOST = SITE.split("://", 1)[1].split("/", 1)[0]
CASES = mr.CASES["cases"]
C = mr.CASES["confirm_seconds"]
args = sys.argv[1:]
TAG, D = args[0], int(args[1])


def opt(name, default=""):
    return args[args.index(name) + 1] if name in args else default


NET = opt("--net", "studio")
BB = NET == "bradbury"
TM = mr.CASES["timing"][NET]
ROLES = ("creditor", "bidder1", "bidder2", "bidder3")
REC_PATH = ROOT / "examples" / f"live-{NET}-{TAG}.json"
REC = {"net": NET, "tag": TAG, "deposits_close": D, "site": SITE, "contract": {}, "accounts": {}, "auctions": {}, "steps": []}
LOCK = threading.Lock()


class ReceiptTimeout(RuntimeError):
    """The transaction was sent but no receipt came back: never send it again."""


def utc(ts=None):
    return datetime.fromtimestamp(ts if ts is not None else time.time(), timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    with LOCK:
        print(f"{utc()} {msg}", flush=True)


def save():
    with LOCK:
        REC_PATH.write_text(json.dumps(REC, indent=1, default=str))


def until(ts):
    while time.time() < ts:
        time.sleep(min(5, max(0.5, ts - time.time())))


class FifoLock:
    """A lock that serves waiting threads in arrival order."""

    def __init__(self):
        self.c, self.q = threading.Condition(), []

    def __enter__(self):
        me = object()
        with self.c:
            self.q.append(me)
            while self.q[0] is not me:
                self.c.wait()

    def __exit__(self, *exc):
        with self.c:
            self.q.pop(0)
            self.c.notify_all()


def reader(i):
    return f"reader{i}" if not BB else ROLES[i % len(ROLES)]


# ------------------------------------------------------------------ backends

if not BB:
    from genlayer_py import create_account, create_client
    from genlayer_py.chains import studionet
    from genlayer_py.types import TransactionStatus

    ACCTS, ROLE_LOCKS = {}, {}

    def _keep_key(role, a):
        """Keep this throwaway Studio key outside the repo (never printed or
        committed), so a run cut short can still be finished by hand."""
        d = Path(os.environ.get("LIVE_KEY_DIR", "/home/claude/keys"))
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"studio-ad-{REC_PATH.stem}.json"
        keys = json.loads(f.read_text()) if f.exists() else {}
        keys[role] = a.key.hex() if hasattr(a.key, "hex") else str(a.key)
        f.write_text(json.dumps(keys))
        os.chmod(f, 0o600)

    def make_accounts():
        for role in ROLES + tuple(f"reader{i}" for i in range(len(CASES))):
            a = create_account()
            c = create_client(chain=studionet, account=a)
            for _k in range(8):  # Studio's gateway sometimes answers 502 for a few seconds
                try:
                    c.provider.make_request(method="sim_fundAccount", params=[a.address, 300 * G])
                    break
                except Exception:
                    time.sleep(10)
            ACCTS[role] = (c, a)
            _keep_key(role, a)
            ROLE_LOCKS[role] = threading.Lock()
            REC["accounts"][role] = a.address

    def _wait(c, tx):
        deadline, last = time.time() + 3600, None  # a busy Studio has taken 35 minutes to process a reading
        while time.time() < deadline:
            try:
                return c.wait_for_transaction_receipt(transaction_hash=tx, status=TransactionStatus.ACCEPTED, interval=3000, retries=20)
            except Exception as e:
                last = e
                time.sleep(5)
        raise ReceiptTimeout(f"no receipt for {tx}: {last}")

    def _result(r):
        cd = r.get("consensus_data") or {}
        lr = cd.get("leader_receipt")
        lr = lr[0] if isinstance(lr, list) and lr else lr
        lr = lr if isinstance(lr, dict) else {}
        res = lr.get("result") or {}
        payload = res.get("payload") if isinstance(res, dict) else None
        if isinstance(payload, dict) and "readable" in payload:
            try:
                payload = json.loads(payload["readable"])
            except Exception:
                payload = payload["readable"]
        return {"status": r.get("status_name"), "execution": lr.get("execution_result"), "result": payload, "votes": cd.get("votes") or {}}

    def deploy(role, path, cargs):
        c, a = ACCTS[role]
        tx = c.deploy_contract(code=Path(path).read_text(), args=cargs)
        r = _wait(c, tx)
        return tx, r.get("to_address") or r.get("recipient")

    def send(role, addr, fn, fargs, value=0, payees=""):
        """One send only: a retry after the node got it would be a second transaction."""
        c, a = ACCTS[role]
        with ROLE_LOCKS[role]:
            sent_at = time.time()
            tx = c.write_contract(address=addr, function_name=fn, args=fargs, value=value)
        return tx, {**_result(_wait(c, tx)), "sent_at": sent_at, "done_at": time.time()}

    def view(addr, fn, fargs):
        c, a = ACCTS["creditor"]
        for k in range(8):
            try:
                return c.read_contract(address=addr, function_name=fn, args=fargs)
            except Exception:
                if k == 7:
                    raise
                time.sleep(10)

    def balance(addr):
        c, a = ACCTS["creditor"]
        return int(c.provider.make_request(method="eth_getBalance", params=[addr, "latest"])["result"], 16)
else:
    JS = ROOT / "tools" / "bradbury"
    KEY_DIR = os.environ.get("BRADBURY_KEY_DIR", "/home/claude/keys")
    KEYS = {r: f"{KEY_DIR}/ad_{r}.key" for r in ROLES}
    ROLE_LOCKS = {r: FifoLock() for r in KEYS}
    NOTHING = ("UNDETERMINED", "LEADER_TIMEOUT", "VALIDATORS_TIMEOUT", "CANCELED")

    def _node(role, *a, timeout=1800):
        p = subprocess.run(["node", "gl.mjs", *a], cwd=JS, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "BRADBURY_KEY_FILE": KEYS[role]})
        return [json.loads(x) for x in p.stdout.splitlines() if x.startswith("{")]

    def make_accounts():
        from eth_account import Account
        for role in KEYS:
            REC["accounts"][role] = Account.from_key(Path(KEYS[role]).read_text().strip()).address

    def _tx(h):
        o = _node("creditor", "tx", h, timeout=300)
        return (o[-1].get("raw") if o else None) or {}

    def _decided(raw):
        st = str(raw.get("statusName", ""))
        return st in NOTHING or (st in ("ACCEPTED", "FINALIZED") and raw.get("resultName") not in (None, "", "IDLE"))

    def _wait_h(h, final=False):
        for _ in range(240):
            raw = _tx(h)
            if (str(raw.get("statusName")) == "FINALIZED") if final else _decided(raw):
                return raw
            time.sleep(10)
        return _tx(h)

    def deploy(role, path, cargs):
        o = _node(role, "deploy", str(path), json.dumps(cargs))
        d = next((x for x in reversed(o) if "ok" in x), {})
        raw = d.get("raw") or {}
        return d.get("hash"), raw.get("recipient") or raw.get("toAddress") or (raw.get("txDataDecoded") or {}).get("contractAddress")

    def send(role, addr, fn, fargs, value=0, payees=""):
        with ROLE_LOCKS[role]:
            sent_at = time.time()  # the moment it leaves, after any wait for the wallet
            o = _node(role, "write", addr, fn, json.dumps(fargs), str(value), payees)
        sent = next((x["sent"] for x in o if "sent" in x), None)
        d = next((x for x in reversed(o) if "ok" in x), {})
        h = d.get("hash") or sent
        if not h:  # nothing left the wallet: raise, so step() records SEND_FAILED and retries a reading
            raise RuntimeError(str(d.get("error") or "gl.mjs gave no transaction hash")[:300])
        raw = d.get("raw") or {}
        if not _decided(raw):
            raw = _wait_h(h)
        if str(raw.get("statusName")) in ("LEADER_TIMEOUT", "VALIDATORS_TIMEOUT"):
            raw = _wait_h(h, final=True)
        st = str(raw.get("statusName", ""))
        return h, {"status": st if st in NOTHING else raw.get("resultName"), "execution": raw.get("txExecutionResultName"),
                   "created": raw.get("createdTimestamp"), "result": None, "sent_at": sent_at, "done_at": time.time()}

    def view(addr, fn, fargs):
        d = {}
        for _ in range(3):
            o = _node("creditor", "read", addr, fn, json.dumps(fargs), timeout=300)
            d = o[-1] if o else {}
            if d.get("ok"):
                return d["result"]
            time.sleep(10)
        raise RuntimeError(f"read {fn} failed: {d}")

    def balance(addr):
        return int(_node("creditor", "balance", addr, timeout=120)[-1]["result"])


def step(case, role, addr, fn, fargs, value=0, expect=None, payees=""):
    log(f"[{case}] {fn} from {role}" + (f" value {value}" if value else ""))
    tx, r = None, {}
    for attempt in range(3 if fn == "read_record" else 1):
        # a reading is an observation: sending it again after a failed send cannot move money twice
        try:
            tx, r = send(role, addr, fn, fargs, value, payees)
            break
        except ReceiptTimeout as e:
            tx, r = None, {"status": "NO_RECEIPT", "error": str(e)[:300], "done_at": time.time()}
            log(f"[{case}]   sent, but no receipt: {str(e)[:120]} (not sent again)")
            break
        except Exception as e:
            tx, r = None, {"status": "SEND_FAILED", "error": str(e)[:300], "done_at": time.time()}
            log(f"[{case}]   send failed ({str(e)[:80]}); " + ("retrying in 15 s" if fn == "read_record" and attempt < 2 else "not retried"))
            time.sleep(15 if fn == "read_record" else 0)
    entry = {"case": case, "at": utc(), "from": REC["accounts"][role], "fn": fn, "args": fargs, "value": str(value), "tx": tx,
             **{k: v for k, v in r.items() if k != "votes"}}
    if r.get("votes"):
        entry["votes"] = r["votes"]
    if expect:
        entry["expect"] = expect
    with LOCK:
        REC["steps"].append(entry)
    save()
    res = r.get("result")
    brief = res.get("reading") if isinstance(res, dict) and "reading" in res else (res.get("error") if isinstance(res, dict) and "error" in res else "")
    log(f"[{case}]   -> {r.get('status')} / {r.get('execution')} {json.dumps(brief, default=str)[:160]}")
    return tx, r


def state_of(addr, aid):
    try:
        return view(addr, "get_auction", [aid])["state"]
    except Exception as e:
        log(f"  could not read auction {aid}: {str(e)[:100]}")
        return "UNKNOWN"


def run_case(i, case, addr, aid):
    key, who = case["key"], reader(i)
    off = i * 8
    reads = [D + 60 * m + off for m in TM["reads"][: case["reads"]]]
    last = [0.0]

    def rd(at, why):
        until(at)
        _tx, r = step(key, who, addr, "read_record", [aid], expect=why)
        last[0] = r.get("done_at", time.time())

    rd(reads[0], "round 1")
    rd(max(reads[1], last[0] + C + 60), "round 2")
    if state_of(addr, aid) not in (case["expect"]["after_first"], "SETTLED"):
        rd(max(D + 60 * TM["spares"][0] + off, last[0] + C + 60), f"spare: not yet {case['expect']['after_first']}")
    if case["reads"] == 4:
        rd(max(reads[2], last[0] + 60), "round 3")
        rd(max(reads[3], last[0] + C + 60), "round 4")
        if state_of(addr, aid) != "SETTLED":
            rd(max(D + 60 * TM["spares"][1] + off, last[0] + C + 60), "spare: not yet settled")
    if case.get("settle"):
        until(D + 60 * TM["settle"] + off)
        if state_of(addr, aid) != "SETTLED":
            step(key, who, addr, "settle", [aid], expect=case["expect"]["reason"])


def check(addr):
    """Every case against its expected outcome."""
    out, ok = {}, True
    for case in CASES:
        a = view(addr, "get_auction", [REC["auctions"][case["key"]]["id"]])
        dep = int(a["terms"]["deposit"])
        x = case["expect"]
        want = {"state": "SETTLED", "reason": x["reason"], "to_creditor": dep * len(x["to_creditor"]),
                "refunded": dep * (3 - len(x["to_creditor"])), "held": 0}
        got = {"state": a["state"], "reason": a["settled_reason"], "to_creditor": int(a["money"]["to_creditor"]),
               "refunded": int(a["money"]["refunded"]), "held": int(a["money"]["held"])}
        out[case["key"]] = {"pass": got == want, "got": got, "want": want, "winner": a["winner"], "readings": a["readings"]}
        ok &= got == want
        log(f"[{case['key']}] {'PASS' if got == want else 'FAIL'} {got['state']} '{got['reason']}'")
    return ok, out


def main():
    make_accounts()
    save()
    acc = REC["accounts"]
    addr = opt("--contract")
    if not addr:
        # Bradbury: the packed build (port.py --pack), well under the deploy gas cap
        path = ROOT / ("bradbury/build/auction_deposit_packed.py" if BB else "contracts/auction_deposit.py")
        tx, addr = deploy("creditor", path, [json.dumps([HOST]), C])
        REC["contract"] = {"address": addr, "deploy_tx": tx}
        log(f"AuctionDeposit deployed at {addr} ({tx})")
    else:
        REC["contract"] = {"address": addr, **({"deploy_tx": opt("--deploy-tx")} if opt("--deploy-tx") else {})}
    save()
    c0 = CASES[0]
    t0 = mr.terms(c0, D, NET)
    step("refused open", "creditor", addr, "open_auction", [t0["auction_id"], t0["property_ref"], "https://auctions.example.com/auction/ea-24117.html",
         t0["deposit"], C, D, t0["balance_seconds"], t0["refund_by"]], expect="error: host not on the frozen list")
    for case in CASES:
        t = mr.terms(case, D, NET)
        url = f"{SITE}/" + mr.page_path(TAG, case)
        step(case["key"], "creditor", addr, "open_auction", [t["auction_id"], t["property_ref"], url, t["deposit"], C, D,
             t["balance_seconds"], t["refund_by"]], expect="auction opened")
        ids = view(addr, "get_auctions_of", [acc["creditor"]])
        a = view(addr, "get_auction", [ids[-1]])
        if a["terms"]["auction_id"] != case["auction_id"]:
            a = next(b for b in (view(addr, "get_auction", [x]) for x in reversed(ids)) if b["terms"]["auction_id"] == case["auction_id"])
        aid = a["id"]
        REC["auctions"][case["key"]] = {"id": aid, "digest": a["digest"], "deposit": str(t["deposit"]), "url": url, "title": case["title"]}
        save()

    def lodge(b):
        role = ROLES[1 + b]
        for i, case in enumerate(CASES):
            au = REC["auctions"][case["key"]]
            if i == 0 and b == 0:
                step(case["key"], role, addr, "deposit", [au["id"], case["bidders"][b], au["digest"]], value=int(au["deposit"]) - 1,
                     expect="refused: not exactly the deposit (credited back)")
            step(case["key"], role, addr, "deposit", [au["id"], case["bidders"][b], au["digest"]], value=int(au["deposit"]), expect="deposit lodged")

    threads = [threading.Thread(target=lodge, args=(b,)) for b in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    missing = []
    for case in CASES:
        a = view(addr, "get_auction", [REC["auctions"][case["key"]]["id"]])
        missing += [f"{case['key']}:{c}" for c in case["bidders"] if c not in a["bidders"]]
    if missing:
        log(f"STOP: deposits missing {missing}")
        REC["stopped"] = f"deposits missing {missing}"
        save()
        sys.exit(2)
    log(f"all 30 deposits registered; {int(D - time.time())} s before deposits close")
    threads = [threading.Thread(target=run_case, args=(i, case, addr, REC["auctions"][case["key"]]["id"])) for i, case in enumerate(CASES)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    still = [c for c in CASES if state_of(addr, REC["auctions"][c["key"]]["id"]) != "SETTLED"]
    if still:
        log(f"still open: {[c['key'] for c in still]}; final settle at D + {TM['final_settle']} min")
        until(D + 60 * TM["final_settle"])
        for c in still:
            step(c["key"], "creditor", addr, "settle", [REC["auctions"][c["key"]]["id"]], expect="final settle")
    for role in ROLES:
        if int(view(addr, "get_claimable", [acc[role]])) > 0:
            step("withdraw", role, addr, "withdraw", [0], payees=acc[role] if BB else "")
    ok, cases = check(addr)
    final = {"all_pass": ok, "cases": cases, "totals": view(addr, "totals", []), "balance": str(balance(addr)),
             "claimable": {r: view(addr, "get_claimable", [acc[r]]) for r in ROLES}}
    REC["final"] = final
    save()
    log(f"{'ALL CASES PASS' if ok else 'SOME CASES FAIL'}; balance {final['balance']} vs totals {final['totals']}")
    log(f"record written to {REC_PATH}")


if __name__ == "__main__":
    main()
