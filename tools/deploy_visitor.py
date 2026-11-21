#!/usr/bin/env python3
"""Deploy the AuctionDeposit contract used by the site's "Try it yourself"
section on GenLayer Studio.

    python tools/deploy_visitor.py

The same contract source as the live runs, deployed with the GitHub Pages host
as its only record host and a 60-second minimum confirmation, so a visitor's
fictional auction runs in about half an hour (the live runs used 600 s). The
throwaway deployer key is kept outside the repository and never printed.
"""
import json
import os
import time
from pathlib import Path

from genlayer_py import create_account, create_client
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionStatus

ROOT = Path(__file__).resolve().parent.parent
HOSTS = ["brilliantnodes.github.io"]
MIN_CONFIRM = 60
G = 10**18


def main():
    a = create_account()
    keys = Path(os.environ.get("LIVE_KEY_DIR", "/home/claude/keys"))
    keys.mkdir(parents=True, exist_ok=True)
    kf = keys / "studio-ad-visitor-deployer.json"
    kf.write_text(json.dumps({"deployer": a.key.hex() if hasattr(a.key, "hex") else str(a.key)}))
    os.chmod(kf, 0o600)
    c = create_client(chain=studionet, account=a)
    for _ in range(8):
        try:
            c.provider.make_request(method="sim_fundAccount", params=[a.address, 10 * G])
            break
        except Exception:
            time.sleep(10)
    code = (ROOT / "contracts" / "auction_deposit.py").read_text()
    tx = c.deploy_contract(code=code, args=[json.dumps(HOSTS), MIN_CONFIRM])
    r = c.wait_for_transaction_receipt(transaction_hash=tx, status=TransactionStatus.ACCEPTED, interval=3000, retries=100)
    addr = r.get("to_address") or r.get("recipient")
    rules = c.read_contract(address=addr, function_name="get_rules", args=[])
    print(json.dumps({"address": addr, "deploy_tx": tx, "deployer": a.address,
                      "record_hosts": rules["record_hosts"], "min_confirm_seconds": rules["min_confirm_seconds"]}))


if __name__ == "__main__":
    main()
