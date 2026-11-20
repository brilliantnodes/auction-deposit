"""Narration for the AuctionDeposit video, offline with Kokoro-82M (voice af_heart, as in the ClaimEscrow video).
Writes voice/<scene>.wav and durations.json (seconds of speech per scene)."""
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

D = Path(__file__).parent
LINES = {
    "s1": "Auction Deposit. A safe way to put down a bid deposit at a property auction, built on Gen Layer.",
    "s2": "In Greece, nearly three hundred thousand property auctions are waiting, and only about one in five succeeds. Europe's largest banks hold three hundred and seventy three billion euros of bad loans.",
    "s3": "Today, every bidder pays a deposit up front. Losers wait weeks to get it back. Auctions get cancelled or suspended. And some winners never pay the rest.",
    "s4": "Auction Deposit keeps every bidder's deposit in one escrow on Gen Layer. Validators read the official auction record. The AI only copies the lines, and plain code checks every copy. Nothing moves on one look: a result must be seen twice, ten minutes apart.",
    "s5": "Then code pays. Won and paid: the losers get their money back, and the winner's deposit goes to the bank as part of the price. If the winner walks away, the deposit is the bank's penalty. Cancelled or suspended: everyone is refunded.",
    "s6": "We ran ten fictional auctions live, on Gen Layer Studio and on Testnet Bradbury. Seventy eight transactions, all final. Every case ended as planned, even a page with a planted instruction.",
    "s7": "Auction Deposit. On Gen Layer, by Brilliant Nodes.",
}
import os
KD = os.environ.get("KOKORO_DIR", "/home/claude/kokoro")
k = Kokoro(f"{KD}/kokoro-v1.0.fp16.onnx", f"{KD}/voices-v1.0.bin")
(D / "voice").mkdir(exist_ok=True)
durs = {}
for name, text in LINES.items():
    s, sr = k.create(text, voice="af_heart", speed=1.0, lang="en-us")
    s = np.asarray(s, dtype=np.float32)
    sf.write(D / "voice" / f"{name}.wav", s, sr)
    durs[name] = round(len(s) / sr, 2)
    print(name, durs[name])
(D / "durations.json").write_text(json.dumps(durs))
