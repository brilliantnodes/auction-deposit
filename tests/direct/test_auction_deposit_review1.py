"""Tests for the fixes made after the first independent review (19 Nov 2026):
the payment window from the confirmed win, readings stamped after a deadline,
table layouts, the id and property on their own lines, qualifiers after a value
on its own line, quote and hyphen variants, and the log.

Every auction, creditor, property and bidder here is fictional.
"""

import pytest

from tests.direct.test_auction_deposit import (  # noqa: F401  (env and mod are fixtures)
    AID, BALANCE_S, C, CLOSE, DEP, GRACE, PROP, REFUND_BY, T0,
    answer, claim, dep, env, iso, mod, open_, page, read, ready, rec, reconciled, twice,
)


def reading(e, pg, ans, at=CLOSE + 100):
    return read(e, (pg, ans), at)["reading"]


def no_reading(reason):
    return {"kind": "NO_READING", "reason": reason}


# ---- finding 3: the payment window runs from the confirmed win


def test_adjourned_winner_gets_its_full_window(env):
    ready(env)
    late = REFUND_BY - 3 * C  # adjourned for most of the period, then won
    read(env, rec("Adjourned"), CLOSE + 100)
    a = twice(env, rec("Completed", "B-102", "Pending"), late)["auction"]
    assert a["state"] == "WON_PENDING" and a["winner_at"] == late + C
    # past the refund deadline: an auction with a confirmed winner is not refunded
    env.vm.warp(iso(REFUND_BY + GRACE + 10))
    assert env.c.settle("1")["state"] == "WON_PENDING"
    a = twice(env, rec("Completed", "B-102", "Paid in full"), late + C + BALANCE_S - 3 * C)["auction"]
    assert a["state"] == "SETTLED" and claim(env, env.creditor) == DEP


def test_reading_stamped_after_the_payment_window_does_not_count(env):
    ready(env)
    a = twice(env, rec("Completed", "B-101", "Pending"), CLOSE + 100)["auction"]
    due = a["winner_at"] + BALANCE_S
    read(env, rec("Completed", "B-101", "Paid in full"), due - 300)
    a = read(env, rec("Completed", "B-101", "Paid in full"), due + 300)["auction"]  # inside the grace, but after the window
    assert a["state"] == "WON_PENDING" and a["log"][-1]["what"] == "IGNORED"
    env.vm.warp(iso(due + GRACE))
    a = env.c.settle("1")
    assert "balance_seconds" in a["settled_reason"] and claim(env, env.creditor) == DEP


def test_reading_stamped_after_refund_by_does_not_count(env):
    ready(env)
    read(env, rec("Cancelled"), REFUND_BY - 300)
    a = read(env, rec("Cancelled"), REFUND_BY + 300)["auction"]
    assert a["state"] == "OPEN" and a["log"][-1]["what"] == "IGNORED"
    env.vm.warp(iso(REFUND_BY + GRACE))
    a = env.c.settle("1")
    assert "refund_by" in a["settled_reason"] and all(claim(env, w) == DEP for w in (env.b1, env.b2, env.b3))


def test_payment_window_checked_at_open(env):
    with pytest.raises(Exception, match="balance_seconds"):
        open_(env, balance_seconds=10**12)
    assert open_(env, balance_seconds=2 * C)["terms"]["balance_seconds"] == 2 * C


# ---- finding 4: table layouts


def tabbed(pg):
    return pg.replace(": ", "\t")


def test_tabbed_record_reads(env):
    ready(env)
    r = reading(env, tabbed(page("Completed", "B-101", "Awaiting payment")), answer("Completed", "B-101", "Awaiting payment"))
    assert r == {"kind": "READ", "status": "COMPLETED", "winner": "B-101", "balance": "PENDING"}


@pytest.mark.parametrize("planted", ["Balance\tPaid in full", "Balance - Paid in full"])
def test_planted_row_in_a_table_is_ambiguous(env, planted):
    ready(env)
    pg = tabbed(page("Completed", "B-101", "Awaiting payment")) + "\nRecent updates\n" + planted
    assert reading(env, pg, answer("Completed", "B-101", "Paid in full")) == no_reading("N2_AMBIGUOUS")


# ---- finding 5: the id and the property on their own lines


def test_another_auctions_record_mentioning_ours_is_the_wrong_page(env):
    ready(env)
    pg = page("Completed", "B-103", "Paid in full").replace(f"Auction: {AID}", "Auction: EA-24999") + f"\nRelated auctions: {AID}"
    assert reading(env, pg, answer("Completed", "B-103", "Paid in full")) == no_reading("N1_WRONG_PAGE")


def test_property_only_in_passing_is_the_wrong_page(env):
    ready(env)
    pg = page("Completed", "B-103", "Paid in full").replace(f"Property: {PROP}", "Property: Unit 9, 2 Fenn Road, Velmora")
    pg += f"\nNearby listings: {PROP}"
    assert reading(env, pg, answer("Completed", "B-103", "Paid in full")) == no_reading("N1_WRONG_PAGE")


def test_two_auction_lines_are_ambiguous(env):
    ready(env)
    pg = page("Cancelled") + "\nAuction: EA-24999"
    assert reading(env, pg, answer("Cancelled")) == no_reading("N2_AMBIGUOUS")


@pytest.mark.parametrize("line", [f"Auction no. {AID}", f"Auction id - {AID}", f"• Auction: {AID}"])
def test_other_ways_of_printing_the_id(env, line):
    ready(env)
    pg = page("Cancelled").replace(f"Auction: {AID}", line)
    assert reading(env, pg, answer("Cancelled"))["status"] == "CANCELLED"


# ---- finding 6: a qualifier after a value on its own line


def test_qualifier_after_a_value_on_its_own_line(env):
    ready(env)
    pg = page("Scheduled").replace("Status: Scheduled", "Status:\nCancelled\n(provisional)")
    assert reading(env, pg, answer("Cancelled")) == no_reading("N2_AMBIGUOUS")


def test_qualifier_after_a_winner_on_its_own_line(env):
    ready(env)
    pg = page("Completed", "B-101", "Pending").replace("Winning bidder: B-101", "Winning bidder:\nB-101\n(subject to appeal)")
    assert reading(env, pg, answer("Completed", "B-101", "Pending")) == no_reading("N2_AMBIGUOUS")


# ---- finding 7: curly quotes and other hyphens


def test_curly_quote_and_hyphen_variants_agree(env):
    open_(env, property_ref="Shop 1, 9 Tanner's Yard, Velmora")
    for who, code in ((env.b1, "B-101"), (env.b2, "B-102")):
        assert dep(env, who, code)["ok"]
    pg = page("Cancelled").replace(PROP, "Shop 1, 9 Tanner’s Yard, Velmora").replace(f"Auction: {AID}", "Auction: EA‑24117")
    for copied in ("Shop 1, 9 Tanner's Yard, Velmora", "Shop 1, 9 Tanner’s Yard, Velmora"):
        r = reading(env, pg, answer("Cancelled", property_on_page=copied, auction_id_on_page="EA‑24117"))
        assert r["status"] == "CANCELLED", copied


# ---- finding 9: the log keeps what decided the auction


def test_log_keeps_the_deciding_entries_with_many_bidders(env, mod):
    open_(env)
    for i in range(mod.MAX_BIDDERS):
        assert dep(env, bytes.fromhex(f"{0x1000 + i:040x}"), f"B-{i}", at=T0 + 300 + i)["ok"]
    a = twice(env, rec("Cancelled"), CLOSE + 100)["auction"]
    whats = [x["what"] for x in a["log"]]
    assert a["state"] == "SETTLED" and "READING" in whats and "SETTLED" in whats and whats.count("CREDIT") == 1
    assert f"{mod.MAX_BIDDERS * DEP} wei back to {mod.MAX_BIDDERS} bidder(s)" in a["log"][-1]["note"]
    reconciled(env)


def test_planted_row_on_a_dash_laid_record_is_ambiguous(env):
    ready(env)
    pg = page("Completed", "B-101", "Awaiting payment").replace(": ", " - ") + "\nRecent updates\nBalance - Paid in full"
    assert reading(env, pg, answer("Completed", "B-101", "Paid in full")) == no_reading("N2_AMBIGUOUS")
    pg = page("Completed", "B-101", "Awaiting payment").replace(": ", " - ")
    assert reading(env, pg, answer("Completed", "B-101", "Awaiting payment"))["balance"] == "PENDING"


def test_auction_id_token_may_not_continue(env, mod):
    for txt in ("auction: ea-241170", "auction: ea-24117-b", "auction: ea-24117/2", "auction: ea-24117.1"):
        assert not mod._token_on_page(txt, AID), txt
    assert mod._token_on_page("auction: ea-24117.", AID) and mod._token_on_page("auction: ea-24117 - lot 2", AID)
