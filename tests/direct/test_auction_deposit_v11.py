"""v1.1: a value copied together with its label ("Status: Completed").

Seen on GenLayer Studio on 21 Nov 2026: in probe renders of the record page,
some models put the label inside the value, which v1 refused as not anchored
(nothing moved, but a visitor had to read again). v1.1 strips the copied label
when the value starts with it followed by ':', '|' or '='; the rest must still
be anchored after that label on the validator's own copy of the page.
Every auction, property and bidder here is fictional.
"""

import json

from tests.direct.test_auction_deposit import AID, PROP, env, mod, page  # noqa: F401

T = {"auction_id": AID, "property_ref": PROP}


def ans(st, wn=("", ""), bl=("", "")):
    return {"page_kind": "auction_record", "auction_id_on_page": AID, "property_on_page": PROP, "other_auctions_shown": "no",
            "status": {"label": st[0], "value": st[1]},
            "winning_bidder": {"label": wn[0], "value": wn[1]},
            "balance": {"label": bl[0], "value": bl[1]}}


def test_label_inside_value_is_read(mod):
    pg = page("Completed", "B-102", "Paid in full")
    r = mod._interpret(T, ans(("Status", "Status: Completed"), ("Winning bidder", "Winning bidder: B-102"), ("Balance", "Balance: Paid in full")), pg)
    assert r == {"kind": "READ", "status": "COMPLETED", "winner": "B-102", "balance": "PAID_IN_FULL"}


def test_label_inside_value_mixed_with_plain_copies(mod):
    pg = page("Completed", "B-102", "Awaiting payment")
    r = mod._interpret(T, ans(("Status", "Status: Completed"), ("Winning bidder", "B-102"), ("Balance", "Balance:Awaiting payment")), pg)
    assert r == {"kind": "READ", "status": "COMPLETED", "winner": "B-102", "balance": "PENDING"}


def test_label_with_colon_and_case_differences(mod):
    pg = page("Cancelled", "-", "-")
    r = mod._interpret(T, ans(("Status:", "STATUS: Cancelled"), ("Winning bidder", "Winning bidder: -"), ("Balance", "Balance: -")), pg)
    assert r == {"kind": "READ", "status": "CANCELLED", "winner": "", "balance": ""}


def test_same_reading_as_plain_copy(mod):
    pg = page("Completed", "B-103", "Buyer in default")
    plain = mod._interpret(T, ans(("Status", "Completed"), ("Winning bidder", "B-103"), ("Balance", "Buyer in default")), pg)
    labelled = mod._interpret(T, ans(("Status", "Status: Completed"), ("Winning bidder", "Winning bidder: B-103"), ("Balance", "Balance: Buyer in default")), pg)
    assert plain == labelled == {"kind": "READ", "status": "COMPLETED", "winner": "B-103", "balance": "DEFAULTED"}


def test_phrase_that_starts_with_the_label_word_is_not_cut(mod):
    # "Balance paid" is a balance phrase, not "Balance" + ": paid".
    pg = page("Completed", "B-102", "Balance paid")
    r = mod._interpret(T, ans(("Status", "Completed"), ("Winning bidder", "B-102"), ("Balance", "Balance paid")), pg)
    assert r == {"kind": "READ", "status": "COMPLETED", "winner": "B-102", "balance": "PAID_IN_FULL"}


def test_value_with_another_label_is_not_stripped(mod):
    pg = page("Completed", "B-102", "Paid in full")
    r = mod._interpret(T, ans(("Result", "Status: Completed"), ("Winning bidder", "B-102"), ("Balance", "Paid in full")), pg)
    assert r["kind"] == "NO_READING"


def test_stripped_value_must_still_be_on_the_page(mod):
    pg = page("Completed", "B-102", "Awaiting payment")
    r = mod._interpret(T, ans(("Status", "Status: Completed"), ("Winning bidder", "B-102"), ("Balance", "Balance: Paid in full")), pg)
    assert r == {"kind": "NO_READING", "reason": "N2_NOT_ANCHORED"}


def test_stripped_winner_must_be_on_the_winner_line(mod):
    pg = page("Completed", "B-102", "Awaiting payment")
    r = mod._interpret(T, ans(("Status", "Completed"), ("Winning bidder", "Winning bidder: B-101"), ("Balance", "Awaiting payment")), pg)
    assert r == {"kind": "NO_READING", "reason": "N2_NOT_ANCHORED"}


def test_label_only_value_is_empty(mod):
    pg = page("Completed", "B-102", "Awaiting payment")
    r = mod._interpret(T, ans(("Status", "Status:"), ("Winning bidder", "B-102"), ("Balance", "Awaiting payment")), pg)
    assert r["kind"] == "NO_READING"


def test_unlabel_leaves_non_strings_alone(mod):
    assert mod._unlabel({"label": "Status", "value": 3}) == {"label": "Status", "value": 3}
    assert mod._unlabel({}) == {}
    assert mod._unlabel({"label": "", "value": "Status: Completed"}) == {"label": "", "value": "Status: Completed"}


def test_prompt_asks_for_the_value_without_its_label(mod):
    p = mod._prompt(T, "page text")
    assert p.count("without the label") == 3
    json.dumps(p)  # plain text
