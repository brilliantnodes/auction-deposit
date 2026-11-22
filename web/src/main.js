import "./style.css";
import { createClient, createAccount, generatePrivateKey, abi } from "genlayer-js";
import { studionet } from "genlayer-js/chains";

// The visitor contract on GenLayer Studio (tools/deploy_visitor.py): the same
// source as the live runs, record host brilliantnodes.github.io, minimum
// confirmation 60 s. Record pages: tools/make_try_pages.py.
const CONTRACT = "0x01bdF97620fFdAe7391df6f98ba8889604d852F0"; // v1.1 (a value copied with its label is read); v1 visitor contract: 0xf19d1C798A3D6DBd5D73F60F001A41C630cf15c0
const EXPLORER = "https://explorer-studio.genlayer.com";
const SITE = "https://brilliantnodes.github.io/auction-deposit";
const SLOT = 15 * 60;
const RESULT_AT = 3 * 60; // the record shows the result from D + 3 min
const CHANGE_AT = 10 * 60; // and the balance change from D + 10 min
const CONFIRM = 120;
const BALANCE_SECONDS = 15 * 60;
const REFUND_AFTER = 40 * 60;
const LEAD = 6 * 60; // at least this long to set up deposits before the auction starts
const PAGES_FROM = 1795239900; // first and last slot with a published record page
const PAGES_TO = 1798695000;
const G = 10n ** 18n;
const STORIES = {
  paid: { letter: "P", title: "Won, balance paid", property: "Flat 2, 7 Marigold Lane, Velmora",
    text: "B-201 wins; the record later shows the balance paid in full. B-202 gets its deposit back; B-201's deposit goes to the creditor as part of the price." },
  default: { letter: "D", title: "Won, buyer in default", property: "Shop 1, 30 Thistledown Road, Velmora",
    text: "B-201 wins but never pays; the record later shows the buyer in default. B-202 gets its deposit back; B-201's deposit goes to the creditor as the penalty." },
  cancelled: { letter: "C", title: "Auction cancelled", property: "House, 4 Orchard Close, Brindlemere",
    text: "The record shows the auction cancelled. Both bidders get their deposits back." },
};
const CODES = { bidder1: "B-201", bidder2: "B-202" };

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = String(text); return n; };
const link = (href, text) => { const a = el("a", null, text); a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer"; return a; };
const RPC = studionet.rpcUrls.default.http[0];
const reader = createClient({ chain: studionet });
function plain(v) {
  if (v instanceof Map) return Object.fromEntries([...v.entries()].map(([k, x]) => [k, plain(x)]));
  if (Array.isArray(v)) return v.map(plain);
  if (typeof v === "bigint") return Number(v) > Number.MAX_SAFE_INTEGER ? v.toString() : Number(v);
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, plain(x)]));
  return v;
}
const read = async (fn, args = []) => plain(await reader.readContract({ address: CONTRACT, functionName: fn, args }));
const short = (e) => String((e && (e.shortMessage || e.message)) || e).slice(0, 300);
const nowS = () => Math.floor(Date.now() / 1000);
const pad = (n) => String(n).padStart(2, "0");
const hhmm = (t) => { const d = new Date(t * 1000); return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`; };
const hhmmss = (t) => { const d = new Date(t * 1000); return `${hhmm(t)}:${pad(d.getUTCSeconds())} UTC`; };
const local = (t) => new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
function inWords(s) { s = Math.max(0, Math.round(s)); const m = Math.floor(s / 60); return m >= 1 ? `${m} min ${pad(s % 60)} s` : `${s} s`; }
function gen(wei) {
  const n = BigInt(wei); const w = n / G; const f = (n % G).toString().padStart(18, "0").slice(0, 4).replace(/0+$/, "");
  return `${w}${f ? "." + f : ""} GEN`;
}
const store = { get: (k) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch {} } };

// ------------------------------------------------------------ accounts

const roles = { creditor: null, bidder1: null, bidder2: null };
function useRole(role) {
  let key = store.get(`ad.temp.${role}`);
  if (!key) { key = generatePrivateKey(); store.set(`ad.temp.${role}`, key); }
  const account = createAccount(key);
  roles[role] = { client: createClient({ chain: studionet, account }), address: account.address };
  $(`${role}-addr`).textContent = account.address;
}
async function faucet(address) {
  const body = JSON.stringify({ jsonrpc: "2.0", id: 1, method: "sim_fundAccount", params: [address, 20000000000000000000] });
  const r = await fetch(RPC, { method: "POST", headers: { "content-type": "application/json" }, body });
  const j = await r.json();
  if (j.error) throw new Error(j.error.message || "faucet error");
}
async function refreshBalances() {
  for (const role of Object.keys(roles)) {
    const r = roles[role];
    const box = $(`${role}-bal`);
    if (!r) { box.textContent = ""; continue; }
    try {
      const [bal, claim] = await Promise.all([reader.getBalance({ address: r.address }), read("get_claimable", [r.address])]);
      box.textContent = `Wallet: ${gen(bal)}. Credited by the contract: ${gen(claim)}.`;
      if (BigInt(claim) > 0n) {
        const b = el("button", "ghost", "Withdraw");
        b.type = "button";
        b.addEventListener("click", () => send(role, "withdraw", [0], 0n, `Withdraw ${gen(claim)} (${role})`));
        box.append(" ", b);
      }
    } catch { /* keep the last figures */ }
  }
}
const acctError = (m) => { $("acct-error").textContent = m; $("acct-error").hidden = !m; };
$("btn-setup").addEventListener("click", async () => {
  acctError("");
  $("btn-setup").disabled = true;
  try {
    for (const role of Object.keys(roles)) {
      if (!roles[role]) useRole(role);
      const bal = await reader.getBalance({ address: roles[role].address });
      if (BigInt(bal) < 3n * G) await faucet(roles[role].address);
    }
    await new Promise((x) => setTimeout(x, 1500));
  } catch (e) { acctError(`Faucet: ${short(e)}. Try again in a moment.`); }
  $("btn-setup").disabled = false;
  refreshBalances();
});
for (const role of Object.keys(roles)) if (store.get(`ad.temp.${role}`)) useRole(role);

// ------------------------------------------------------------- stories

let story = store.get("ad.story") || "paid";
function drawStories() {
  const box = $("stories");
  box.replaceChildren();
  for (const [key, s] of Object.entries(STORIES)) {
    const lab = el("label", "story");
    const r = el("input"); r.type = "radio"; r.name = "story"; r.value = key; r.checked = key === story;
    r.addEventListener("change", () => { story = key; store.set("ad.story", key); drawSlot(); });
    lab.append(r, el("strong", null, ` ${s.title}. `), el("span", "small", s.text));
    box.append(lab);
  }
}
function nextSlot() { return (Math.floor((nowS() + LEAD) / SLOT) + 1) * SLOT; }
const auctionId = (st, d) => { const x = new Date(d * 1000); return `TRY-${STORIES[st].letter}-${String(x.getUTCFullYear()).slice(2)}${pad(x.getUTCMonth() + 1)}${pad(x.getUTCDate())}${pad(x.getUTCHours())}${pad(x.getUTCMinutes())}`; };
const recordUrl = (st, id) => `${SITE}/record/try/${st}/${id.toLowerCase()}.html`;
function drawSlot() {
  const d = nextSlot();
  const ok = d >= PAGES_FROM && d <= PAGES_TO;
  $("slot-note").replaceChildren();
  if (!ok) { $("slot-note").innerHTML = 'No record page is published for the next slot. The finished live runs are on the <a href="../">main page</a>.'; $("btn-open").disabled = true; return; }
  const id = auctionId(story, d);
  $("slot-note").append(`Auction ${id} starts at ${hhmm(d)} UTC (your time ${local(d)}, in ${inWords(d - nowS())}); deposits close then. `, link(recordUrl(story, id), "See its record page"), ".");
  $("btn-open").disabled = false;
}
$("btn-open").addEventListener("click", async () => {
  if (!roles.creditor) return acctError("Set up the accounts first.");
  const d = nextSlot();
  const id = auctionId(story, d);
  const res = await send("creditor", "open_auction", [id, STORIES[story].property, recordUrl(story, id), G, CONFIRM, d, BALANCE_SECONDS, d + REFUND_AFTER], 0n, `Open auction ${id}`);
  let aid = res && res.answer && res.answer.id;
  if (res && !aid) { try { const ids = await read("get_auctions_of", [roles.creditor.address]); aid = ids[ids.length - 1]; } catch {} }
  if (aid) { store.set("ad.current", String(aid)); openAuction(String(aid)); }
});

// ------------------------------------------------------- the auction

let current = null; // { id, a }
let auto = false, autoCount = 0, lastEnd = 0; // "keep reading for me": the page sends each reading when it is due
const AUTO_MAX = 8;
async function openAuction(id) {
  try { const a = await read("get_auction", [id]); current = { id, a }; render(); $("auction").hidden = false; }
  catch (e) { current = null; $("auction").hidden = true; alert(`Could not open auction ${id}: ${short(e)}`); }
}
async function reload() { if (current) { try { current.a = await read("get_auction", [current.id]); render(); } catch {} } refreshBalances(); }
$("a-reload").addEventListener("click", reload);
$("lookup").addEventListener("submit", (ev) => { ev.preventDefault(); const v = $("lookup-id").value.trim(); if (/^\d+$/.test(v)) openAuction(v); });

const storyOf = (a) => Object.keys(STORIES).find((k) => (a.terms.auction_id || "").startsWith(`TRY-${STORIES[k].letter}-`));
function kv(dl, rows) { dl.replaceChildren(); for (const [k, v] of rows) { dl.append(el("dt", null, k)); const dd = el("dd"); if (v instanceof Node) dd.append(v); else dd.textContent = v; dl.append(dd); } }
function render() {
  const a = current.a, t = a.terms;
  $("a-title").textContent = `Auction #${a.id}: ${t.auction_id}`;
  $("a-state").textContent = a.state;
  $("a-state").className = `badge ${a.state === "SETTLED" || a.state === "CANCELLED" ? "ok" : "live"}`;
  kv($("a-money"), [["Deposited", gen(a.money.deposited)], ["Held in escrow", gen(a.money.held)], ["Paid to the creditor", gen(a.money.to_creditor)], ["Refunded to bidders", gen(a.money.refunded)], ["Winner confirmed", a.winner || "not yet"], ["Readings so far", String(a.readings)]]);
  kv($("a-terms"), [["Property", t.property_ref], ["Record page", link(t.record_url, "open the page the validators read")], ["Deposit", gen(t.deposit)], ["Deposits close", `${hhmmss(t.deposits_close)}`], ["Seen twice, at least", `${t.confirm_seconds} s apart`], ["Winner must pay within", `${Math.round(t.balance_seconds / 60)} min of a confirmed win`], ["Everyone refunded if no outcome by", hhmmss(t.refund_by)], ["Creditor", a.creditor]]);
  const bl = $("a-bidders"); bl.replaceChildren();
  const codes = Object.keys(a.bidders || {});
  if (!codes.length) bl.append(el("li", "small", "No deposits yet."));
  for (const c of codes) bl.append(el("li", null, `${c}: ${gen(a.bidders[c].held)} held · ${a.bidders[c].addr}`));
  const lg = $("a-log"); lg.replaceChildren();
  for (const e of a.log || []) { const li = el("li"); li.append(el("strong", null, `${hhmmss(e.at)} ${e.what}`), el("span", null, e.note ? ` ${String(e.note).replace(/(\d+) wei/g, (_m, n) => gen(n))}` : "")); lg.append(li); }
  drawActions();
}

function nextStep() {
  const a = current.a, t = a.terms, d = t.deposits_close, now = nowS();
  const st = storyOf(a);
  const missing = Object.entries(CODES).filter(([, c]) => !(a.bidders || {})[c]).map(([r]) => r);
  if (a.state === "SETTLED" || a.state === "CANCELLED") return { text: `Done: ${a.settled_reason || a.state}. Each party withdraws what was credited to it (buttons under Accounts).`, can: [] };
  if (a.state === "OPEN" && now < d) {
    return { text: missing.length ? `Lodge the deposits before ${hhmmss(d)} (in ${inWords(d - now)}).` : `Both deposits are in. The auction starts at ${hhmmss(d)} (in ${inWords(d - now)}); the result appears on the record 3 minutes later.`, can: missing.map((r) => `deposit:${r}`) };
  }
  if (now < d + RESULT_AT) return { text: `The auction is under way. The record shows the result from ${hhmmss(d + RESULT_AT)} (in ${inWords(d + RESULT_AT - now)}). Then read it twice, at least ${t.confirm_seconds} s apart.`, can: [] };
  if (a.state === "WON_PENDING" && st !== "cancelled" && now < d + CHANGE_AT) return { text: `Winner ${a.winner} confirmed: the losing deposit is refunded and the winner's is held. The record shows the balance outcome from ${hhmmss(d + CHANGE_AT)} (in ${inWords(d + CHANGE_AT - now)}); then read twice again.`, can: ["settle"] };
  const run = a.run;
  if (run && run.at && now < run.at + t.confirm_seconds + 10) return { text: `First look recorded at ${hhmmss(run.at)}. Read again from ${hhmmss(run.at + t.confirm_seconds + 10)} (in ${inWords(run.at + t.confirm_seconds + 10 - now)}) to confirm it.`, can: ["settle"] };
  const lastLog = (a.log || []).slice(-1)[0];
  const empty = lastLog && lastLog.what === "READING" && /^N\d_/.test(lastLog.note || "") ? `The last reading found nothing usable (${lastLog.note}), so nothing moved; this is the safe outcome. ` : "";
  return { text: empty + (run ? "Read the record again to confirm what the first look showed." : "Read the record: validators open the page and copy the status, winner and balance."), can: ["read", "settle"] };
}
const HELP = {
  read: ["Read the record", "Every validator opens the record page and copies three lines; code checks them; validators must agree exactly. One to three minutes."],
  settle: ["Apply deadlines", "Applies any deadline that has passed, without reading the page."],
};
function drawActions() {
  const box = $("a-actions"); box.replaceChildren();
  const ns = nextStep();
  $("a-next").textContent = ns.text;
  const done = current.a.state === "SETTLED" || current.a.state === "CANCELLED";
  if (!done && Date.now() / 1000 >= current.a.terms.deposits_close) {
    const lab = el("label", "auto");
    const cb = el("input"); cb.type = "checkbox"; cb.checked = auto;
    cb.addEventListener("change", () => { auto = cb.checked; autoCount = 0; drawActions(); });
    lab.append(cb, el("strong", null, " Keep reading for me. "), el("span", "small", `This page sends each reading as soon as it is due, and reads again after a reading that found nothing usable (at most ${AUTO_MAX} readings; ${autoCount} sent so far). Keep the page open.`));
    box.append(lab);
  }
  if (auto && !busy && ns.can.includes("read") && autoCount < AUTO_MAX && Date.now() - lastEnd > 20000) {
    const who = roles.bidder2 ? "bidder2" : roles.creditor ? "creditor" : null;
    if (who) { autoCount += 1; setTimeout(() => send(who, "read_record", [current.id], 0n, `Read the record (automatic reading ${autoCount} of at most ${AUTO_MAX})`), 0); }
  }
  if (done) auto = false;
  for (const c of ns.can) {
    const row = el("div", "act");
    let label, help, fn;
    if (c.startsWith("deposit:")) {
      const role = c.split(":")[1];
      label = `${role === "bidder1" ? "Bidder 1" : "Bidder 2"}: deposit 1 GEN as ${CODES[role]}`;
      help = "Sends exactly the deposit and the terms' fingerprint; a wrong amount is refused and credited straight back.";
      fn = () => roles[role] ? send(role, "deposit", [current.id, CODES[role], current.a.digest], current.a.terms.deposit ? BigInt(current.a.terms.deposit) : G, `${CODES[role]} lodges the deposit`) : acctError("Set up the accounts first.");
    } else {
      [label, help] = HELP[c];
      const who = roles.bidder2 ? "bidder2" : roles.creditor ? "creditor" : null;
      fn = () => who ? send(who, c === "read" ? "read_record" : "settle", [current.id], 0n, c === "read" ? "Read the record" : "Apply deadlines") : acctError("Set up the accounts first.");
    }
    const b = el("button", c === "settle" ? "ghost" : null, label); b.type = "button"; b.addEventListener("click", fn);
    row.append(b, el("p", "small", help));
    box.append(row);
  }
}

// ------------------------------------------------- transaction lifecycle

const STEPS = [["SENT", "Sent", "Signed in this browser and sent."], ["PENDING", "Queued", "Waiting for a leader."], ["PROPOSING", "Leader works", "One validator runs the call; for a reading it opens the record page now."], ["COMMITTING", "Validators check", "The others run it on their own and vote."], ["REVEALING", "Votes revealed", "Votes are opened and counted."], ["ACCEPTED", "Accepted", "A majority agreed; the new state is recorded and any payout credited."], ["FINALIZED", "Finalized", "The appeal window has passed. A withdrawal reaches the wallet now."]];
const ORDER = STEPS.map((s) => s[0]);
const BAD = { UNDETERMINED: "The validators did not agree, so nothing changed. Read again.", CANCELED: "Cancelled; nothing changed.", LEADER_TIMEOUT: "The leader did not answer in time; check the explorer before trying again.", VALIDATORS_TIMEOUT: "The validators did not answer in time; check the explorer before trying again." };
const statusOf = (tx) => String(tx?.statusName ?? tx?.status_name ?? "").toUpperCase();
function drawSteps(cur, failed) {
  const ol = $("steps"); ol.replaceChildren(); const at = ORDER.indexOf(cur);
  STEPS.forEach(([key, title, help], i) => { const li = el("li"); li.className = failed && i >= Math.max(at, 0) ? (i === Math.max(at, 0) ? "failed" : "todo") : i < at ? "done" : i === at ? (key === "FINALIZED" ? "done" : "now") : "todo"; li.append(el("strong", null, title), el("span", null, help)); ol.append(li); });
}
function answer(tx) {
  try {
    const lr = tx?.consensus_data?.leader_receipt; const r = (Array.isArray(lr) ? lr[0] : lr)?.result;
    if (!r) return null;
    if (r.status === "rollback") return { reverted: String(r.payload || "") };
    if (typeof r.raw === "string") {
      // Studio returns the result as base64: one result-code byte, then the value.
      const bytes = Uint8Array.from(atob(r.raw), (ch) => ch.charCodeAt(0));
      if (bytes[0] === 0) return plain(abi.calldata.decode(bytes.slice(1)));
      return { reverted: new TextDecoder().decode(bytes.slice(1)) || "the call was refused" };
    }
    const p = r.payload;
    if (p && typeof p === "object" && "readable" in p) { try { return JSON.parse(p.readable); } catch { return null; } }
    return null;
  } catch { return null; }
}
let busy = false;
async function send(role, fn, args, value, what) {
  if (busy) return null;
  const who = roles[role];
  if (!who) { acctError("Set up the accounts first."); return null; }
  busy = true; document.querySelectorAll("#a-actions button, #btn-open").forEach((b) => (b.disabled = true));
  $("life").hidden = false; $("life-what").textContent = what; $("life-hash").replaceChildren(); $("life-note").textContent = "Signing in this browser…"; drawSteps("", false);
  let hash, err;
  try { hash = await who.client.writeContract({ address: CONTRACT, functionName: fn, args, value: value || 0n }); } catch (e) { err = e; }
  let out = null;
  if (err) { drawSteps("SENT", true); $("life-note").textContent = `The network did not confirm the send (${short(err)}). Studio's gateway sometimes refuses for a moment when it is busy. It may or may not have gone out, so this page does not resend it: press Reload in a minute and check before trying again.`; auto = false; }
  else {
    $("life-hash").append("Transaction: ", el("code", null, hash), " · ", link(`${EXPLORER}/tx/${hash}`, "view on the explorer"));
    drawSteps("SENT", false);
    let last = "SENT", fin = null; const t0 = Date.now();
    while (Date.now() - t0 < 10 * 60 * 1000) {
      $("life-note").textContent = `Sent ${Math.round((Date.now() - t0) / 1000)} s ago. ${fn === "read_record" ? "A reading takes one to three minutes." : "Usually under a minute."}`;
      await new Promise((r) => setTimeout(r, 6000));
      let tx; try { tx = await reader.getTransaction({ hash }); } catch { continue; }
      const st = statusOf(tx);
      if (st && st !== last && ORDER.includes(st)) { last = st; drawSteps(st, false); }
      if (st === "ACCEPTED" || st === "FINALIZED") { fin = { ok: true, tx }; break; }
      if (BAD[st]) { fin = { ok: false, st }; break; }
    }
    if (!fin) $("life-note").textContent = "Not settled after ten minutes. It may still complete; press Reload later.";
    else if (!fin.ok) { drawSteps(last, true); $("life-note").textContent = BAD[fin.st]; }
    else {
      const ans = answer(fin.tx);
      if (ans && ans.reverted) { drawSteps("REVEALING", true); $("life-note").textContent = `The contract refused this step: ${ans.reverted}`; }
      else if (ans && ans.ok === false) { drawSteps("REVEALING", true); $("life-note").textContent = `Refused and credited straight back: ${ans.error}`; }
      else if (ans && ans.reading) { const r = ans.reading; $("life-note").textContent = r.kind === "READ" ? `Validators agreed on: status ${r.status}${r.winner ? ", winner " + r.winner : ""}${r.balance ? ", balance " + r.balance : ""}.` : `No reading (${r.reason}); nothing moved. Read again.`; }
      else if (ans && ans.amount) $("life-note").textContent = `Accepted: ${gen(ans.amount)} is on its way; it reaches the wallet when the transaction is finalized.`;
      else $("life-note").textContent = "Accepted by a majority of validators.";
      out = { hash, answer: ans };
    }
  }
  busy = false; lastEnd = Date.now(); document.querySelectorAll("#a-actions button, #btn-open").forEach((b) => (b.disabled = false));
  await reload();
  return out;
}

// ----------------------------------------------------------------- start

$("foot-contract").append("Contract on GenLayer Studio: ", link(`${EXPLORER}/address/${CONTRACT}`, CONTRACT), " · ", link(`https://studio.genlayer.com/?import-contract=${CONTRACT}`, "open it in GenLayer Studio"));
drawStories();
drawSlot();
refreshBalances();
const qid = new URLSearchParams(location.search).get("id");
const start = qid && /^\d+$/.test(qid) ? qid : store.get("ad.current");
if (start) openAuction(start);
setInterval(() => { drawSlot(); if (current) drawActions(); }, 5000);
setInterval(() => { if (current && !busy && document.visibilityState === "visible") reload(); }, 60000);
