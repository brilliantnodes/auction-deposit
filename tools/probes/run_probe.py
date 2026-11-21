import json, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from genlayer_py import create_account, create_client
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionStatus
G = 10**18
a = create_account(); c = create_client(chain=studionet, account=a)
c.provider.make_request(method="sim_fundAccount", params=[a.address, 50 * G])
tx = c.deploy_contract(code=Path("/home/claude/probe/render_probe.py").read_text(), args=[])
r = c.wait_for_transaction_receipt(transaction_hash=tx, status=TransactionStatus.ACCEPTED, interval=3000, retries=100)
addr = r.get("to_address") or r.get("recipient"); print("probe at", addr, flush=True)
SITE = "https://brilliantnodes.github.io/auction-deposit/record/try"
jobs = [("paid", "TRY-P-2611210615", "Flat 2, 7 Marigold Lane, Velmora")] * 3 + [("cancelled", "TRY-C-2611210615", "House, 4 Orchard Close, Brindlemere")] * 2
def one(j):
    st, aid, prop = j
    acc = create_account(); cl = create_client(chain=studionet, account=acc)
    cl.provider.make_request(method="sim_fundAccount", params=[acc.address, 5 * G])
    h = cl.write_contract(address=addr, function_name="probe", args=[f"{SITE}/{st}/{aid.lower()}.html", aid, prop])
    rr = cl.wait_for_transaction_receipt(transaction_hash=h, status=TransactionStatus.ACCEPTED, interval=3000, retries=200)
    return h, rr.get("status_name")
with ThreadPoolExecutor(5) as ex:
    for h, s in ex.map(one, jobs): print(h, s, flush=True)
logs = c.read_contract(address=addr, function_name="get_log", args=[])
Path("/home/claude/probe/out.json").write_text(json.dumps([json.loads(x) for x in logs], indent=1))
print("entries", len(logs))
