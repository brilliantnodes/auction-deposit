"""AuctionDeposit video v2 scenes: photo of the Acropolis (George E. Koronaios, CC BY-SA 4.0, Wikimedia Commons),
waving Greek flag, counters, moving coins; durations fitted to the narration."""
import json
from pathlib import Path

D = Path(__file__).parent
OUT = D / "scenes2"
OUT.mkdir(exist_ok=True)
SPEECH = json.loads((D / "durations.json").read_text())
LEAD, TAIL = 0.6, 1.0
DUR = {k: round(max(6.0, LEAD + v + TAIL), 2) for k, v in SPEECH.items()}
PHOTO = (D / "photo" / "acropolis.jpg").resolve().as_uri()
CREDIT = '<div class="credit">Photo: George E. Koronaios, CC BY-SA 4.0, via Wikimedia Commons</div>'

FLAG_SVG = ("data:image/svg+xml;utf8," + "<svg xmlns='http://www.w3.org/2000/svg' width='270' height='180' viewBox='0 0 27 18'>"
            + "".join(f"<rect y='{i*2}' width='27' height='2' fill='{'%230D5EAF' if i % 2 == 0 else '%23ffffff'}'/>" for i in range(9))
            + "<rect width='10' height='10' fill='%230D5EAF'/><rect x='4' width='2' height='10' fill='%23fff'/><rect y='4' width='10' height='2' fill='%23fff'/></svg>")


def flag(x, y, w=270, pole=True, slices=30):
    h = w * 2 / 3
    sw = w / slices
    parts = "".join(f'<div class="fs" style="left:{i*sw:.2f}px;width:{sw+0.6:.2f}px;background-position:-{i*sw:.2f}px 0;animation-delay:-{i*0.07:.2f}s"></div>' for i in range(slices))
    p = f'<div class="pole" style="height:{h*2.6:.0f}px"></div>' if pole else ""
    return f'<div class="flag" style="left:{x}px;top:{y}px;width:{w}px;height:{h:.0f}px;--w:{w}px;--h:{h:.0f}px">{p}{parts}</div>'


BASE = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden;background:#04101f;font-family:Inter,"Helvetica Neue",Arial,sans-serif;color:#fff}
.stage{position:absolute;inset:0;animation:fade %(dur)ss linear both}
@keyframes fade{0%%{opacity:0}4%%{opacity:1}95%%{opacity:1}100%%{opacity:0}}
.bg{position:absolute;inset:0;background:radial-gradient(ellipse at 30%% 20%%,#16477d 0%%,#0b2a50 45%%,#040f1e 100%%)}
.glow{position:absolute;width:900px;height:900px;border-radius:50%%;background:radial-gradient(rgba(255,215,106,.10),rgba(255,215,106,0) 65%%);animation:drift %(dur)ss linear both}
@keyframes drift{from{transform:translate(-200px,0)}to{transform:translate(300px,80px)}}
.dots{position:absolute;inset:0;background-image:radial-gradient(rgba(150,200,255,.18) 1.5px,transparent 1.6px);background-size:46px 46px;animation:pan %(dur)ss linear both;opacity:.6}
@keyframes pan{from{background-position:0 0}to{background-position:120px 60px}}
.photo{position:absolute;inset:-60px;background:url('%(photo)s') center/cover;animation:kb %(dur)ss linear both}
@keyframes kb{from{transform:scale(1.0)}to{transform:scale(1.12) translate(-20px,10px)}}
.in{opacity:0;animation:rise .8s cubic-bezier(.2,.8,.2,1) both}
@keyframes rise{from{opacity:0;transform:translateY(40px)}to{opacity:1;transform:none}}
.pop{opacity:0;animation:pop .55s cubic-bezier(.2,1.6,.4,1) both}
@keyframes pop{from{opacity:0;transform:scale(.3)}to{opacity:1;transform:scale(1)}}
.slide{opacity:0;animation:slide .8s cubic-bezier(.2,.8,.2,1) both}
@keyframes slide{from{opacity:0;transform:translateX(-80px)}to{opacity:1;transform:none}}
.h{font-size:72px;font-weight:800;letter-spacing:-1.5px}
.s{font-size:40px;color:#d7e6f7;font-weight:500}
.gold{color:#ffd76a}.green{color:#62e0a3}.amber{color:#ffb547}.red{color:#ff7a6b}
.glass{background:rgba(9,32,62,.72);border:1.5px solid rgba(140,190,255,.28);border-radius:26px;backdrop-filter:blur(6px);box-shadow:0 20px 60px rgba(0,0,0,.35)}
.credit{position:absolute;left:26px;bottom:18px;font-size:18px;color:rgba(255,255,255,.75);text-shadow:0 1px 4px rgba(0,0,0,.8)}
.flag{position:absolute}.pole{position:absolute;left:-14px;top:-12px;width:12px;border-radius:6px;background:linear-gradient(90deg,#9aa4ad,#f4f6f8,#8a939b)}
.fs{position:absolute;top:0;height:100%%;background:url("%(flag)s");background-size:var(--w) var(--h);animation:wv 1.5s ease-in-out infinite alternate;box-shadow:inset 0 0 0 9999px rgba(0,0,0,0)}
@keyframes wv{from{transform:translateY(-7px);filter:brightness(1.08)}to{transform:translateY(7px);filter:brightness(.86)}}
.coin{position:absolute;width:70px;height:70px;border-radius:50%%;background:radial-gradient(circle at 35%% 30%%,#fff3c4,#f2c14e 45%%,#c58b1c);border:4px solid #a8740f;color:#6d4908;font-weight:900;font-size:34px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 24px rgba(255,200,80,.45)}
.vig{position:absolute;inset:0;background:radial-gradient(ellipse at center,rgba(0,0,0,0) 55%%,rgba(0,0,0,.45) 100%%)}
%(css)s
</style></head><body><div class="stage">%(body)s</div>
<script>%(js)s</script></body></html>"""


def scene(name, css, body, js=""):
    (OUT / f"{name}.html").write_text(BASE % {"dur": DUR[name], "photo": PHOTO, "flag": FLAG_SVG, "css": css, "body": body, "js": js})


# ---------------------------------------------------------------- s1 title on the photo
scene("s1", """
.shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(4,16,31,.55) 0%,rgba(4,16,31,.1) 38%,rgba(4,16,31,0) 60%,rgba(4,16,31,.55) 100%)}
.title{position:absolute;left:0;right:0;top:70px;text-align:center}
.title .h{font-size:120px;text-shadow:0 6px 30px rgba(0,0,0,.55)}
.bar{height:6px;width:0;background:linear-gradient(90deg,#ffd76a,#ffb547);margin:14px auto 18px;border-radius:3px;animation:bar 1.2s ease-out 1.2s both}
@keyframes bar{to{width:520px}}
.title .s{font-size:46px;color:#fff;text-shadow:0 3px 18px rgba(0,0,0,.7)}
.by{position:absolute;left:0;right:0;bottom:70px;text-align:center;font-size:30px;font-weight:600;text-shadow:0 2px 12px rgba(0,0,0,.8)}
""", '<div class="photo"></div><div class="shade"></div>' + flag(1600, 720, 230) + """
<div class="title"><div class="h in" style="animation-delay:.5s">AuctionDeposit</div><div class="bar"></div>
<div class="s in" style="animation-delay:1.6s">A safe way to put down a bid deposit at a property auction</div></div>
<div class="by in" style="animation-delay:3s">Built on <span class="gold">GenLayer</span> by Brilliant Nodes</div>""" + CREDIT)

# ---------------------------------------------------------------- s2 the market
scene("s2", """
.photo{filter:blur(10px) brightness(.38)}
.wrap{position:absolute;left:150px;right:150px;top:150px;display:grid;grid-template-columns:1.25fr 1fr;gap:40px}
.card{padding:40px 46px}.big{font-size:150px;font-weight:900;line-height:1;color:#ffd76a;font-variant-numeric:tabular-nums}
.lbl{font-size:42px;color:#e6f0fb;margin-top:12px}
.homes{display:flex;gap:22px;margin-top:26px}.home{width:96px;height:96px;opacity:.28}
.home.lit{animation:lit .6s ease-out 6.2s both}@keyframes lit{to{opacity:1;filter:drop-shadow(0 0 18px #ffd76a)}}
.wide{grid-column:1/3;text-align:center;padding:34px}.wide .big{font-size:120px}
.src{position:absolute;left:0;right:0;bottom:30px;text-align:center;font-size:22px;color:#9fb6d2}
""", '<div class="photo"></div><div class="vig"></div>' + flag(1640, 60, 170, pole=False) + """
<div class="wrap">
<div class="card glass in" style="animation-delay:.4s"><div class="big"><span id="c1">0</span></div><div class="lbl">property auctions waiting in <b>Greece</b></div></div>
<div class="card glass in" style="animation-delay:4.4s"><div class="big">1 in 5</div><div class="lbl">auctions succeeds</div>
<div class="homes">""" + "".join(f'<svg class="home{" lit" if i == 0 else ""}" viewBox="0 0 24 24"><path fill="{"#ffd76a" if i == 0 else "#9fc0e8"}" d="M12 3 2 11h3v9h5v-6h4v6h5v-9h3z"/></svg>' for i in range(5)) + """</div></div>
<div class="wide glass in" style="animation-delay:7.6s"><div class="lbl" style="margin:0 0 8px">Europe's largest banks hold</div><div class="big"><span id="c2">€0bn</span></div><div class="lbl">of bad loans</div></div>
</div>
<div class="src in" style="animation-delay:8.4s">Sources: euro2day citing IOBE, Cepal and the IMF (Q1 2026) · Banca Ifis Market Watch NPL (Q2 2025)</div>""",
      """function ease(x){return x<0?0:x>1?1:1-Math.pow(1-x,3)}
window.tick=function(ms){var t=ms/1000;
document.getElementById('c1').textContent=Math.round(300000*ease((t-0.8)/2.4)).toLocaleString('en-US');
document.getElementById('c2').textContent='€'+Math.round(373*ease((t-8.0)/2.0))+'bn';}""")

# ---------------------------------------------------------------- s3 the problem today
people = "".join(f'''<div class="person in" style="left:{140 + i*210}px;animation-delay:{.3 + i*.15:.2f}s"><svg viewBox="0 0 100 120" width="150"><circle cx="50" cy="34" r="24" fill="#a9cbf0"/><path d="M8 118c4-34 22-50 42-50s38 16 42 50z" fill="#3e74b4"/></svg><div>Bidder {i+1}</div></div>''' for i in range(3))
coins = "".join(f'<div class="coin fly" style="left:{180 + i*210}px;top:520px;--dx:{870 - i*140}px;--dy:-110px;animation-delay:{1.0 + i*.25:.2f}s">€</div>' for i in range(3))
scene("s3", """
.t{position:absolute;left:0;right:0;top:70px;text-align:center}
.person{position:absolute;top:300px;width:170px;text-align:center;font-size:32px;color:#d7e6f7}
.fly{opacity:0;animation:fly 1.4s cubic-bezier(.5,0,.6,1) both}
@keyframes fly{0%{opacity:0;transform:none}12%{opacity:1}100%{opacity:1;transform:translate(var(--dx),var(--dy)) scale(.8)}}
.vault{position:absolute;left:960px;top:290px;width:300px;height:300px;border-radius:30px;background:linear-gradient(#3a4558,#232b38);border:5px solid #59677d;display:flex;align-items:center;justify-content:center}
.clock{width:150px;height:150px;border-radius:50%;border:8px solid #8fa3bd;position:relative}
.hand{position:absolute;left:67px;top:16px;width:8px;height:58px;background:#ffb547;border-radius:4px;transform-origin:4px 58px;animation:spin 2s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.weeks{position:absolute;left:960px;top:610px;width:300px;text-align:center;font-size:30px;color:#9fb6d2}
.list{position:absolute;left:1340px;top:270px;width:520px}
.it{display:flex;gap:18px;align-items:flex-start;font-size:38px;line-height:1.25;margin-bottom:46px}
.ic{flex:0 0 56px;height:56px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:900}
""", '<div class="bg"></div><div class="dots"></div><div class="glow" style="left:600px;top:200px"></div>' + """
<div class="t h in" style="animation-delay:.1s">Today, deposits wait, and trust is thin</div>""" + people + coins + """
<div class="vault in" style="animation-delay:.6s"><div class="clock"><div class="hand"></div></div></div><div class="weeks in" style="animation-delay:2s">money tied up</div>
<div class="list">
<div class="it slide" style="animation-delay:2.9s"><div class="ic" style="background:#5a4a1c;color:#ffd76a">⏳</div><div>Unsuccessful bidders wait to get their deposit back.</div></div>
<div class="it slide" style="animation-delay:5.0s"><div class="ic" style="background:#5c3a14;color:#ffb547">✕</div><div>Auctions get <span class="amber">cancelled or suspended</span>.</div></div>
<div class="it slide" style="animation-delay:7.0s"><div class="ic" style="background:#5c2420;color:#ff7a6b">!</div><div>Some winners <span class="red">never pay</span> the rest.</div></div>
</div>""")

# ---------------------------------------------------------------- s4 how it works
vals = "".join(f'<div class="val" style="left:{1460 + 150*__import__("math").cos(a):.0f}px;top:{520 + 150*__import__("math").sin(a):.0f}px;animation-delay:{5.0 + i*.25:.2f}s"></div>' for i, a in enumerate([-1.57 + k*1.2566 for k in range(5)]))
scene("s4", """
.t{position:absolute;left:0;right:0;top:56px;text-align:center}
.lab{position:absolute;font-size:32px;font-weight:700;text-align:center}
.vault{position:absolute;left:150px;top:300px;width:400px;height:400px;border-radius:40px;background:radial-gradient(circle at 50% 40%,#1d5aa0,#0b2a50);border:4px solid #4f8fd6;box-shadow:0 0 0 0 rgba(98,224,163,.0);animation:vglow 2s ease-in-out 2.4s both}
@keyframes vglow{to{box-shadow:0 0 70px 6px rgba(98,224,163,.45);border-color:#62e0a3}}
.lock{position:absolute;left:115px;top:95px;width:170px;height:190px}
.cin{opacity:0;animation:cin 1.2s cubic-bezier(.5,0,.6,1) both}
@keyframes cin{0%{opacity:0;transform:translate(-160px,var(--y0)) scale(.9)}15%{opacity:1}100%{opacity:0;transform:translate(150px,0) scale(.5)}}
.doc{position:absolute;left:690px;top:280px;width:560px;padding:30px 34px;background:#f4f1e8;color:#1f2a36;border-radius:16px;box-shadow:0 24px 70px rgba(0,0,0,.45);transform:rotate(-1.5deg)}
.doc .hd{font-size:26px;font-weight:800;color:#0d5eaf;margin-bottom:14px;letter-spacing:.5px}
.doc .ln{font-family:ui-monospace,Menlo,monospace;font-size:30px;padding:10px 8px;border-bottom:1px dashed #c9c2ae;border-radius:6px}
.hl{animation:hl 1.2s ease-out both}@keyframes hl{0%{background:rgba(255,215,106,0)}40%{background:rgba(255,215,106,.55)}100%{background:rgba(255,215,106,.28)}}
.val{position:absolute;width:74px;height:74px;border-radius:50%;background:radial-gradient(#62e0a3,#1d6b47);border:4px solid #b9f3d6;opacity:0;animation:pop .5s cubic-bezier(.2,1.6,.4,1) both}
.beam{position:absolute;left:1250px;top:490px;height:6px;width:0;background:linear-gradient(90deg,rgba(98,224,163,0),#62e0a3);border-radius:3px;animation:beam .8s ease-out 6.4s both;transform-origin:left}
@keyframes beam{to{width:180px}}
.chk{position:absolute;left:1325px;top:740px;width:320px;text-align:center;font-size:28px;color:#d7e6f7;line-height:1.4}
.twice{position:absolute;left:150px;right:150px;top:880px;padding:22px 30px;display:flex;align-items:center;justify-content:center;gap:26px;font-size:40px}
.tk{width:58px;height:58px;border-radius:50%;background:#1d6b47;border:3px solid #62e0a3;display:inline-flex;align-items:center;justify-content:center;font-weight:900;color:#d9ffe9}
.line{height:4px;width:200px;background:repeating-linear-gradient(90deg,#ffd76a 0 14px,transparent 14px 24px)}
""", '<div class="bg"></div><div class="dots"></div><div class="glow" style="left:100px;top:100px"></div>' + """
<div class="t h in" style="animation-delay:.1s">How AuctionDeposit works</div>
<div class="in" style="animation-delay:.6s"><div class="vault"><svg class="lock" viewBox="0 0 34 38"><path d="M9 16V11a8 8 0 0 1 16 0v5" stroke="#ffd76a" stroke-width="3.5" fill="none"/><rect x="4" y="16" width="26" height="20" rx="4" fill="#ffd76a"/><circle cx="17" cy="25" r="3" fill="#6d4908"/><rect x="15.6" y="26" width="2.8" height="6" fill="#6d4908"/></svg></div></div>
<div class="lab in" style="left:150px;width:400px;top:720px;animation-delay:1.2s">One escrow on <span class="gold">GenLayer</span></div>""" +
      "".join(f'<div class="coin cin" style="left:240px;top:{430 + k*40}px;--y0:{(k-1)*60}px;animation-delay:{1.4 + k*.35:.2f}s">€</div>' for k in range(3)) + """
<div class="doc in" style="animation-delay:4.0s"><div class="hd">OFFICIAL AUCTION RECORD</div>
<div class="ln">Auction: EA-24117</div><div class="ln hl" style="animation-delay:7.0s">Status: Completed</div><div class="ln hl" style="animation-delay:7.6s">Winning bidder: B-1102</div><div class="ln hl" style="animation-delay:8.2s">Balance: Paid in full</div></div>
""" + vals + """<div class="beam"></div>
<div class="lab in" style="left:1310px;width:340px;top:250px;animation-delay:5.0s">Validators read it</div>
<div class="chk in" style="animation-delay:9.6s">AI only <b>copies</b> the lines.<br>Code <b>checks</b> every copy.</div>
<div class="twice glass in" style="animation-delay:12.6s"><span>Nothing moves on one look</span><span class="tk pop" style="animation-delay:13.6s">✓</span><span class="line"></span><span class="tk pop" style="animation-delay:14.6s">✓</span><span class="gold"><b>seen twice, 10 minutes apart</b></span></div>""")

# ---------------------------------------------------------------- s5 the outcomes
def row(top, delay, title, items):
    chips = "".join(f'<div class="dest pop" style="animation-delay:{delay + 1.0 + j*.5:.2f}s;background:{c}">{txt}</div>' for j, (txt, c) in enumerate(items))
    return f'<div class="row glass slide" style="top:{top}px;animation-delay:{delay:.2f}s"><div class="what">{title}</div><div class="arrow">→</div><div class="dests">{chips}</div></div>'


scene("s5", """
.t{position:absolute;left:0;right:0;top:60px;text-align:center}
.row{position:absolute;left:140px;width:1640px;height:200px;display:flex;align-items:center;padding:0 46px;gap:34px}
.what{width:560px;font-size:48px;font-weight:800}.arrow{font-size:70px;color:#ffd76a}
.dests{display:flex;gap:22px;flex-wrap:wrap}.dest{padding:16px 26px;border-radius:16px;font-size:34px;font-weight:700}
""", '<div class="bg"></div><div class="dots"></div><div class="glow" style="left:900px;top:300px"></div>' + """
<div class="t h in" style="animation-delay:.1s">The record decides. <span class="gold">Code pays.</span></div>""" +
      row(240, 1.4, "Won and paid", [("Unsuccessful bidders refunded", "#1d6b47"), ("Winner's deposit → bank, as part of the price", "#8a5a14")]) +
      row(480, 8.6, "Winner walks away", [("Unsuccessful bidders refunded", "#1d6b47"), ("Deposit → bank, as the penalty", "#8a5a14")]) +
      row(720, 12.3, "Cancelled or suspended", [("Everyone refunded", "#1d6b47")]))

# ---------------------------------------------------------------- s6 the proof
cases = ["Won and paid", "Winner defaulted", "Payment never shown", "Cancelled", "Suspended by the court",
         "Adjourned, then won", "No bids", "Winner outside the escrow", "Planted instruction ignored", "Wrong page: refund"]
grid = "".join(f'<div class="case pop{" star" if i == 8 else ""}" style="animation-delay:{4.6 + i*.3:.2f}s"><span class="ck">✓</span>{t}</div>' for i, t in enumerate(cases))
scene("s6", """
.t{position:absolute;left:0;right:0;top:66px;text-align:center}
.nums{position:absolute;left:0;right:0;top:210px;display:flex;justify-content:center;gap:120px;text-align:center}
.nums .big{font-size:140px;font-weight:900;color:#ffd76a;line-height:1;font-variant-numeric:tabular-nums}.nums .l{font-size:34px;color:#d7e6f7;margin-top:8px}
.grid{position:absolute;left:170px;top:540px;width:1580px;display:grid;grid-template-columns:repeat(5,1fr);gap:20px}
.case{padding:20px;font-size:27px;line-height:1.25;min-height:110px;border-radius:18px;background:rgba(9,32,62,.8);border:1.5px solid rgba(140,190,255,.3)}
.ck{display:inline-flex;width:40px;height:40px;border-radius:50%;background:#1d6b47;color:#d9ffe9;align-items:center;justify-content:center;font-weight:900;margin-right:10px}
.star{animation:pop .55s cubic-bezier(.2,1.6,.4,1) 7.0s both,star 1.4s ease-in-out 10.4s both}
@keyframes star{50%{box-shadow:0 0 50px 8px rgba(255,215,106,.6);border-color:#ffd76a;transform:scale(1.08)}100%{box-shadow:0 0 30px 2px rgba(255,215,106,.35);border-color:#ffd76a}}
.note{position:absolute;left:0;right:0;top:880px;text-align:center;font-size:38px;color:#e6f0fb}
""", '<div class="bg"></div><div class="dots"></div><div class="glow" style="left:500px;top:0"></div>' + """
<div class="t h in" style="animation-delay:.1s">Tested live on GenLayer</div>
<div class="nums"><div class="in" style="animation-delay:.6s"><div class="big" id="n1">0</div><div class="l">fictional auctions</div></div>
<div class="in" style="animation-delay:2.4s"><div class="big" id="n2">0</div><div class="l">transactions on Testnet Bradbury</div></div>
<div class="in" style="animation-delay:4.0s"><div class="big">100%</div><div class="l">finalized, 0 GEN left behind</div></div></div>
<div class="grid">""" + grid + """</div>
<div class="note in" style="animation-delay:8.2s">Every case ended as planned, on <b>Studio</b> and on <b>Bradbury</b>.</div>""",
      """function ease(x){return x<0?0:x>1?1:1-Math.pow(1-x,3)}
window.tick=function(ms){var t=ms/1000;document.getElementById('n1').textContent=Math.round(10*ease((t-0.8)/1.2));document.getElementById('n2').textContent=Math.round(78*ease((t-2.6)/1.8));}""")

# ---------------------------------------------------------------- s7 end card on the photo
scene("s7", """
.shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(4,16,31,.7) 0%,rgba(4,16,31,.25) 45%,rgba(4,16,31,.6) 100%)}
.c{position:absolute;left:0;right:0;top:90px;text-align:center}
.c .h{font-size:110px;text-shadow:0 6px 30px rgba(0,0,0,.6)}
.url{display:inline-block;margin-top:26px;padding:14px 34px;border-radius:40px;background:rgba(9,32,62,.75);border:2px solid #ffd76a;font-size:44px;color:#ffd76a;font-weight:700}
.foot{position:absolute;left:0;right:0;bottom:70px;text-align:center;font-size:28px;color:#fff;text-shadow:0 2px 10px rgba(0,0,0,.9)}
""", '<div class="photo"></div><div class="shade"></div>' + flag(1600, 700, 230) + """
<div class="c"><div class="h in" style="animation-delay:.3s">AuctionDeposit</div>
<div class="s in" style="animation-delay:.8s;color:#fff;text-shadow:0 2px 12px rgba(0,0,0,.8)">Bid deposits that move only on the official record</div>
<div class="url pop" style="animation-delay:1.5s">brilliantnodes.github.io/auction-deposit</div></div>
<div class="foot in" style="animation-delay:2.2s">On <span class="gold">GenLayer</span>, by Brilliant Nodes · Fictional demo · Test GEN only</div>""" + CREDIT)

(OUT / "durations.txt").write_text("\n".join(f"{k} {v}" for k, v in DUR.items()))
print(DUR, round(sum(DUR.values()), 1))
