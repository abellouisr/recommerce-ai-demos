"""Recommerce AI demos – password-protected public version of two prototypes:

1. Dispute Copilot  – partner dispute email → checked decision → drafted reply → ticket
2. Stock Lookup     – plain-language stock questions answered from clean data via tools

All data is synthetic. Settings come from Streamlit secrets (see README).
"""
import hmac
import json
import os
import sqlite3
import tempfile
import threading
import time
import uuid
from datetime import date
from pathlib import Path

import streamlit as st

import ui

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Recommerce AI demos", layout="wide", initial_sidebar_state="expanded")


def secret(key, default=None):
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:  # no secrets file (local run)
        pass
    return os.environ.get(key, default)


# Hand the Claude settings to the copilot package before it is imported. Jira and Slack are never
# passed on: the public version shows ticket and alert previews instead of writing to real systems.
for _k in ("ANTHROPIC_API_KEY", "CLAUDE_MODEL", "ANTHROPIC_WORKSPACE_ID", "PRICE_IN_PER_MTOK", "PRICE_OUT_PER_MTOK"):
    if secret(_k):
        os.environ[_k] = secret(_k)
for _k in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEY", "SLACK_WEBHOOK_URL"):
    os.environ.pop(_k, None)

from copilot import config, data_gen, integrations, llm, store  # noqa: E402
import stock_chat  # noqa: E402
import stock_server  # noqa: E402

config.JIRA_BASE_URL = config.SLACK_WEBHOOK_URL = None
DAILY_BUDGET_USD = float(secret("DAILY_BUDGET_USD", "3"))
SESSION_CLAUDE_LIMIT = int(secret("SESSION_CLAUDE_LIMIT", "60"))  # Claude-backed actions per visitor
EXAMPLES = [
    "How many grade A or B iPhone 13 128GB, unlocked, do we have in the main warehouse?",
    "What iPhone supply arrives in the next two weeks, and in what grades?",
    "What is wrong with our raw stock export?",
    "Show stock value by site.",
    "Which Galaxy S22 lots under €200 are unlocked?",
]

# ------------------------------------------------------------------ shared state (all visitors)
@st.cache_resource
def shared():
    return {"day": str(date.today()), "spent": 0.0, "lock": threading.Lock()}


@st.cache_resource
def claude_status():
    if not config.ANTHROPIC_API_KEY:
        return {"ok": False, "message": "No Claude API key set – running in offline rules mode."}
    return dict(llm.check())


def budget_left():
    s = shared()
    with s["lock"]:
        if s["day"] != str(date.today()):
            s["day"], s["spent"] = str(date.today()), 0.0
        return max(0.0, DAILY_BUDGET_USD - s["spent"])


def record_spend(usd):
    s = shared()
    with s["lock"]:
        s["spent"] += usd or 0.0
    st.session_state.claude_actions = st.session_state.get("claude_actions", 0) + 1


def claude_allowed():
    """Claude is used when a key works, today's budget is not spent, and this visitor is under the limit."""
    return bool(claude_status().get("ok") and budget_left() > 0
                and st.session_state.get("claude_actions", 0) < SESSION_CLAUDE_LIMIT)


def run_case(c, did):
    use_claude = claude_allowed()
    with config.rules_only(not use_claude):
        res = store.run_case(c, did)
    if use_claude:
        record_spend(res["usage"]["cost_usd"])
    return res




def bar(data, height=220):
    import pandas as pd
    if not data:
        ui.html('<div class="empty">Nothing yet.</div>')
        return
    df = pd.DataFrame({"value": pd.Series(dict(data))}).sort_values("value")
    st.bar_chart(df, horizontal=True, color="#0d7a64", height=height)


ui.inject()


# ------------------------------------------------------------------ password gate
def gate():
    pw = secret("DEMO_PASSWORD")
    if not pw:
        st.error("This demo has no password set yet. Add DEMO_PASSWORD to the app's secrets.")
        st.stop()
    if st.session_state.get("authed"):
        return
    ui.html("<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']{display:none}</style>")
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        ui.html('<div class="login"><div class="eyebrow">Phone recommerce · AI prototypes</div>'
                '<h1 style="font-size:30px;margin:0 0 8px">Recommerce AI demos</h1>'
                '<p style="color:var(--muted);margin:0 0 18px">Two working prototypes by Abel Louis: a dispute copilot '
                'and a stock lookup assistant. All data is synthetic.</p></div>')
        tries = st.session_state.get("tries", 0)
        if tries >= 5:
            ui.html('<div class="status off">Too many attempts. Reload the page to try again.</div>')
            st.stop()
        with st.form("login", border=True):
            entered = st.text_input("Password", type="password", key="pw", placeholder="Password you were given")
            if st.form_submit_button("Open the demos", type="primary", use_container_width=True):
                if hmac.compare_digest(entered.encode(), pw.encode()):
                    st.session_state.authed = True
                    st.rerun()
                st.session_state.tries = tries + 1
                ui.html('<div class="status off">That password is not right. Check it and try again.</div>')
    st.stop()


gate()


# ------------------------------------------------------------------ per-visitor dispute database
def con():
    if "db_path" not in st.session_state:
        path = os.path.join(tempfile.gettempdir(), f"disputes_{uuid.uuid4().hex}.db")
        data_gen.build(path)
        st.session_state.db_path = path
    if "db" not in st.session_state:
        st.session_state.db = sqlite3.connect(st.session_state.db_path, check_same_thread=False)
    return st.session_state.db


def reset_disputes():
    for k in ("db", "db_path", "eval_rules", "eval_llm"):
        st.session_state.pop(k, None)


def go(page):
    st.session_state.page = page


# ------------------------------------------------------------------ sidebar
PAGES = {"Home": "Start here", "Dispute Copilot": "Partner disputes", "Stock Lookup": "Stock questions"}


def sidebar():
    with st.sidebar:
        ui.html('<div class="side-brand">Recommerce AI demos</div>'
                '<div class="side-sub">Prototypes by Abel Louis · synthetic data</div>')
        st.write("")
        choice = st.radio("Go to", list(PAGES), key="page", format_func=PAGES.get, label_visibility="collapsed")
        st.write("")
        on = claude_allowed()
        ui.html(f'<div class="side-status"><span class="dot {"" if on else "off"}"></span>'
                f'{"AI assistant on" if on else "AI assistant off · offline mode"}</div>')
        st.caption("Replies, tickets and alerts are previews. Nothing is sent.")
    return choice


# ------------------------------------------------------------------ home
def page_overview():
    ui.hero("Phone recommerce · AI prototypes", "Two AI assistants for a recommerce operation",
            "Both run on invented partners, devices, prices and stock. Decisions and numbers come from code that can "
            "be tested; Claude reads, writes and chooses what to look up.")
    ui.stats([("39", "labelled partner disputes"), ("100%", "correct on the test set with Claude"),
              ("≈1¢", "AI cost per dispute"), ("420 → 309", "raw stock rows → clean lots"),
              ("5", "read-only stock tools")])
    a, b = st.columns(2, gap="large")
    with a:
        ui.html('<div class="card"><div class="eyebrow">Demo 1 · Partner disputes</div><h3>Dispute Copilot</h3>'
                '<p>Partners email disputes about grades, payouts, locked or missing devices. The copilot reads the '
                'email, checks it against the device record, recommends a decision with the exact credit, drafts the '
                'reply and routes it to the owning team. A person approves every reply.</p>'
                + ui.tag("Claude reads and drafts") + ui.tag("Rules decide", "plain") + ui.tag("A person approves", "ext")
                + '<ul><li>Pick a dispute from the list and run the copilot</li><li>Edit the draft and approve it</li>'
                  '<li>See the ticket preview and the summary</li></ul></div>')
        st.button("Open partner disputes", type="primary", on_click=go, args=("Dispute Copilot",), use_container_width=True)
    with b:
        ui.html('<div class="card"><div class="eyebrow">Demo 2 · Stock questions</div><h3>Stock Lookup</h3>'
                '<p>A messy stock export is cleaned into sellable lots. Claude answers stock questions by calling '
                'five read-only tools, so every number comes from the data, with lot ids you can check.</p>'
                + ui.tag("Cleaned before use") + ui.tag("Read-only tools", "ext") + ui.tag("Traceable to raw rows", "data")
                + '<ul><li>Ask how many grade A/B iPhone 13s are in the main warehouse</li>'
                  '<li>Open the lookups under the answer</li><li>Check the numbers yourself in the next tab</li></ul></div>')
        st.button("Open stock questions", type="primary", on_click=go, args=("Stock Lookup",), use_container_width=True)
    ui.label("Architecture")
    d1, d2 = st.columns(2, gap="large")
    for col, name, title in ((d1, "Dispute_Copilot_Architecture.pdf", "Dispute Copilot architecture (PDF)"),
                             (d2, "Stock_Lookup_Architecture.pdf", "Stock Lookup architecture (PDF)")):
        p = ROOT / "docs" / name
        if p.exists():
            col.download_button(title, p.read_bytes(), file_name=name, mime="application/pdf", use_container_width=True)


# ------------------------------------------------------------------ dispute copilot
def render_email(d):
    ui.html(f'<div class="mail"><div class="head"><div class="subj">{ui.e(d["subject"])}</div>'
            f'<div class="meta">{ui.e(d["sender"])} · received {ui.e(d["received_at"][:16].replace("T", " "))}</div></div>'
            f'<div class="body" style="max-height:220px">{ui.e(d["body"])}</div></div>')


def render_result(r):
    esc = r["escalate"]
    credit = f"Credit €{r['credit_eur']:.2f}" if r["credit_eur"] else "No credit"
    tags = (ui.tag(ui.TOPIC.get(r["category"], r["category"]), "plain") + ui.tag(f"Route to {r['team']}", "ext")
            + ui.tag(f"Confidence {r['confidence']:.0%}", "plain"))
    reasons = (f'<div style="margin-top:6px;color:var(--warn);font-size:14px"><b>Needs a senior look:</b> '
               f'{ui.e("; ".join(r["escalation_reasons"]))}</div>') if esc else ""
    ui.html(f'<div class="decision {"esc" if esc else ""}"><div class="eyebrow">Copilot recommends</div>'
            f'<div class="big">{ui.e(ui.ACTION.get(r["action"], r["action"]))}</div>'
            f'<div style="font-size:16px;margin:-4px 0 10px;font-weight:600">{ui.e(credit)}</div>{tags}{reasons}</div>')
    passed = sum(c["ok"] for c in r["checks"])
    with st.expander(f"Checks against the device record · {passed} of {len(r['checks'])} passed"):
        rows = "".join(f'<div class="check"><span class="badge {"ok" if c["ok"] else "no"}">{"PASS" if c["ok"] else "NO"}</span>'
                       f'<div>{ui.e(c["check"])}<div class="d">{ui.e(c["detail"])}</div></div></div>' for c in r["checks"])
        ui.html(f'<div class="checks">{rows or "<div class=empty>No checks ran.</div>"}</div>')
        dev = r["facts"].get("device")
        if dev:
            fields = [("Model", dev["model"]), ("IMEI", dev["imei"]), ("Order", dev["order"]),
                      ("Quoted grade", dev["quoted_grade"]), ("Assigned grade", dev["assigned_grade"]),
                      ("Corrected grade", dev["corrected_grade"] or "–"), ("Battery", f"{dev['battery_health']}%"),
                      ("Paid", f"€{dev['paid_eur']}"), ("iCloud lock", "yes" if dev["fmi_lock"] else "no"),
                      ("MDM lock", "yes" if dev["mdm_lock"] else "no")]
            ui.label("Device record")
            ui.html('<div class="kv">' + "".join(f"<div><span>{ui.e(k)}</span>{ui.e(v)}</div>" for k, v in fields) + "</div>")


def show_case(c, did):
    d = store.dispute(c, did)
    case = store.get_case(c, did)
    st_txt = ui.STATUS.get(d["status"], d["status"])
    ui.html(f'<div class="casehead">{ui.tag(did, "plain")}{ui.tag(st_txt, "" if d["status"] in ("CLOSED",) else "ext")}</div>')
    render_email(d)
    if not case:
        ui.html('<div class="empty">The copilot has not looked at this dispute yet. It will read the email, find the '
                'device, run the checks and draft a reply for you to approve.</div>')
        st.write("")
        if st.button("Run the copilot on this dispute", type="primary", key=f"run_{did}", use_container_width=True):
            with st.spinner("Reading the email, checking the device record, drafting the reply…"):
                run_case(c, did)
            st.session_state[f"shown_{did}"] = time.time()
            st.rerun()
        return
    r = case["result"]
    st.session_state.setdefault(f"shown_{did}", time.time())
    render_result(r)
    if case["decision"]:
        kind = {"APPROVED": "Approved and sent", "TO_HUMAN": "Handed to the team", "REJECTED": "Rejected"}[case["decision"]]
        ui.html(f'<div class="status ok" style="margin:6px 0 10px"><b>{kind}</b> · ticket {ui.e(case["jira_key"] or "–")} · '
                f'your review took {case["handling_seconds"] or 0} s</div>')
        p1, p2 = st.columns(2, gap="medium")
        with p1:
            ui.label("Reply to the partner (preview)")
            ui.html(f'<div class="pre">{ui.e(case["final_reply"])}</div>')
        with p2:
            if case["jira_key"]:
                t = integrations.OUTBOX / "jira" / f"{case['jira_key']}.txt"
                ui.label("Jira ticket (preview)")
                ui.html(f'<div class="pre">{ui.e(t.read_text(encoding="utf-8") if t.exists() else "(not available)")}</div>')
    else:
        ui.label("Draft reply · edit before approving")
        draft = st.text_area("Draft reply", r["draft"], height=230, key=f"draft_{did}", label_visibility="collapsed")
        b = st.columns(3)
        choice = None
        if b[0].button("Approve and send", type="primary", key=f"ok_{did}", use_container_width=True):
            choice = "APPROVED"
        if b[1].button("Hand to the team", key=f"team_{did}", use_container_width=True):
            choice = "TO_HUMAN"
        if b[2].button("Reject", key=f"no_{did}", use_container_width=True):
            choice = "REJECTED"
        if choice:
            secs = round(time.time() - st.session_state.get(f"shown_{did}", time.time()))
            store.decide(c, did, choice, draft, secs)
            st.rerun()
    with st.expander(f"How the copilot got there · {r['elapsed_ms']} ms · {r['usage']['calls']} AI calls · "
                     f"${r['usage']['cost_usd']:.4f}"):
        st.dataframe([{"Step": s["step"], "What happened": s["detail"]} for s in r["steps"]],
                     hide_index=True, use_container_width=True)


def page_disputes():
    ui.hero("Demo 1 · Partner disputes", "Dispute Copilot",
            "Pick a dispute on the left. The copilot checks it against the device record and drafts a reply; you approve.")
    c = con()
    tab_inbox, tab_dash, tab_eval, tab_audit = st.tabs(["Disputes", "Summary", "Accuracy test", "Activity log"])
    with tab_inbox:
        rows = store.disputes(c)
        new = [r["id"] for r in rows if not r["action"]]
        left, right = st.columns([4, 7], gap="large")
        with left:
            ui.label(f"Inbox · {len(rows)} disputes · {len(new)} new")
            table = [{"Dispute": r["id"], "Partner": r["partner"],
                      "Topic": ui.TOPIC.get(r["category"], "–") if r["category"] else "–",
                      "Status": ui.STATUS.get(r["status"], r["status"])} for r in rows]
            event = st.dataframe(table, hide_index=True, use_container_width=True, height=560,
                                 on_select="rerun", selection_mode="single-row", key="inbox_table")
            sel = getattr(getattr(event, "selection", None), "rows", None) or []
            if sel:
                st.session_state.open_case = rows[sel[0]]["id"]
            b1, b2 = st.columns(2)
            if b1.button(f"Process all {len(new)} new", disabled=not new, use_container_width=True):
                prog = st.progress(0.0, "Running…")
                for i, x in enumerate(new, 1):
                    run_case(c, x)
                    prog.progress(i / len(new), f"{x} done")
                st.rerun()
            if b2.button("Start over", use_container_width=True):
                reset_disputes()
                st.session_state.pop("open_case", None)
                st.rerun()
        with right:
            did = st.session_state.get("open_case") or rows[0]["id"]
            show_case(c, did)
    with tab_dash:
        page_summary(c)
    with tab_eval:
        ui.html('<div class="card"><h3>Test before trusting it</h3><p>Runs the copilot on all 39 labelled disputes '
                '(without saving) and scores the type, decision, credit, team, escalation and reply language against '
                'the correct answers. Recorded on 14 Oct 2026: with Claude 100% fully correct for $0.42; rules only 97.4%.</p></div>')
        e1, e2 = st.columns(2)
        if e1.button("Run with rules only (free)", use_container_width=True):
            with st.spinner("Scoring 39 cases…"), config.rules_only():
                st.session_state.eval_rules = store.evaluate(c)
        llm_ok = claude_allowed() and budget_left() > 0.6 and not st.session_state.get("eval_llm")
        if e2.button("Run with Claude (≈$0.42, once per visit)", type="primary", disabled=not llm_ok,
                     use_container_width=True):
            with st.spinner("Scoring 39 cases with Claude – about two minutes…"):
                res = store.evaluate(c)
            record_spend(res["cost_usd"])
            st.session_state.eval_llm = res
        names = {"category": "type", "action": "decision", "credit": "credit", "team": "team",
                 "escalate": "escalation", "language": "reply language"}
        for key, title in (("eval_llm", "With Claude"), ("eval_rules", "Rules only")):
            ev = st.session_state.get(key)
            if ev:
                ui.label(title)
                ui.stats([(f"{ev['fully_correct']}%", "of cases fully correct"), (f"${ev['cost_usd']}", "AI cost for 39 cases")]
                         + [(f"{v}%", f"{names.get(k, k)} correct") for k, v in ev["accuracy"].items()])
                misses = [{"Case": r["id"], **{names.get(f, f): f"expected {r['expected'][f]}, got {r['got'][f]}"
                                               for f, ok in r["ok"].items() if not ok}}
                          for r in ev["rows"] if not r["all_ok"]]
                if misses:
                    st.dataframe(misses, hide_index=True, use_container_width=True)
    with tab_audit:
        cur = c.execute("SELECT ts, dispute_id, event, detail FROM audit ORDER BY id DESC LIMIT 200")
        data = [dict(zip(("Time", "Dispute", "Event", "Detail"), row)) for row in cur.fetchall()]
        if data:
            st.dataframe(data, hide_index=True, use_container_width=True, height=480)
        else:
            ui.html('<div class="empty">Every copilot run and every decision you make is logged here.</div>')


def page_summary(c):
    m = store.metrics(c)
    total = len(store.disputes(c))
    if not m["processed"]:
        ui.html('<div class="empty">The summary fills in as disputes are processed. '
                'Go to Disputes and click “Process all new” to see it with all 39.</div>')
        return
    decided = m["approved"] + m["to_human"] + m["rejected"]
    no_edit = m["approved"] - m["edited"]
    secs = m["review_seconds"]
    avg = f"{sum(secs) / len(secs):.0f} s" if secs else "–"
    ui.kpis([
        (f"{m['processed']} of {total}", "Disputes handled by the copilot",
         "Read, checked against the device record and given a draft reply."),
        (f"{no_edit} of {m['approved']}" if m["approved"] else "–", "Approved without changes",
         "How often the draft was good enough to send as it was."),
        (avg, "Average review time", "From opening a case to your decision."),
        (f"€{m['credits_eur']:,.0f}", "Credits owed to partners", "Where the record shows the partner was underpaid."),
        (str(m["escalated"]), "Sent for a senior look", "High value, repeat partner or an angry tone."),
        (f"${m['cost_usd']:.2f}", "AI cost so far", f"About {m['cost_usd'] / m['processed'] * 100:.1f}¢ per dispute."),
    ])
    g1, g2 = st.columns(2, gap="large")
    with g1:
        ui.label("What partners dispute")
        ui.html('<div class="explain">Number of disputes by topic.</div>')
        ui.bars([(ui.TOPIC.get(k, k), v) for k, v in m["by_category"].items()])
        ui.label("Which devices lead to credits")
        ui.html('<div class="explain">Credits by device model: where grading or pricing goes wrong most.</div>')
        ui.bars(list(m["by_model"].items()))
    with g2:
        ui.label("What the copilot recommended")
        ui.html('<div class="explain">Most disputes need no credit; the copilot shows the evidence either way.</div>')
        ui.bars([(ui.ACTION.get(k, k), v) for k, v in m["by_action"].items()])
        ui.label("Grading accuracy by grader")
        ui.html('<div class="explain">Share of each grader\'s devices that a re-check would grade better. '
                'For coaching and re-training, not for ranking people.</div>')
        ui.bars(list(m["grader_error_rate"].items()), fmt=lambda v: f"{v}%")
    if decided:
        st.caption(f"You decided {decided} disputes: {m['approved']} approved, {m['to_human']} handed to a team, "
                   f"{m['rejected']} rejected.")


# ------------------------------------------------------------------ stock lookup
EXAMPLE_LABELS = ["Grade A/B iPhone 13 in the main warehouse", "iPhone supply in the next 2 weeks",
                  "What's wrong with the raw export?", "Stock value by site", "Unlocked Galaxy S22 under €200"]


def lots_table(out):
    ui.stats([(out["total_units"], f"units · {out['site_filter']}"), (out["matching_lots"], "matching lots")]
             + [(v, f"grade {g}") for g, v in out["by_grade"].items() if v])
    st.dataframe([{"Lot": l["lot_id"], "Units here": l["units_here"], "Lot total": l["lot_total_units"],
                   "Locations": ", ".join(l["locations_here"]), "Summary": l["summary"]} for l in out["lots"]],
                 hide_index=True, use_container_width=True)


def page_stock():
    ui.hero("Demo 2 · Stock questions", "Stock Lookup",
            "Ask about refurbished phone stock in plain language. Claude answers by calling read-only tools "
            "over cleaned data, and shows you every lookup.")
    q = stock_server.QUALITY
    ui.stats([(q["raw_rows"], "raw export rows"), (q["lots_after_merge"], "clean, sellable lots"),
              (q["rows_held_back"], "rows held back"), (len(stock_server.INBOUND), "inbound shipments")])
    tab_chat, tab_tools, tab_quality = st.tabs(["Ask Claude", "Check with the tools", "Data quality"])
    with tab_chat:
        st.session_state.setdefault("chat", [])
        st.session_state.setdefault("history", [])
        allowed = claude_allowed()
        if not allowed:
            ui.html('<div class="empty">The AI assistant is off right now. The next tab gives the same answers without it.</div>')
        cols = st.columns(len(EXAMPLE_LABELS))
        picked = None
        for i, (lab, full) in enumerate(zip(EXAMPLE_LABELS, EXAMPLES)):
            if cols[i].button(lab, key=f"ex{i}", use_container_width=True, disabled=not allowed, help=full):
                picked = full
        if not st.session_state.chat:
            ui.html('<div class="empty" style="margin-top:12px">Pick an example above or type a question below. '
                    'Each answer lists the tool calls Claude made, so you can see where the numbers come from.</div>')
        for turn in st.session_state.chat:
            with st.chat_message(turn["role"]):
                st.markdown(turn["text"])
                for call in turn.get("calls", []):
                    args = ", ".join(f"{k}={v!r}" for k, v in (call["input"] or {}).items())
                    with st.expander(f"Looked up: {call['tool']}({args})"):
                        st.json(call["output"], expanded=False)
                if turn.get("cost") is not None:
                    st.caption(f"{len(turn.get('calls', []))} tool calls · ${turn['cost']:.4f}")
        typed = st.chat_input("Ask about stock, incoming supply or data quality", disabled=not allowed)
        question = typed or picked
        if question and allowed:
            st.session_state.chat.append({"role": "user", "text": question})
            if len(st.session_state.history) > 24:
                st.session_state.history = []
            try:
                with st.spinner("Claude is choosing a tool and looking it up…"):
                    answer, calls, usage = stock_chat.ask(st.session_state.history, question)
                record_spend(usage.cost_usd)
                st.session_state.chat.append({"role": "assistant", "text": answer or "(no answer)",
                                              "calls": calls, "cost": usage.cost_usd})
            except Exception as ex:
                st.session_state.history = []
                st.session_state.chat.append({"role": "assistant", "text": f"Claude could not answer this time ({ex}). Try again, or use the tools tab."})
            st.rerun()
        if st.session_state.chat and st.button("Clear chat"):
            st.session_state.chat, st.session_state.history = [], []
            st.rerun()
    with tab_tools:
        ui.html('<div class="card"><h3>Search the clean stock</h3><p>This is the same search_stock tool Claude calls. '
                'Use it to check any answer.</p></div>')
        a = st.columns([2, 1, 1.4, 1])
        query = a[0].text_input("Model", "iPhone 13 128GB", key="t_q")
        grade = a[1].selectbox("Worst grade", ["A", "B", "C", "D"], index=1, key="t_g")
        site = a[2].selectbox("Site", ["", "main", "refurbishment"], key="t_s",
                              format_func=lambda s: {"": "All sites", "main": "Main warehouse",
                                                     "refurbishment": "Refurbishment hub"}[s])
        with a[3]:
            st.write("")
            unlocked = st.checkbox("Unlocked only", True, key="t_u")
        lots_table(stock_chat.run_tool("search_stock", {"query": query, "min_grade": grade, "site": site,
                                                        "unlocked_only": unlocked, "limit": 25}))
        ui.label("Incoming supply")
        b = st.columns([2, 2])
        iq = b[0].text_input("Model", "iPhone", key="t_iq")
        days = b[1].slider("Days ahead", 1, 30, 14, key="t_days")
        sup = stock_chat.run_tool("incoming_supply", {"query": iq, "days_ahead": days})
        ui.stats([(sup["shipments"], "shipments"), (sup["units_expected"], "units expected")]
                 + [(v, f"expected grade {g}") for g, v in sup["expected_by_grade"].items()])
        if sup["detail"]:
            st.dataframe([{"Shipment": s["shipment_id"], "Partner": s["partner"], "Model": f"{s['brand']} {s['model']} {s['storage_gb']}GB",
                           "Units": s["units"], "ETA": s["eta"], "Status": s["status"]} for s in sup["detail"]],
                         hide_index=True, use_container_width=True)
    with tab_quality:
        rep = stock_chat.run_tool("data_quality_report", {})
        ui.html('<div class="card"><h3>What the cleaning step fixed</h3><ul>'
                + "".join(f"<li>{ui.e(x)}</li>" for x in rep["what_this_means"]) + "</ul></div>")
        f1, f2 = st.columns(2, gap="large")
        with f1:
            ui.label("Fixes applied")
            st.dataframe([{"Fix": k, "Rows": v} for k, v in rep["fixes"].items()], hide_index=True, use_container_width=True)
            ui.label("Examples")
            st.dataframe([{"Field": k, "Raw → clean": x} for k, xs in rep["examples"].items() for x in xs],
                         hide_index=True, use_container_width=True, height=300)
        with f2:
            ui.label("Rows held back, with the reason")
            st.dataframe([h for h in stock_server.QUALITY["held_back"]], hide_index=True, use_container_width=True, height=470)


# ------------------------------------------------------------------ main
page = sidebar()
{"Home": page_overview, "Dispute Copilot": page_disputes, "Stock Lookup": page_stock}[page]()
