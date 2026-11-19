#!/usr/bin/env python3
"""Mutation check: break the contract on purpose, one change at a time, and
confirm that the direct-mode tests catch every break.

    PYTHONPATH=. venv/bin/python tools/mutate.py [--jobs 2]

Each mutant is written to a temporary file and the tests are pointed at it
with AD_CONTRACT; contracts/auction_deposit.py itself is never modified.
"""
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "contracts" / "auction_deposit.py").read_text()

MUTANTS = [
    # deployment
    ("upper-case hosts allowed", "or host != host.lower():", ":"),
    ("internal hosts allowed", "if host.endswith(PRIVATE_SUFFIXES) or all(c in DIGITS for c in labels[-1]):", "if False:"),
    ("duplicate hosts allowed", " or len(set(hosts)) != len(hosts):", ":"),
    ("confirm floor ignored", "_int_in(min_confirm_seconds, MIN_CONFIRM_FLOOR, MAX_CONFIRM_SECONDS)", "_int_in(min_confirm_seconds, 1, MAX_CONFIRM_SECONDS)"),
    # terms
    ("any host accepted", "    if _host_of(url) not in hosts:", "    if False:"),
    ("http accepted", 'if not url.startswith("https://"):', 'if not url.startswith("http"):'),
    ("port accepted", 'if "@" in authority or ":" in authority:', 'if "@" in authority:'),
    ("query string accepted", ' or "#" in url or "?" in url:', ' or "#" in url:'),
    ("bare host accepted", '    if "/" not in url.split("://", 1)[1]:', "    if False:"),
    ("auction id of any text", '    if _code(t["auction_id"]) is None:', "    if False:"),
    ("control characters in text", "    if any(ord(c) < 32 for c in value):", "    if False:"),
    ("zero deposit", '_int_in(t["deposit"], 1, MAX_DEPOSIT)', '_int_in(t["deposit"], 0, MAX_DEPOSIT)'),
    ("confirm below the deployment minimum", '_int_in(t["confirm_seconds"], min_confirm, MAX_CONFIRM_SECONDS)', '_int_in(t["confirm_seconds"], 1, MAX_CONFIRM_SECONDS)'),
    ("times without horizon", "_int_in(t[key], 0, now + MAX_HORIZON_SECONDS)", "_int_in(t[key], 0, 2**63)"),
    ("deposits_close in the past", '    if t["deposits_close"] <= now:', "    if False:"),
    ("payment window too short", '_int_in(t["balance_seconds"], 2 * c, MAX_HORIZON_SECONDS)', '_int_in(t["balance_seconds"], 1, MAX_HORIZON_SECONDS)'),
    ("payment window without limit", '_int_in(t["balance_seconds"], 2 * c, MAX_HORIZON_SECONDS)', '_int_in(t["balance_seconds"], 2 * c, 2**63)'),
    ("refund_by too early", 'if t["refund_by"] < t["deposits_close"] + 2 * c:', 'if t["refund_by"] < t["deposits_close"]:'),
    ("creditor not indexed", "        self._index(creditor, aid)\n", ""),
    # bidder codes
    ("codes keep their case", "    s = v.strip().upper()", "    s = v.strip()"),
    ("codes of any length", "if not 1 <= len(s) <= MAX_CODE_LEN or", "if not 1 <= len(s) or"),
    ("codes of any characters", " or any(c not in CODE_CHARS for c in s)", ""),
    ("codes may start or end with a hyphen", ' or s[0] == "-" or s[-1] == "-":', ":"),
    # deposits
    ("deposit on a closed auction", '        if s["state"] != "OPEN":\n            problem = "the auction is "', '        if False:\n            problem = "the auction is "'),
    ("deposit after close", '        elif now >= t["deposits_close"]:\n            problem = "deposits are closed"', '        elif False:\n            problem = "deposits are closed"'),
    ("deposit without the digest", "        elif terms_digest != a.digest:", "        elif False:"),
    ("creditor may bid", "        elif me.lower() == a.creditor.lower():", "        elif False:"),
    ("a code used twice", '        elif code in s["bidders"]:', "        elif False:"),
    ("an address bids twice", '        elif any(b["addr"].lower() == me.lower() for b in s["bidders"].values()):', "        elif False:"),
    ("no bidder limit", '        elif len(s["bidders"]) >= MAX_BIDDERS:', "        elif False:"),
    ("more than the deposit accepted", '        elif value != t["deposit"]:', '        elif value < t["deposit"]:'),
    ("refused value kept", "        self._credit(gl.message.sender_address.as_hex, v)\n        return {\"ok\": False", "        return {\"ok\": False"),
    ("bidder not indexed", "        self._index(me, auction_id)\n        return {\"ok\": True", "        return {\"ok\": True"),
    # withdraw_bid and cancel
    ("bid withdrawn after close", '        if s["state"] != "OPEN" or now >= t["deposits_close"]:\n            raise gl.vm.UserError("deposits are closed', '        if s["state"] != "OPEN":\n            raise gl.vm.UserError("deposits are closed'),
    ("withdrawn bidder stays registered", '        del s["bidders"][code]', "        pass"),
    ("anyone cancels", '        if gl.message.sender_address.as_hex.lower() != a.creditor.lower():\n            raise gl.vm.UserError("only the creditor may cancel")', '        if False:\n            raise gl.vm.UserError("only the creditor may cancel")'),
    ("cancel after close", '        if s["state"] != "OPEN" or now >= t["deposits_close"]:\n            raise gl.vm.UserError("only an open auction', '        if s["state"] != "OPEN":\n            raise gl.vm.UserError("only an open auction'),
    ("cancel keeps the deposits", '        _refund_all(s, pays, "the creditor cancelled the auction before it started")', "        pass"),
    # reading engine
    ("older reading counted", '    if at < s["last_read"]:', "    if False:"),
    ("last reading time not kept", '    s["last_read"] = at\n', ""),
    ("readings before close count", '    if at < t["deposits_close"]:\n        return  # before', '    if False:\n        return  # before'),
    ("unclear breaks the run", '    if key is None:\n        return\n    if key == []:', '    if key is None:\n        s["run"] = None\n        return\n    if key == []:'),
    ("open state does not restart the run", '    if key == []:\n        s["run"] = None\n        return', "    if key == []:\n        return"),
    ("one look confirms", '        if at - run["at"] >= t["confirm_seconds"]:', "        if True:"),
    ("confirm needs more than confirm_seconds", '        if at - run["at"] >= t["confirm_seconds"]:', '        if at - run["at"] > t["confirm_seconds"]:'),
    ("run kept after confirming", '            _confirm(t, s, key, at, pays)\n            s["run"] = None', "            _confirm(t, s, key, at, pays)"),
    ("another state does not restart the run", '    if run is not None and run["key"] == key:', "    if run is not None:"),
    ("readings counted at the auction clock", "        _apply_reading(t, s, r, stamp, pays)", "        _apply_reading(t, s, r, now, pays)"),
    ("unclear balance counts", '    if st == "UNCLEAR" or (st == "COMPLETED" and r["balance"] == "UNCLEAR"):', '    if st == "UNCLEAR":'),
    ("adjourned treated as an outcome", '    if st in ("SCHEDULED", "ADJOURNED"):', '    if st == "SCHEDULED":'),
    # outcomes
    ("no-sale after a winner ignored", '        if s["state"] == "WON_PENDING":\n            _refund_all(s, pays, f"auction {key[0]} after the win', '        if s["state"] == "WON_PENDING":\n            return\n            _refund_all(s, pays, f"auction {key[0]} after the win'),
    ("no-sale after a winner keeps the winner's deposit", '            _refund_all(s, pays, f"auction {key[0]} after the win: the winner\'s deposit back")', '            pass'),
    ("no-sale keeps the deposits", '        _refund_all(s, pays, f"auction {key[0]}: every deposit back")', "        pass"),
    ("winner may change", '    if s["winner"] and winner != s["winner"]:', "    if False:"),
    ("outside winner keeps the deposits", '        _refund_all(s, pays, f"the winner {winner} did not bid through this contract: every deposit back")', "        pass"),
    ("outside winner not closed", '        _close(s, at, f"confirmed winner {winner} is not a bidder here")\n        return', "        return"),
    ("losers not refunded", '        _refund_all(s, pays, f"auction won by {winner}: losing deposit back", keep=winner)', "        pass"),
    ("winner refunded with the losers", ': losing deposit back", keep=winner)', ': losing deposit back")'),
    ("winner time not kept", '        s["winner"], s["winner_at"] = winner, at', '        s["winner"], s["winner_at"] = winner, 0'),
    ("pending leaves the auction open", '    if balance == "PENDING":\n        s["state"] = "WON_PENDING"', '    if balance == "PENDING":\n        pass'),
    ("paid refunds the winner", '_pay_bidder(s, pays, winner, "creditor", "balance paid in full', '_pay_bidder(s, pays, winner, "bidder", "balance paid in full'),
    ("paid not closed", '        _close(s, at, f"won by {winner}, balance paid in full")', "        pass"),
    ("default refunds the winner", '_pay_bidder(s, pays, winner, "creditor", "the winner defaulted', '_pay_bidder(s, pays, winner, "bidder", "the winner defaulted'),
    ("default not closed", '        _close(s, at, f"won by {winner}, the winner defaulted")', "        pass"),
    # deadlines
    ("no balance deadline", '    if s["state"] == "WON_PENDING" and now >= _balance_due(t, s) + GRACE_SECONDS:', "    if False:"),
    ("balance deadline without grace", '    if s["state"] == "WON_PENDING" and now >= _balance_due(t, s) + GRACE_SECONDS:', '    if s["state"] == "WON_PENDING" and now >= _balance_due(t, s):'),
    ("payment window from deposits_close", '    return s["winner_at"] + t["balance_seconds"]', '    return t["deposits_close"] + t["balance_seconds"]'),
    ("readings after the deadline count", '    if at >= due:\n        _log(s, at, "IGNORED", "a reading stamped at or after the deadline")\n        return\n', ""),
    ("payment window not used for readings", '    due = _balance_due(t, s) if s["state"] == "WON_PENDING" else t["refund_by"]', '    due = t["refund_by"]'),
    ("refund_by not used for readings", '    due = _balance_due(t, s) if s["state"] == "WON_PENDING" else t["refund_by"]', '    due = _balance_due(t, s) if s["state"] == "WON_PENDING" else 2**63'),
    ("balance deadline refunds the winner", '_pay_bidder(s, pays, s["winner"], "creditor", "no confirmed payment', '_pay_bidder(s, pays, s["winner"], "bidder", "no confirmed payment'),
    ("no refund deadline", '    elif s["state"] == "OPEN" and now >= t["refund_by"] + GRACE_SECONDS:', "    elif False:"),
    ("refund deadline without grace", '    elif s["state"] == "OPEN" and now >= t["refund_by"] + GRACE_SECONDS:', '    elif s["state"] == "OPEN" and now >= t["refund_by"]:'),
    ("refund deadline keeps the deposits", '        _refund_all(s, pays, "no confirmed outcome by refund_by: every deposit back")', "        pass"),
    ("clock runs backwards", '        now = max(self._tx_time(), s["t"])', "        now = self._tx_time()"),
    ("deadline through a reading not kept", '            if s["_was"] in ("OPEN", "WON_PENDING"):', "            if False:"),
    ("reading a settled auction", '        if s["state"] not in ("OPEN", "WON_PENDING"):\n            if s["_was"]', '        if False:\n            if s["_was"]'),
    # interpreting the copy
    ("wrong page kind accepted", '    if str(ans.get("page_kind", "")).strip().lower() != "auction_record":', "    if False:"),
    ("copied auction id not compared", '    if _norm(ans.get("auction_id_on_page")) != t["auction_id"].lower() or not _token_on_page(page_n, t["auction_id"]):', '    if not _token_on_page(page_n, t["auction_id"]):'),
    ("copied property not compared", '    if _norm(ans.get("property_on_page")) != prop or prop not in page_n or all(', "    if prop not in page_n or all("),
    ("property only in passing accepted", ' or all(_line_start(pl, lab, prop) < 0 for lab in PROPERTY_LABELS):', ":"),
    ("id only in passing accepted", '    if not id_at:\n        return {"kind": "NO_READING", "reason": "N1_WRONG_PAGE"}', '    if False:\n        return {"kind": "NO_READING", "reason": "N1_WRONG_PAGE"}'),
    ("another auction line accepted", "    if any(x not in id_at for x in _label_form_lines(pl, AUCTION_LABELS)):", "    if False:"),
    ("other auctions ignored", '    if str(ans.get("other_auctions_shown", "")).strip().lower() in ("yes", "true", "1"):', "    if False:"),
    ("status label not checked", '    if _norm_label(st.get("label")) not in STATUS_LABELS:', "    if False:"),
    ("status not anchored", "    if st_at < 0:", "    if False:"),
    ("a second status line accepted", "    if any(x != st_at for x in _label_form_lines(pl, STATUS_LABELS)) or _qualified_next(pl, st_end):", "    if _qualified_next(pl, st_end):"),
    ("status qualifier ignored", "    if any(x != st_at for x in _label_form_lines(pl, STATUS_LABELS)) or _qualified_next(pl, st_end):", "    if any(x != st_at for x in _label_form_lines(pl, STATUS_LABELS)):"),
    ("winner with a no-sale accepted", "        for f in (wn, bl):", "        for f in ():"),
    ("balance with a no-sale accepted", "        for f in (wn, bl):", "        for f in (wn,):"),
    ("winner label not checked", '    if _norm_label(wn.get("label")) not in WINNER_LABELS or _norm_label(bl.get("label")) not in BALANCE_LABELS:', '    if _norm_label(bl.get("label")) not in BALANCE_LABELS:'),
    ("balance label not checked", '    if _norm_label(wn.get("label")) not in WINNER_LABELS or _norm_label(bl.get("label")) not in BALANCE_LABELS:', '    if _norm_label(wn.get("label")) not in WINNER_LABELS:'),
    ("winner not anchored", "    if wn_at < 0 or bl_at < 0:", "    if bl_at < 0:"),
    ("balance not anchored", "    if wn_at < 0 or bl_at < 0:", "    if wn_at < 0:"),
    ("a second winner line accepted", "    if any(x != wn_at for x in _label_form_lines(pl, WINNER_LABELS)) or any(x != bl_at for x in _label_form_lines(pl, BALANCE_LABELS)):", "    if any(x != bl_at for x in _label_form_lines(pl, BALANCE_LABELS)):"),
    ("a second balance line accepted", "    if any(x != wn_at for x in _label_form_lines(pl, WINNER_LABELS)) or any(x != bl_at for x in _label_form_lines(pl, BALANCE_LABELS)):", "    if any(x != wn_at for x in _label_form_lines(pl, WINNER_LABELS)):"),
    ("winner qualifier ignored", "    if _qualified_next(pl, wn_end) or _qualified_next(pl, bl_end):", "    if _qualified_next(pl, bl_end):"),
    ("balance qualifier ignored", "    if _qualified_next(pl, wn_end) or _qualified_next(pl, bl_end):", "    if _qualified_next(pl, wn_end):"),
    ("bad winner code passed on", '    if winner is None:\n        return {"kind": "NO_READING", "reason": "N2_FORMAT"}', '    if winner is None:\n        winner = str(wn.get("value"))'),
    ("status by word, not phrase", '    status = STATUS_TABLE.get(_norm_phrase(st.get("value")), "UNCLEAR")', '    status = next((v for k, v in STATUS_TABLE.items() if k in _norm_phrase(st.get("value"))), "UNCLEAR")'),
    ("balance by word, not phrase", '    balance = BALANCE_TABLE.get(_norm_phrase(bl.get("value")), "UNCLEAR")', '    balance = next((v for k, v in BALANCE_TABLE.items() if k in _norm_phrase(bl.get("value"))), "UNCLEAR")'),
    ("not paid counted as paid", '"paid": "PAID_IN_FULL", "paid in full"', '"paid": "PAID_IN_FULL", "not paid": "PAID_IN_FULL", "paid in full"'),
    ("final full stop kept", '    while s.endswith("."):', "    while False:"),
    ("label colon kept", '    while s.endswith(":"):', "    while False:"),
    ("dashes not normalised", 'for d in ("−", "–", "—", "‒", "―", "‐", "‑"):', 'for d in ("−",):'),
    ("other hyphens not normalised", '"―", "‐", "‑"):', '"―"):'),
    ("curly quotes not folded", '    for q in ("‘", "’", "ʼ", "′"):\n        s = s.replace(q, "\'")\n', ""),
    ("tabs not cells", '_norm(line.replace("\\t", " | "))', "_norm(line)"),
    # anchoring
    ("partial value anchored", '                if all(c in " |" for c in pl[e:eol]):', "                if True:"),
    ("label anchored after other words", "        if all(c in SEPARATORS or c in LEAD_MARKS for c in pl[start:a]) and (b == len(pl) or pl[b] in SEPARATORS):", "        if (b == len(pl) or pl[b] in SEPARATORS):"),
    ("label anchored inside a longer word", "        if all(c in SEPARATORS or c in LEAD_MARKS for c in pl[start:a]) and (b == len(pl) or pl[b] in SEPARATORS):", "        if all(c in SEPARATORS or c in LEAD_MARKS for c in pl[start:a]):"),
    ("bullets not allowed before a label", "        if all(c in SEPARATORS or c in LEAD_MARKS for c in pl[start:a]) and", "        if all(c in SEPARATORS for c in pl[start:a]) and"),
    ("value lines away", ' and breaks + (pl[j] == "\\n") <= 1:', ":"),
    ("value far after its label", "            if j - b <= ANCHOR_CHARS and pl.startswith(value_n, j):", "            if pl.startswith(value_n, j):"),
    ("words between label and value", " and pl[j] in SEPARATORS and breaks", " and not pl.startswith(value_n, j) and breaks"),
    ("longer label counted as a label line", '                if tail == "" or tail[0] in ":|=-":', "                if True:"),
    ("label line written with = not counted", '                if tail == "" or tail[0] in ":|=-":', '                if tail == "" or tail[0] in ":|-":'),
    ("label line written with - not counted", '                if tail == "" or tail[0] in ":|=-":', '                if tail == "" or tail[0] in ":|=":'),
    ("status qualifier checked from the label line", "_qualified_next(pl, st_end):", "_qualified_next(pl, st_at):"),
    ("winner qualifier checked from the label line", "    if _qualified_next(pl, wn_end) or", "    if _qualified_next(pl, wn_at) or"),
    ("bracket on the next line not a qualifier", '        return n.startswith("(") or any(w in n for w in QUALIFIERS)', "        return any(w in n for w in QUALIFIERS)"),
    ("qualifier words ignored", '        return n.startswith("(") or any(w in n for w in QUALIFIERS)', '        return n.startswith("(")'),
    ("blank line ends the qualifier check", '        if n == "":\n            continue', '        if n == "":\n            return False'),
    ("auction id may continue", '        after = b >= len(page_n) or not (page_n[b].isalnum() or (page_n[b] in "-/." and b + 1 < len(page_n) and page_n[b + 1].isalnum()))', "        after = True"),
    ("auction id may be preceded", '        before = a == 0 or not (page_n[a - 1].isalnum() or page_n[a - 1] in "-/.")', "        before = True"),
    # page handling
    ("markers not removed", '    text = text.replace(PAGE_BEGIN, " ").replace(PAGE_END, " ").replace("=====", " ")', "    text = text"),
    ("page not cut", "        text = text[:PAGE_CHARS]\n", ""),
    ("page cut inside a line", '        text = (text[:nl] if nl >= 0 else "") + "\\n(cut)"', '        text = text + "\\n(cut)"'),
    ("dark page read", '    if page.strip() == "":\n        return {"kind": "NO_READING", "reason": "N1_PAGE_DARK"}', '    if False:\n        return {"kind": "NO_READING", "reason": "N1_PAGE_DARK"}'),
    # agreement
    ("leader error accepted", "            if not isinstance(leader_result, gl.vm.Return):\n                return False", "            if not isinstance(leader_result, gl.vm.Return):\n                return True"),
    ("kind not compared", '    if a["kind"] != b["kind"]:\n        return False', '    if False:\n        return False'),
    ("status not compared", '    return (a["status"], a["winner"], a["balance"]) == (b["status"], b["winner"], b["balance"])', '    return (a["winner"], a["balance"]) == (b["winner"], b["balance"])'),
    ("winner not compared", '    return (a["status"], a["winner"], a["balance"]) == (b["status"], b["winner"], b["balance"])', '    return (a["status"], a["balance"]) == (b["status"], b["balance"])'),
    ("balance not compared", '    return (a["status"], a["winner"], a["balance"]) == (b["status"], b["winner"], b["balance"])', '    return (a["status"], a["winner"]) == (b["status"], b["winner"])'),
    ("unknown reason accepted", '        if r.get("reason") not in NO_READING_REASONS:', "        if False:"),
    ("unknown status accepted", "    if st not in STATUSES or b not in BALANCES or not isinstance(w, str):", "    if b not in BALANCES or not isinstance(w, str):"),
    ("completed without a balance", '        if _code(w) != w or b == "":', "        if _code(w) != w:"),
    ("winner with a no-sale outcome accepted", '    elif w != "" or b != "":\n        raise ValueError', '    elif False:\n        raise ValueError'),
    # money
    ("money check removed", 'if any(v < 0 for _w, _addr, v, _n in pays) or held_before + value_in != s["held"] + out or s["held"] < 0:', "if False:"),
    ("deposits reconcile check removed", '        if s["deposited"] != s["held"] + s["to_creditor"] + s["refunded"]:', "        if False:"),
    ("held reconcile check removed", '        if s["held"] != sum(b["held"] for b in s["bidders"].values()):', "        if False:"),
    ("locked total not kept", '        self.locked = u256(int(self.locked) + s["held"] - held_before)', "        pass"),
    ("creditor and bidder swapped", '            to = a.creditor if who == "creditor" else addr', '            to = addr if who == "creditor" else a.creditor'),
    ("paid deposit not taken off the bidder", '    b["held"] = 0\n    s["held"] -= amount', '    s["held"] -= amount'),
    ("withdraw more than credited", "        if not 0 < amount <= have:", "        if not 0 < amount:"),
    ("credit not reduced on withdraw", "        self.claims[k] = u256(have - amount)", "        pass"),
    ("credited total not reduced on withdraw", "        self.claims_total = u256(int(self.claims_total) - amount)\n        _Wallet", "        _Wallet"),
]

# Not counted, with the reason the change cannot alter any outcome.
EQUIVALENT = [
    # The id and the property must now be anchored on their own labelled line,
    # which already puts them on the page as whole values.
    ("property not on the page", ' != prop or prop not in page_n or all(_line_start', ' != prop or all(_line_start'),
    ("auction id not on the page", '    if _norm(ans.get("auction_id_on_page")) != t["auction_id"].lower() or not _token_on_page(page_n, t["auction_id"]):', '    if _norm(ans.get("auction_id_on_page")) != t["auction_id"].lower():'),
    # _norm ends with " ".join(s.split()), and Python's str.split() already
    # splits on no-break spaces (U+00A0, U+202F), so the explicit replace is a
    # belt-and-braces step.
    ("no-break spaces kept", '.replace("\xa0", " ").replace(" ", " ")', ""),
]


def run_one(i, name, path, env):
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/direct", "-q", "-x", "-p", "no:cacheprovider"],
                       cwd=ROOT, env={**env, "AD_CONTRACT": str(path)}, capture_output=True, text=True)
    return i, name, r.returncode != 0


def main() -> int:
    jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 2
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    tmp = Path(tempfile.mkdtemp(prefix="ad-mutants-"))
    work = []
    for i, (name, old, new) in enumerate(MUTANTS, 1):
        n = SRC.count(old)
        if n != 1:
            print(f"SETUP ERROR  {i} {name}: pattern found {n} times")
            return 2
        path = tmp / f"mutant_{i:03d}.py"
        path.write_text(SRC.replace(old, new))
        work.append((i, name, path))
    caught = 0
    with ThreadPoolExecutor(jobs) as ex:
        for i, name, ok in ex.map(lambda w: run_one(*w, env), work):
            caught += ok
            print(f"{'caught ' if ok else 'MISSED '} {i:3d} {name}", flush=True)
    print(f"\n{caught} of {len(MUTANTS)} mutants caught")
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
