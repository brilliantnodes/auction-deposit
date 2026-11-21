#!/usr/bin/env python3
"""Click through the "Try it yourself" page in a headless browser, as a
visitor does, against the visitor contract on GenLayer Studio.

    python tools/e2e_try.py <page url> <story: paid|default|cancelled> <out dir>

Sets up the three temporary accounts, opens an auction for the next slot,
lodges both deposits, then keeps pressing the button the page offers ("Read
the record", or waiting while it shows a countdown) until the auction is
settled or cancelled, and withdraws every credit. Screenshots and a JSON log
of every step go to <out dir>. Fictional data; test GEN only.
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

url, story, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
LOG = []


def log(what, **kw):
    LOG.append({"t": int(time.time()), "what": what, **kw})
    (out / "log.json").write_text(json.dumps(LOG, indent=1))
    print(time.strftime("%H:%M:%S"), what, json.dumps(kw)[:300], flush=True)


def wait_tx(pg, limit=900):
    """Wait until the lifecycle panel shows a final note."""
    t0 = time.time()
    while time.time() - t0 < limit:
        note = pg.inner_text("#life-note")
        if note and not note.startswith("Sent ") and not note.startswith("Signing"):
            return note
        time.sleep(3)
    return "timeout"


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1200, "height": 1600})
    pg.on("pageerror", lambda e: log("page error", error=str(e)))
    pg.goto(url)
    pg.wait_for_timeout(3000)
    pg.click("#btn-setup")
    pg.wait_for_function("document.getElementById('bidder2-bal').textContent.includes('Wallet')", timeout=120000)
    log("accounts", creditor=pg.inner_text("#creditor-addr"), b1=pg.inner_text("#bidder1-addr"), b2=pg.inner_text("#bidder2-addr"))
    pg.check(f"input[name=story][value={story}]")
    log("slot", note=pg.inner_text("#slot-note"))
    pg.screenshot(path=str(out / "01-start.png"), full_page=True)
    pg.click("#btn-open")
    log("open", note=wait_tx(pg))
    pg.wait_for_selector("#auction:not([hidden])", timeout=60000)
    log("auction", title=pg.inner_text("#a-title"), next=pg.inner_text("#a-next"))
    for who in ("Bidder 1", "Bidder 2"):
        pg.get_by_role("button", name=f"{who}: deposit 1 GEN").click()
        log(f"deposit {who}", note=wait_tx(pg))
    pg.screenshot(path=str(out / "02-deposits.png"), full_page=True)
    t0 = time.time()
    shots = 3
    while time.time() - t0 < 60 * 60:
        state = pg.inner_text("#a-state")
        nxt = pg.inner_text("#a-next")
        if state in ("SETTLED", "CANCELLED"):
            break
        btn = pg.get_by_role("button", name="Read the record")
        if btn.count() and btn.first.is_enabled():
            btn.first.click()
            note = wait_tx(pg)
            log("read", note=note, state=pg.inner_text("#a-state"))
            pg.screenshot(path=str(out / f"{shots:02d}-read.png"), full_page=True)
            shots += 1
        else:
            time.sleep(10)
            pg.click("#a-reload")
            time.sleep(2)
            if int(time.time() - t0) % 120 < 12:
                log("waiting", next=nxt)
    log("final", state=pg.inner_text("#a-state"), next=pg.inner_text("#a-next"), money=pg.inner_text("#a-money"))
    pg.screenshot(path=str(out / f"{shots:02d}-final.png"), full_page=True)
    for role in ("creditor", "bidder1", "bidder2"):
        w = pg.locator(f"#{role}-bal button")
        if w.count():
            w.first.click()
            log(f"withdraw {role}", note=wait_tx(pg))
    pg.click("#a-reload")
    time.sleep(3)
    log("balances", creditor=pg.inner_text("#creditor-bal"), b1=pg.inner_text("#bidder1-bal"), b2=pg.inner_text("#bidder2-bal"))
    pg.screenshot(path=str(out / "99-done.png"), full_page=True)
    b.close()
