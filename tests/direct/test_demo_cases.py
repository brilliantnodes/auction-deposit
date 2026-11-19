"""The ten demo cases of examples/cases.json, run through the contract on the
exact text of the record pages that tools/make_record.py writes, at the
moments the live script will read them. Web pages and the LLM are mocked; the
mocked model copies the page faithfully (or, in the attack tests, obeys the
planted instruction or misreports the page).

Every platform, creditor, auction, property and bidder here is fictional.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.direct.conftest import to_hex

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import make_record as mr  # noqa: E402

CONTRACT = os.environ.get("AD_CONTRACT", "contracts/auction_deposit.py")
HOST = "auctions.example.org"
PROMPT = r"(?s).*official record page.*"
NET = "studio"
TM = mr.CASES["timing"][NET]
C = mr.CASES["confirm_seconds"]
D = int(datetime(2026, 11, 23, 10, 0, tzinfo=timezone.utc).timestamp())
CASES = mr.CASES["cases"]
KEYS = [c["key"] for c in CASES]


def iso(t: int) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z")


def url(case) -> str:
    return f"https://{HOST}/" + mr.page_path("demo", case)


def text(case, t) -> str:
    return "\n".join(mr.text_lines(case, D, NET, t))


def faithful(case, page: str) -> str:
    """What a model that copies correctly answers."""
    kv = {}
    for ln in page.splitlines():
        if ": " in ln:
            k, v = ln.split(": ", 1)
            kv.setdefault(k, v)

    def f(label):
        v = kv.get(label, "-")
        return {"label": "", "value": ""} if v in ("", "-") else {"label": label, "value": v}

    return json.dumps({
        "page_kind": "auction_record" if kv.get("Auction") == case["auction_id"] else "other",
        "auction_id_on_page": kv.get("Auction", ""), "property_on_page": kv.get("Property", ""),
        "other_auctions_shown": "no", "status": {"label": "Status", "value": kv["Status"]},
        "winning_bidder": f("Winning bidder"), "balance": f("Balance"),
    })


def shown(r: dict) -> str:
    if r["kind"] == "NO_READING":
        return r["reason"]
    return " ".join(x for x in (r["status"], r["winner"], r["balance"]) if x)


@pytest.fixture
def env(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    direct_vm.warp(iso(D - 3600))
    c = direct_deploy(CONTRACT, json.dumps([HOST]), C)

    class E:
        pass

    e = E()
    e.vm, e.c = direct_vm, c
    e.creditor = direct_alice
    e.bidders = [direct_bob, direct_charlie, bytes.fromhex("44" * 20)]
    e.anyone = bytes.fromhex("55" * 20)
    e.ids = {}
    return e


def open_case(e, case, at):
    e.vm.warp(iso(at))
    e.vm.sender = e.creditor
    t = mr.terms(case, D, NET)
    a = e.c.open_auction(t["auction_id"], t["property_ref"], url(case), t["deposit"], t["confirm_seconds"],
                         t["deposits_close"], t["balance_by"], t["refund_by"])
    e.ids[case["key"]] = a["id"]
    for i, (who, code) in enumerate(zip(e.bidders, case["bidders"])):
        e.vm.warp(iso(at + 60 * (i + 1)))
        e.vm.sender = who
        e.vm.value = t["deposit"]
        try:
            assert e.c.deposit(a["id"], code, a["digest"])["ok"]
        finally:
            e.vm.value = 0
    return a["id"]


def read(e, case, at, answer=None):
    page = text(case, at)
    e.vm.clear_mocks()
    e.vm.warp(iso(at))
    e.vm.sender = e.anyone
    e.vm.mock_web(re.escape(url(case)), {"status": 200, "body": page})
    e.vm.mock_llm(PROMPT, answer if answer is not None else faithful(case, page))
    return e.c.read_record(e.ids[case["key"]])


def settle(e, case, at):
    e.vm.warp(iso(at))
    e.vm.sender = e.anyone
    return e.c.settle(e.ids[case["key"]])


def read_times(case) -> list:
    return [D + 60 * m for m in TM["reads"][: case["reads"]]]


def check_outcome(e, case):
    a = e.c.get_auction(e.ids[case["key"]])
    x = case["expect"]
    dep = mr.deposit_wei(case, NET)
    assert a["state"] == "SETTLED", (case["key"], a["state"], a["log"][-4:])
    assert a["settled_reason"] == x["reason"]
    m = {k: int(v) for k, v in a["money"].items()}
    assert m == {"deposited": 3 * dep, "held": 0, "to_creditor": dep * len(x["to_creditor"]),
                 "refunded": dep * (3 - len(x["to_creditor"]))}
    return a


# ------------------------------------------------------- each case alone


@pytest.mark.parametrize("key", KEYS)
def test_case(env, key):
    case = mr.case_by_key(key)
    open_case(env, case, D - 1800)
    # a look before the auction starts counts for nothing (the wrong page is wrong all along)
    r = read(env, case, D - 600)
    assert shown(r["reading"]) == ("N1_WRONG_PAGE" if case.get("shows") else "SCHEDULED") and r["auction"]["run"] is None
    got = [shown(read(env, case, t)["reading"]) for t in read_times(case)]
    assert got == case["expect"]["readings"]
    if case.get("settle"):
        assert env.c.get_auction(env.ids[key])["state"] != "SETTLED"
        settle(env, case, D + 60 * TM["settle"])
    check_outcome(env, case)
    dep = mr.deposit_wei(case, NET)
    assert int(env.c.get_claimable(to_hex(env.creditor))) == dep * len(case["expect"]["to_creditor"])
    for who, code in zip(env.bidders, case["bidders"]):
        assert int(env.c.get_claimable(to_hex(who))) == (0 if code in case["expect"]["to_creditor"] else dep)


def test_cases_file_is_consistent():
    keys, ids = set(), set()
    for case in CASES:
        assert case["key"] not in keys and case["auction_id"] not in ids
        keys.add(case["key"])
        ids.add(case["auction_id"])
        assert len(case["bidders"]) == 3 and len(case["expect"]["readings"]) == case["reads"]
        assert set(case["expect"]["to_creditor"]) <= set(case["bidders"])
        t = mr.terms(case, D, NET)
        assert t["balance_by"] >= D + 2 * C and t["refund_by"] >= t["balance_by"] + 2 * C
        if case.get("settle"):
            # the deadline used takes effect before the settle call
            used = t["balance_by"] if case["expect"]["to_creditor"] else t["refund_by"]
            assert used + 1800 <= D + 60 * TM["settle"]
        else:
            # every other case settles on readings, well before any deadline takes effect
            assert t["balance_by"] > D + 60 * max(TM["reads"]) and t["refund_by"] > t["balance_by"]
    assert len(CASES) == 10


# ------------------------------------------- all ten together, as live


def test_all_ten_in_one_contract(env):
    for i, case in enumerate(CASES):
        open_case(env, case, D - 3000 + 240 * i)
    events = [(t, 0, case) for case in CASES for t in read_times(case)]
    events += [(D + 60 * TM["settle"], 1, case) for case in CASES if case.get("settle")]
    seen = {c["key"]: [] for c in CASES}
    for t, kind, case in sorted(events, key=lambda ev: (ev[0], ev[1], KEYS.index(ev[2]["key"]))):
        if kind == 0:
            seen[case["key"]].append(shown(read(env, case, t)["reading"]))
        else:
            settle(env, case, t)
    for case in CASES:
        assert seen[case["key"]] == case["expect"]["readings"]
        check_outcome(env, case)
    # per address, across all ten auctions
    want_creditor = sum(mr.deposit_wei(c, NET) * len(c["expect"]["to_creditor"]) for c in CASES)
    assert int(env.c.get_claimable(to_hex(env.creditor))) == want_creditor
    total = want_creditor
    for i, who in enumerate(env.bidders):
        want = sum(mr.deposit_wei(c, NET) for c in CASES if c["bidders"][i] not in c["expect"]["to_creditor"])
        assert int(env.c.get_claimable(to_hex(who))) == want
        total += want
    tot = env.c.totals()
    assert tot == {"auctions": 10, "locked": "0", "credited": str(total)}
    assert total == 3 * sum(mr.deposit_wei(c, NET) for c in CASES)
    for who in [env.creditor] + env.bidders:
        env.vm.sender = who
        env.c.withdraw(0)
    assert env.c.totals() == {"auctions": 10, "locked": "0", "credited": "0"}


# ---------------------------------------------------------- attacks


def test_obeying_the_planted_line_moves_nothing(env):
    case = mr.case_by_key("injection")
    open_case(env, case, D - 1800)
    t1, t2 = read_times(case)
    obey = json.loads(faithful(case, text(case, t1)))
    obey["winning_bidder"] = {"label": "Winning bidder", "value": "B-1901"}
    r = read(env, case, t1, json.dumps(obey))
    assert shown(r["reading"]) == "N2_NOT_ANCHORED" and r["auction"]["run"] is None
    # a misled model that writes the planted claim as if it were the winner line is not anchored either
    obey["winning_bidder"] = {"label": "won by bidder", "value": "B-1901"}
    r = read(env, case, t1 + 60, json.dumps(obey))
    assert shown(r["reading"]) == "N2_LABEL"
    # honest copies then settle it on the record: B-1902
    read(env, case, t2)
    a = read(env, case, t2 + C)["auction"]
    assert a["state"] == "SETTLED" and a["winner"] == "B-1902"


@pytest.mark.parametrize("lie", ["claims_own_id", "copies_shown_id"])
def test_wrong_page_cannot_pay(env, lie):
    case = mr.case_by_key("wrong_page")
    open_case(env, case, D - 1800)
    t1, t2 = read_times(case)
    ans = json.loads(faithful(case, text(case, t1)))
    ans["page_kind"] = "auction_record"
    if lie == "claims_own_id":
        ans["auction_id_on_page"], ans["property_on_page"] = case["auction_id"], case["property"]
    for t in (t1, t2, t2 + C):
        assert shown(read(env, case, t, json.dumps(ans))["reading"]) == "N1_WRONG_PAGE"
    a = env.c.get_auction(env.ids["wrong_page"])
    assert a["state"] == "OPEN" and a["winner"] == "" and a["money"]["held"] == str(3 * mr.deposit_wei(case, NET))
