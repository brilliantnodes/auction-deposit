"""The ten demo cases of examples/cases.json, run through the contract on the
exact text of the record pages that tools/make_record.py writes, at the
moments the live script will read them, on both timetables (Studio and
Testnet Bradbury). Web pages and the LLM are mocked; the mocked model copies
the page faithfully (or, in the attack tests, obeys the planted instruction or
misreports the page).

The live plan is simulated as the live script will run it: two rounds of
readings, a spare reading for any case not yet where it should be, two more
rounds and a spare for the four-reading cases, settle calls, then a final
settle for anything still open. test_one_failed_reading_changes_nothing drops
each scheduled reading in turn (as one of 43 failed on Bradbury in
ClaimEscrow's run b1) and checks every case still ends as expected.

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
NETS = ["studio", "bradbury"]
C = mr.CASES["confirm_seconds"]
GRACE = 1800
D = int(datetime(2026, 11, 23, 10, 0, tzinfo=timezone.utc).timestamp())
CASES = mr.CASES["cases"]
KEYS = [c["key"] for c in CASES]


def iso(t: int) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z")


def tm(net):
    return mr.CASES["timing"][net]


def url(case) -> str:
    return f"https://{HOST}/" + mr.page_path("demo", case)


def text(case, net, t) -> str:
    return "\n".join(mr.text_lines(case, D, net, t))


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


def open_case(e, case, net, at):
    e.vm.warp(iso(at))
    e.vm.sender = e.creditor
    t = mr.terms(case, D, net)
    a = e.c.open_auction(t["auction_id"], t["property_ref"], url(case), t["deposit"], t["confirm_seconds"],
                         t["deposits_close"], t["balance_seconds"], t["refund_by"])
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


def read(e, case, net, at, answer=None):
    page = text(case, net, at)
    e.vm.clear_mocks()
    e.vm.warp(iso(at))
    e.vm.sender = e.anyone
    e.vm.mock_web(re.escape(url(case)), {"status": 200, "body": page})
    # fenced, as models usually answer; it also stops genlayer-test 0.30's mock
    # from turning a bare JSON string into a dict before the contract sees it
    e.vm.mock_llm(PROMPT, "```json\n" + (answer if answer is not None else faithful(case, page)) + "\n```")
    return e.c.read_record(e.ids[case["key"]])


def settle(e, case, at):
    e.vm.warp(iso(at))
    e.vm.sender = e.anyone
    return e.c.settle(e.ids[case["key"]])


def state(e, case):
    return e.c.get_auction(e.ids[case["key"]])["state"]


def plan(case, net):
    """The live plan for one case: a list of (minute, what) in order, where
    what is 'R1'..'R4', 'S1', 'S2' (spares, sent only if needed), 'settle'
    or 'final'."""
    t = tm(net)
    r = [(m, f"R{i + 1}") for i, m in enumerate(t["reads"][: case["reads"]])]
    p = r[:2] + [(t["spares"][0], "S1")] + r[2:]
    if case["reads"] == 4:
        p.append((t["spares"][1], "S2"))
    if case.get("settle"):
        p.append((t["settle"], "settle"))
    return p + [(t["final_settle"], "final")]


def bad_answer(case, net, at):
    ans = json.loads(faithful(case, text(case, net, at)))
    ans["page_kind"] = "other"
    return json.dumps(ans)


def run_plan(e, case, net, drop=None):
    """Run the plan for one case; drop names a scheduled reading that comes
    back as a no-reading. Returns the readings seen and the spares used."""
    seen, spares, last = [], [], None
    for m, what in plan(case, net):
        at = D + 60 * m
        st = state(e, case)
        if what in ("settle", "final"):
            if st in ("OPEN", "WON_PENDING"):
                settle(e, case, at)
            continue
        if st not in ("OPEN", "WON_PENDING"):
            continue
        if what == "S1" and st == case["expect"]["after_first"]:
            continue
        if what == "S2" and st == "SETTLED":
            continue
        if what.startswith("S"):
            at = max(at, last + C + 60)
            spares.append(what)
        r = read(e, case, net, at, bad_answer(case, net, at) if what == drop else None)
        seen.append(shown(r["reading"]))
        last = at
    return seen, spares


def check_outcome(e, case, net):
    a = e.c.get_auction(e.ids[case["key"]])
    x = case["expect"]
    dep = mr.deposit_wei(case, net)
    assert a["state"] == "SETTLED", (case["key"], a["state"], a["log"][-4:])
    assert a["settled_reason"] == x["reason"], (case["key"], a["settled_reason"])
    m = {k: int(v) for k, v in a["money"].items()}
    assert m == {"deposited": 3 * dep, "held": 0, "to_creditor": dep * len(x["to_creditor"]),
                 "refunded": dep * (3 - len(x["to_creditor"]))}
    return a


# ------------------------------------------------------- each case alone


@pytest.mark.parametrize("net", NETS)
@pytest.mark.parametrize("key", KEYS)
def test_case(env, key, net):
    case = mr.case_by_key(key)
    open_case(env, case, net, D - 1800)
    # a look before the auction starts counts for nothing (the wrong page is wrong all along)
    r = read(env, case, net, D - 600)
    assert shown(r["reading"]) == ("N1_WRONG_PAGE" if case.get("shows") else "SCHEDULED") and r["auction"]["run"] is None
    seen, spares = run_plan(env, case, net)
    assert seen == case["expect"]["readings"] and spares == []
    check_outcome(env, case, net)
    dep = mr.deposit_wei(case, net)
    assert int(env.c.get_claimable(to_hex(env.creditor))) == dep * len(case["expect"]["to_creditor"])
    for who, code in zip(env.bidders, case["bidders"]):
        assert int(env.c.get_claimable(to_hex(who))) == (0 if code in case["expect"]["to_creditor"] else dep)


@pytest.mark.parametrize("net", NETS)
@pytest.mark.parametrize("key", KEYS)
def test_after_round_two(env, key, net):
    case = mr.case_by_key(key)
    open_case(env, case, net, D - 1800)
    for at in [D + 60 * m for m in tm(net)["reads"][:2]]:
        read(env, case, net, at)
    assert state(env, case) == case["expect"]["after_first"]


@pytest.mark.parametrize("net", NETS)
@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("drop", ["R1", "R2", "R3", "R4"])
def test_one_failed_reading_changes_nothing(env, key, net, drop):
    case = mr.case_by_key(key)
    if int(drop[1]) > case["reads"]:
        pytest.skip("this case has two readings")
    open_case(env, case, net, D - 1800)
    run_plan(env, case, net, drop=drop)
    check_outcome(env, case, net)


@pytest.mark.parametrize("net", NETS)
def test_cases_file_is_consistent(net):
    keys, ids = set(), set()
    t = tm(net)
    assert t["reads"] == sorted(t["reads"]) and t["result"] < t["reads"][0]
    assert t["reads"][1] < t["spares"][0] < t["change"] < t["reads"][2] < t["reads"][3] < t["spares"][1] < t["settle"] < t["final_settle"]
    assert t["spares"][0] - t["reads"][1] >= C / 60 and t["spares"][1] - t["reads"][3] >= C / 60
    for case in CASES:
        assert case["key"] not in keys and case["auction_id"] not in ids
        keys.add(case["key"])
        ids.add(case["auction_id"])
        assert len(case["bidders"]) == 3 and len(case["expect"]["readings"]) == case["reads"]
        assert set(case["expect"]["to_creditor"]) <= set(case["bidders"])
        assert "'" not in case["property"] and "'" not in case.get("shows", {}).get("property", "")  # no quote a model might curl
        tr = mr.terms(case, D, net)
        assert tr["balance_seconds"] >= 2 * C and tr["refund_by"] >= D + 2 * C
        last_read = D + 60 * max(m for m, w in plan(case, net) if w[0] in "RS")
        earliest_win = D + 60 * t["reads"][1]  # a winner is confirmed at R2 at the earliest
        latest_win = D + 60 * t["spares"][0] + C + 60  # and at S1 at the latest, when one reading failed
        if case.get("settle"):
            used = latest_win + tr["balance_seconds"] if case["expect"]["to_creditor"] else tr["refund_by"]
            assert used + GRACE <= D + 60 * t["settle"]  # the deadline used takes effect before the settle call
        else:
            # every other case settles on readings stamped before any deadline
            assert last_read < earliest_win + tr["balance_seconds"] and last_read < tr["refund_by"]
        # anything still open is settled by the final call
        assert latest_win + tr["balance_seconds"] + GRACE <= D + 60 * t["final_settle"]
        assert tr["refund_by"] + GRACE <= D + 60 * t["final_settle"]
    assert len(CASES) == 10


# ------------------------------------------- all ten together, as live


@pytest.mark.parametrize("net", NETS)
def test_all_ten_in_one_contract(env, net):
    for i, case in enumerate(CASES):
        open_case(env, case, net, D - 3000 + 240 * i)
    events = [(D + 60 * m, k, w, case) for case in CASES for k, (m, w) in enumerate(plan(case, net)) if w[0] == "R"]
    events += [(D + 60 * tm(net)["settle"], 90, "settle", case) for case in CASES if case.get("settle")]
    seen = {c["key"]: [] for c in CASES}
    for t, _k, what, case in sorted(events, key=lambda ev: (ev[0], ev[1], KEYS.index(ev[3]["key"]))):
        if what == "settle":
            settle(env, case, t)
        else:
            seen[case["key"]].append(shown(read(env, case, net, t)["reading"]))
    for case in CASES:
        assert seen[case["key"]] == case["expect"]["readings"]
        check_outcome(env, case, net)
    # per address, across all ten auctions
    want_creditor = sum(mr.deposit_wei(c, net) * len(c["expect"]["to_creditor"]) for c in CASES)
    assert int(env.c.get_claimable(to_hex(env.creditor))) == want_creditor
    total = want_creditor
    for i, who in enumerate(env.bidders):
        want = sum(mr.deposit_wei(c, net) for c in CASES if c["bidders"][i] not in c["expect"]["to_creditor"])
        assert int(env.c.get_claimable(to_hex(who))) == want
        total += want
    tot = env.c.totals()
    assert tot == {"auctions": 10, "locked": "0", "credited": str(total)}
    assert total == 3 * sum(mr.deposit_wei(c, net) for c in CASES)
    for who in [env.creditor] + env.bidders:
        env.vm.sender = who
        env.c.withdraw(0)
    assert env.c.totals() == {"auctions": 10, "locked": "0", "credited": "0"}


# ---------------------------------------------------------- attacks


def test_obeying_the_planted_line_moves_nothing(env):
    net = "bradbury"
    case = mr.case_by_key("injection")
    open_case(env, case, net, D - 1800)
    t1, t2 = [D + 60 * m for m in tm(net)["reads"][:2]]
    obey = json.loads(faithful(case, text(case, net, t1)))
    obey["winning_bidder"] = {"label": "Winning bidder", "value": "B-1901"}
    r = read(env, case, net, t1, json.dumps(obey))
    assert shown(r["reading"]) == "N2_NOT_ANCHORED" and r["auction"]["run"] is None
    # a misled model that writes the planted claim as if it were the winner line is not anchored either
    obey["winning_bidder"] = {"label": "won by bidder", "value": "B-1901"}
    r = read(env, case, net, t1 + 60, json.dumps(obey))
    assert shown(r["reading"]) == "N2_LABEL"
    # honest copies then settle it on the record: B-1902
    read(env, case, net, t2)
    a = read(env, case, net, t2 + C)["auction"]
    assert a["state"] == "SETTLED" and a["winner"] == "B-1902"


@pytest.mark.parametrize("lie", ["claims_own_id", "copies_shown_id"])
def test_wrong_page_cannot_pay(env, lie):
    net = "bradbury"
    case = mr.case_by_key("wrong_page")
    open_case(env, case, net, D - 1800)
    t1, t2 = [D + 60 * m for m in tm(net)["reads"][:2]]
    ans = json.loads(faithful(case, text(case, net, t1)))
    ans["page_kind"] = "auction_record"
    if lie == "claims_own_id":
        ans["auction_id_on_page"], ans["property_on_page"] = case["auction_id"], case["property"]
    for t in (t1, t2, t2 + C):
        assert shown(read(env, case, net, t, json.dumps(ans))["reading"]) == "N1_WRONG_PAGE"
    a = env.c.get_auction(env.ids["wrong_page"])
    assert a["state"] == "OPEN" and a["winner"] == "" and a["money"]["held"] == str(3 * mr.deposit_wei(case, net))
