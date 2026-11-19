"""More direct-mode tests for AuctionDeposit: one or more for every break the
first mutation check (tools/mutate.py, 19 Nov 2026) found the tests did not
catch. Web pages and the LLM are mocked.

Every auction, creditor, property and bidder here is fictional.
"""

import json
import re

import pytest

from tests.direct.test_auction_deposit import (  # noqa: F401  (env and mod are fixtures)
    AID, C, CLOSE, CONTRACT, DEP, GRACE, HOST, PROMPT, PROP, REFUND_BY, T0, URL,
    answer, claim, dep, env, iso, mod, open_, page, read, ready, rec, reconciled, twice,
)
from tests.direct.conftest import to_hex


def reading(e, pg, ans, at=CLOSE + 100):
    return read(e, (pg, ans), at)["reading"]


def no_reading(reason):
    return {"kind": "NO_READING", "reason": reason}


def status_line(pg, new):
    """Replace the page's status line with other line(s)."""
    lines = pg.split("\n")
    i = next(k for k, ln in enumerate(lines) if ln.startswith("Status: "))
    return "\n".join(lines[:i] + new.split("\n") + lines[i + 1:])


# ------------------------------------------------------- deployment and terms


def test_duplicate_hosts_refused(direct_vm, direct_deploy):
    direct_vm.warp(iso(T0))
    with pytest.raises(Exception, match="1 to 8"):
        direct_deploy(CONTRACT, json.dumps([HOST, HOST]), C)


@pytest.mark.parametrize("over,msg", [
    (dict(record_url=f"https://{HOST}:8443/auction/EA-24117"), "port"),
    (dict(record_url=f"https://user@{HOST}/auction/EA-24117"), "port"),
    (dict(property_ref="Unit 4B\x07, 12 Larkspur Row"), "plain text on one line"),
])
def test_open_refuses_more(env, over, msg):
    with pytest.raises(Exception, match=msg):
        open_(env, **over)


# ------------------------------------------------------------------ deposits


def test_bidder_code_longest_and_too_long(env):
    open_(env)
    assert dep(env, env.b1, "B" * 24)["ok"]
    r = dep(env, env.b2, "B" * 25)
    assert not r["ok"] and "bidder_code" in r["error"] and claim(env, env.b2) == DEP


def test_deposit_into_a_cancelled_auction_refused(env):
    ready(env)
    env.vm.sender = env.creditor
    env.vm.warp(iso(T0 + 500))
    env.c.cancel_auction("1")
    r = dep(env, bytes.fromhex("66" * 20), "B-104", at=T0 + 600)
    assert not r["ok"] and "CANCELLED" in r["error"] and claim(env, bytes.fromhex("66" * 20)) == DEP
    a, m = reconciled(env)
    assert m["held"] == 0 and "B-104" not in a["bidders"]


def test_bidder_limit(env, mod):
    open_(env)
    for i in range(mod.MAX_BIDDERS):
        assert dep(env, bytes.fromhex(f"{0x1000 + i:040x}"), f"B-{i}", at=T0 + 300 + i)["ok"]
    r = dep(env, bytes.fromhex(f"{0x2000:040x}"), "B-999", at=T0 + 900)
    assert not r["ok"] and "at most" in r["error"]


def test_bidder_is_indexed(env):
    ready(env)
    assert env.c.get_auctions_of(to_hex(env.b1)) == ["1"] and env.c.get_auctions_of(to_hex(env.b3)) == ["1"]


# ------------------------------------------------------------ run and clock


def test_confirmation_clears_the_run_and_stamps_the_winner(env):
    ready(env)
    a = twice(env, rec("Completed", "B-102", "Pending"), CLOSE + 100)["auction"]
    assert a["state"] == "WON_PENDING" and a["run"] is None and a["winner_at"] == CLOSE + 100 + C


def test_refund_deadline_takes_effect_after_grace(env):
    ready(env)
    env.vm.warp(iso(REFUND_BY + GRACE - 1))
    assert env.c.settle("1")["state"] == "OPEN"
    env.vm.warp(iso(REFUND_BY + GRACE))
    assert env.c.settle("1")["state"] == "SETTLED"


def test_clock_never_runs_backwards(env):
    ready(env)
    read(env, rec("Scheduled"), CLOSE + 60)
    # a call stamped before deposits closed, processed after a later one, cannot lodge a deposit
    r = dep(env, bytes.fromhex("66" * 20), "B-104", at=CLOSE - 60)
    assert not r["ok"] and "deposits are closed" in r["error"]


# ------------------------------------------------------------ reading rules


def test_property_must_be_on_the_page(env):
    ready(env)
    pg = page("Suspended").replace(PROP, "Unit 4C, 12 Larkspur Row, Velmora")
    assert reading(env, pg, answer("Suspended")) == no_reading("N1_WRONG_PAGE")


def test_auction_id_must_be_a_whole_token_before_too(env, mod):
    for txt in ("auction: xea-24117", "auction: lot-ea-24117", "auction: lots/ea-24117", "auction: a.ea-24117"):
        assert not mod._token_on_page(txt, AID), txt
    assert mod._token_on_page("auction: ea-24117", AID) and mod._token_on_page("ea-24117 (online)", AID)


def test_balance_shown_on_a_cancelled_auction_is_a_contradiction(env):
    ready(env)
    pg = page("Cancelled", balance="Paid in full")
    ans = answer("Cancelled", balance={"label": "Balance", "value": "Paid in full"})
    assert reading(env, pg, ans) == no_reading("N2_AMBIGUOUS")


def test_balance_must_be_anchored(env):
    ready(env)
    pg = page("Completed", "B-101", "Awaiting payment")
    assert reading(env, pg, answer("Completed", "B-101", "Paid in full")) == no_reading("N2_NOT_ANCHORED")


@pytest.mark.parametrize("extra", ["Winner: B-103", "Balance status: Paid in full"])
def test_a_second_winner_or_balance_line_is_ambiguous(env, extra):
    ready(env)
    pg = page("Completed", "B-101", "Pending", extra=extra)
    assert reading(env, pg, answer("Completed", "B-101", "Pending")) == no_reading("N2_AMBIGUOUS")


def test_a_qualified_winner_line_is_ambiguous(env):
    ready(env)
    pg = page("Completed", "B-101", "Pending").replace("Winning bidder: B-101", "Winning bidder: B-101\n(subject to appeal)")
    assert reading(env, pg, answer("Completed", "B-101", "Pending")) == no_reading("N2_AMBIGUOUS")


def test_a_qualified_balance_line_is_ambiguous(env):
    ready(env)
    pg = page("Completed", "B-101", "Paid in full", extra="(partial payment received)")
    assert reading(env, pg, answer("Completed", "B-101", "Paid in full")) == no_reading("N2_AMBIGUOUS")


@pytest.mark.parametrize("status,want", [
    ("Not sold", "UNCLEAR"), ("Sold out of time", "UNCLEAR"), ("Cancelled.", "CANCELLED"),
    ("SUSPENDED BY COURT ORDER", "SUSPENDED"), ("Unsuccessful — no bidders", "NO_BIDDERS"),
    ("Unsuccessful ‒ no bidders", "NO_BIDDERS"), ("Unsuccessful ― no bidders", "NO_BIDDERS"),
])
def test_status_is_a_whole_phrase(env, status, want):
    ready(env)
    r = reading(env, page(status), answer(status))
    assert r == {"kind": "READ", "status": want, "winner": "", "balance": ""}


@pytest.mark.parametrize("balance,want", [("Not paid", "UNCLEAR"), ("Paid in full.", "PAID_IN_FULL"), ("Due by 30 Nov", "UNCLEAR")])
def test_balance_is_a_whole_phrase(env, balance, want):
    ready(env)
    r = reading(env, page("Completed", "B-101", balance), answer("Completed", "B-101", balance))
    assert r == {"kind": "READ", "status": "COMPLETED", "winner": "B-101", "balance": want}


def test_labels_copied_with_colons(env):
    ready(env)
    ans = answer("Completed", "B-101", "Pending", status={"label": "Status:", "value": "Completed"},
                 winning_bidder={"label": "Winning bidder:", "value": "B-101"}, balance={"label": "Balance :", "value": "Pending"})
    r = reading(env, page("Completed", "B-101", "Pending"), ans)
    assert r == {"kind": "READ", "status": "COMPLETED", "winner": "B-101", "balance": "PENDING"}


@pytest.mark.parametrize("lines,value,want", [
    ("Status: Cancelled order reversed, completed", "Cancelled", "N2_NOT_ANCHORED"),  # part of the line only
    ("Previous status: Cancelled", "Cancelled", "N2_NOT_ANCHORED"),  # the label after other words
    ("Statuses: Cancelled", "Cancelled", "N2_NOT_ANCHORED"),  # the label inside a longer word
    ("Status:\n\nCancelled", "Cancelled", "N2_NOT_ANCHORED"),  # the value two line breaks away
    ("Status:" + "-" * 79 + " Cancelled", "Cancelled", "N2_NOT_ANCHORED"),  # 81 characters away
    ("Status: formerly Cancelled", "Cancelled", "N2_NOT_ANCHORED"),  # words between label and value
    ("• Status: Cancelled", "Cancelled", "CANCELLED"),  # a bullet before the label is fine
    ("Status:\nCancelled", "Cancelled", "CANCELLED"),  # one line break is fine
    ("Status:" + "-" * 78 + " Cancelled", "Cancelled", "CANCELLED"),  # 80 characters away is fine
    ("Status: Cancelled\nStatus history: see the notary's file", "Cancelled", "CANCELLED"),  # a longer label is not a label line
    ("Status: Cancelled\nStatus = Completed", "Cancelled", "N2_AMBIGUOUS"),  # a second status line written with =
    ("Status: Cancelled\n(see note 3)", "Cancelled", "N2_AMBIGUOUS"),  # a bracket on the next line
    ("Status: Cancelled\nProvisional result", "Cancelled", "N2_AMBIGUOUS"),  # a qualifier word on the next line
    ("Status: Cancelled\n\n(provisional)", "Cancelled", "N2_AMBIGUOUS"),  # a qualifier after a blank line
])
def test_anchoring(env, lines, value, want):
    ready(env)
    pg = status_line(page("Scheduled"), lines)
    r = reading(env, pg, answer(value))
    assert (r.get("reason") or r["status"]) == want


def test_label_ends_at_a_word_boundary(env, mod):
    # the value may not run straight on from the label's last letter
    assert mod._line_start("statuscancelled", "status", "cancelled") == -1
    assert mod._line_start("winnerb-101", "winner", "b-101") == -1
    assert mod._line_start("x\nstatus cancelled", "status", "cancelled") == 2
    assert mod._line_start("x\n- winner = b-101", "winner", "b-101") == 2


# ------------------------------------------------------------ page handling


def test_clean_page(env, mod):
    out = mod._clean_page("a " + mod.PAGE_END + " b " + mod.PAGE_BEGIN + " c")
    assert "=====" not in out and out.split() == ["a", "b", "c"]
    long = "\n".join(f"line {i:05d} " + "x" * 40 for i in range(600))
    out = mod._clean_page(long)
    assert len(out) <= mod.PAGE_CHARS + len("\n(cut)") and out.endswith("\n(cut)")
    body = out[: -len("\n(cut)")]
    assert long.startswith(body) and long[len(body)] == "\n"  # cut at the end of a whole line


# ------------------------------------------------------------ the validator


def leader_then(e, leader, mine, at=CLOSE + 100):
    ready(e)
    read(e, leader, at)
    e.vm.clear_mocks()
    e.vm.mock_web(re.escape(URL), {"status": 200, "body": mine[0]})
    e.vm.mock_llm(PROMPT, mine[1])


def test_validator_agrees(env):
    leader_then(env, rec("Completed", "B-101", "Pending"), rec("Completed", "B-101", "Pending"))
    assert env.vm.run_validator() is True


@pytest.mark.parametrize("mine", [
    rec("Cancelled"), rec("Completed", "B-102", "Pending"), rec("Completed", "B-101", "Paid in full"),
    rec("Sold", "B-101", "Pending", page_kind="other"),
])
def test_validator_rejects_another_reading(env, mine):
    leader_then(env, rec("Completed", "B-101", "Pending"), mine)
    assert env.vm.run_validator() is False


def test_validator_compares_reasons(env):
    leader_then(env, rec("Suspended", other_auctions_shown="yes"), rec("Suspended", page_kind="other"))
    assert env.vm.run_validator() is False


def test_validator_compares_status(env):
    leader_then(env, rec("Suspended"), rec("Cancelled"))
    assert env.vm.run_validator() is False


def test_validator_rejects_tampered_and_failed_leaders(env):
    leader_then(env, rec("Cancelled"), rec("Cancelled"))
    assert env.vm.run_validator(leader_result={"kind": "READ", "status": "SUSPENDED", "winner": "", "balance": ""}) is False
    assert env.vm.run_validator(leader_result={"kind": "READ", "status": "MAYBE", "winner": "", "balance": ""}) is False
    assert env.vm.run_validator(leader_result={"kind": "NO_READING", "reason": "MADE_UP"}) is False
    assert env.vm.run_validator(leader_error=Exception("boom")) is False


def test_check_outcome_rejects_more(env, mod):
    for bad in ({"kind": "READ", "status": "MAYBE", "winner": "", "balance": ""},
                {"kind": "READ", "status": "COMPLETED", "winner": "B-1", "balance": ""},
                {"kind": "READ", "status": "COMPLETED", "winner": "B-1", "balance": "SOON"}):
        with pytest.raises(Exception):
            mod._check_outcome(bad)
    a = {"kind": "READ", "status": "COMPLETED", "winner": "B-1", "balance": "PENDING"}
    assert mod._check_outcome(a) == a and mod._same_outcome(a, dict(a))
    for other in ({**a, "winner": "B-2"}, {**a, "balance": "PAID_IN_FULL"}, {**a, "status": "UNCLEAR", "winner": "", "balance": ""}):
        assert not mod._same_outcome(a, other)
    n1, n2 = {"kind": "NO_READING", "reason": "N2_LABEL"}, {"kind": "NO_READING", "reason": "N2_FORMAT"}
    assert mod._same_outcome(n1, dict(n1)) and not mod._same_outcome(n1, n2) and not mod._same_outcome(a, n1)


# ------------------------------------------------- the money checks themselves


def _broken(kind):
    def pay(s, pays, code, to, note):
        b = s["bidders"][code]
        amount = b["held"]
        if amount <= 0:
            return
        if kind == "not_taken":  # paid out, but still counted as held
            pays.append(("bidder", b["addr"], amount, note))
            return
        if kind == "not_cleared":  # taken off the total but left on the bidder
            s["held"] -= amount
            s["refunded"] += amount
            pays.append(("bidder", b["addr"], amount, note))
            return
        b["held"] = 0  # "counted_twice": a correct refund, counted twice
        s["held"] -= amount
        s["refunded"] += 2 * amount
        pays.append(("bidder", b["addr"], amount, note))
    return pay


@pytest.mark.parametrize("kind,msg", [
    ("not_taken", "money does not add up"), ("counted_twice", "deposits do not reconcile"),
    ("not_cleared", "held deposits do not reconcile"),
])
def test_money_checks_stop_a_broken_payout(env, mod, monkeypatch, kind, msg):
    ready(env)
    monkeypatch.setattr(mod, "_pay_bidder", _broken(kind))
    env.vm.sender = env.creditor
    env.vm.warp(iso(T0 + 500))
    with pytest.raises(Exception, match=msg):
        env.c.cancel_auction("1")


def test_withdraw_no_more_than_credited(env):
    ready(env)
    twice(env, rec("Cancelled"), CLOSE + 100)
    env.vm.sender = env.b1
    with pytest.raises(Exception, match="amount must be 1 to"):
        env.c.withdraw(DEP + 1)
    assert env.c.withdraw(DEP - 5)["left"] == "5" and env.c.withdraw(0)["amount"] == "5"
