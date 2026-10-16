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

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Recommerce AI demos", layout="wide")


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


def bar(data):
    import pandas as pd
    if not data:
        st.caption("Nothing yet.")
        return
    st.bar_chart(pd.DataFrame({"count": pd.Series(dict(data))}), horizontal=True)


# ------------------------------------------------------------------ password gate
def gate():
    pw = secret("DEMO_PASSWORD")
    if not pw:
        st.error("This demo has no password set yet. Add DEMO_PASSWORD to the app's secrets.")
        st.stop()
    if st.session_state.get("authed"):
        return
    st.title("Recommerce AI demos")
    st.caption("Two working prototypes on synthetic data. Enter the password you were given.")
    tries = st.session_state.get("tries", 0)
    if tries >= 5:
        st.error("Too many attempts. Reload the page to try again.")
        st.stop()
    with st.form("login"):
        entered = st.text_input("Password", type="password", key="pw")
        if st.form_submit_button("Open the demos", type="primary"):
            if hmac.compare_digest(entered.encode(), pw.encode()):
                st.session_state.authed = True
                st.rerun()
            st.session_state.tries = tries + 1
            st.error("That password is not right.")
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
    for k in ("db", "db_path", "eval_rules", "eval_llm", "last_ticket"):
        st.session_state.pop(k, None)


def mode_badge():
    status = claude_status()
    if claude_allowed():
        st.sidebar.success(f"Claude connected · {config.CLAUDE_MODEL}")
    elif status.get("ok"):
        st.sidebar.warning("Claude paused (today's demo budget or your session limit is used up). "
                           "Running in offline rules mode.")
    else:
        st.sidebar.info("Offline rules mode (no Claude). " + (status.get("message") or ""))


# ------------------------------------------------------------------ pages
def page_overview():
    st.title("Recommerce AI demos")
    st.markdown(
        "Two prototypes for a phone recommerce business, built by **Abel Louis**. "
        "Everything runs on **synthetic data**: invented partners, devices, prices and stock. "
        "Nothing here connects to a real company system.")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1 · Dispute Copilot")
        st.markdown(
            "Partners email disputes about grades, payouts, locked or missing devices. The copilot reads the email "
            "with Claude, checks it against the device record, recommends a decision with the exact credit, "
            "drafts the reply and routes it to the owning team. **A person approves every reply.**\n\n"
            "**Try:** open the Inbox, run the copilot on a case, edit the draft and approve it. "
            "Then look at the Dashboard and run the Evaluation.")
    with c2:
        st.subheader("2 · Stock Lookup")
        st.markdown(
            "A messy stock export is cleaned into sellable lots, and Claude answers stock questions by calling "
            "five read-only tools. Every number comes from the tools, with lot ids you can check.\n\n"
            "**Try:** ask *\"How many grade A or B iPhone 13 128GB, unlocked, do we have in the main warehouse?\"* "
            "and open the tool calls under the answer.")
    st.divider()
    st.subheader("Architecture")
    d1, d2 = st.columns(2)
    for col, name in ((d1, "Dispute_Copilot_Architecture.pdf"), (d2, "Stock_Lookup_Architecture.pdf")):
        p = ROOT / "docs" / name
        if p.exists():
            col.download_button(f"Download {name.replace('_', ' ').replace('.pdf', '')} (PDF)", p.read_bytes(),
                                file_name=name, mime="application/pdf", use_container_width=True)
    st.caption("In this public version replies, Jira tickets and Slack alerts are shown as previews; nothing is sent. "
               f"Claude use is capped at ${DAILY_BUDGET_USD:.0f} a day across all visitors.")


def show_case(c, did):
    d = store.dispute(c, did)
    case = store.get_case(c, did)
    left, right = st.columns([5, 7], gap="large")
    with left:
        st.markdown(f"**{d['subject']}**")
        st.caption(f"From {d['sender']} · received {d['received_at']}")
        st.text(d["body"])
    with right:
        if not case:
            st.info("The copilot has not looked at this dispute yet.")
            if st.button("Run copilot on this case", type="primary", key=f"run_{did}"):
                with st.spinner("Reading the email, checking the device record, drafting the reply…"):
                    run_case(c, did)
                st.session_state[f"shown_{did}"] = time.time()
                st.rerun()
            return
        r = case["result"]
        st.session_state.setdefault(f"shown_{did}", time.time())
        m = st.columns(4)
        m[0].metric("Recommendation", r["action"].replace("_", " ").title())
        m[1].metric("Credit", f"€{r['credit_eur']:.2f}" if r["credit_eur"] else "–")
        m[2].metric("Confidence", f"{r['confidence']:.0%}" if isinstance(r["confidence"], float) else str(r["confidence"]))
        m[3].metric("Mode", {"llm": "Claude", "rules": "Rules"}.get(r["mode"], r["mode"]))
        st.markdown(f"**Type:** {r['category'].replace('_', ' ').title()} · **Route to:** {r['team']}")
        if r["escalate"]:
            st.warning("Escalated: " + "; ".join(r["escalation_reasons"]))
        st.markdown("**Checks against the device record**")
        st.dataframe([{"": "PASS" if ck["ok"] else "FAIL", "Check": ck["check"], "Detail": str(ck["detail"])}
                      for ck in r["checks"]], hide_index=True, use_container_width=True)
        if r["facts"].get("device"):
            with st.expander("Device record"):
                st.json(r["facts"]["device"])
        if case["decision"]:
            st.success(f"Decided: {case['decision'].replace('_', ' ').lower()} · ticket {case['jira_key'] or '–'}")
            st.markdown("**Reply sent (preview)**")
            st.text(case["final_reply"])
            if case["jira_key"]:
                t = integrations.OUTBOX / "jira" / f"{case['jira_key']}.txt"
                with st.expander("Jira ticket preview", expanded=True):
                    st.text(t.read_text(encoding="utf-8") if t.exists() else "(preview not available)")
        else:
            draft = st.text_area("Draft reply – edit before approving", r["draft"], height=260, key=f"draft_{did}")
            b = st.columns(3)
            choice = None
            if b[0].button("Approve and send", type="primary", key=f"ok_{did}"):
                choice = "APPROVED"
            if b[1].button("Hand to team", key=f"team_{did}"):
                choice = "TO_HUMAN"
            if b[2].button("Reject", key=f"no_{did}"):
                choice = "REJECTED"
            if choice:
                secs = round(time.time() - st.session_state.get(f"shown_{did}", time.time()))
                store.decide(c, did, choice, draft, secs)
                st.rerun()
        with st.expander(f"Trace · {r['elapsed_ms']} ms · {r['usage']['calls']} Claude calls · ${r['usage']['cost_usd']:.4f}"):
            st.dataframe(r["steps"], hide_index=True, use_container_width=True)
            if r.get("llm_errors"):
                st.error("; ".join(r["llm_errors"]))


def page_disputes():
    st.title("Dispute Copilot")
    c = con()
    tab_inbox, tab_dash, tab_eval, tab_audit = st.tabs(["Inbox", "Dashboard", "Evaluation", "Audit log"])
    with tab_inbox:
        rows = store.disputes(c)
        top = st.columns([3, 1, 1])
        new = [r["id"] for r in rows if not r["action"]]
        top[0].caption(f"{len(rows)} disputes · {len(new)} not yet processed · your own copy of the data")
        if top[1].button(f"Run copilot on all {len(new)}", disabled=not new):
            prog = st.progress(0.0, "Running…")
            for i, did in enumerate(new, 1):
                run_case(c, did)
                prog.progress(i / len(new), f"{did} done")
            st.rerun()
        if top[2].button("Reset data"):
            reset_disputes()
            st.rerun()
        st.dataframe([{"ID": r["id"], "Partner": r["partner"], "Subject": r["subject"], "Status": r["status"],
                       "Recommendation": (r["action"] or "").replace("_", " ").lower(),
                       "Escalated": "yes" if r["escalate"] else ""} for r in rows],
                     hide_index=True, use_container_width=True, height=280)
        labels = {r["id"]: f"{r['id']} · {r['partner']} · {r['subject'][:70]}" for r in rows}
        did = st.selectbox("Open a dispute", list(labels), format_func=labels.get, key="open_case")
        st.divider()
        show_case(c, did)
    with tab_dash:
        m = store.metrics(c)
        if not m["processed"]:
            st.info("Run the copilot on some disputes first.")
        else:
            k = st.columns(5)
            k[0].metric("Cases processed", m["processed"])
            k[1].metric("Approved", m["approved"])
            k[2].metric("Approved without edits", m["approved"] - m["edited"])
            k[3].metric("Credits recommended", f"€{m['credits_eur']:,.0f}")
            k[4].metric("Model cost", f"${m['cost_usd']:.2f}")
            g = st.columns(2)
            g[0].markdown("**Cases by type**")
            with g[0]:
                bar(m["by_category"])
            g[1].markdown("**Recommended action**")
            with g[1]:
                bar(m["by_action"])
            h = st.columns(2)
            h[0].markdown("**Credits by device model**")
            with h[0]:
                bar(m["by_model"])
            h[1].markdown("**Grader regrade rate (%)** – for coaching and re-checks, not ranking")
            with h[1]:
                bar(m["grader_error_rate"])
    with tab_eval:
        st.markdown("Runs the copilot on all 39 labelled disputes (without saving) and scores category, action, "
                    "credit, team, escalation and reply language.")
        e1, e2 = st.columns(2)
        if e1.button("Run in rules mode (free)"):
            with config.rules_only():
                st.session_state.eval_rules = store.evaluate(c)
        llm_ok = claude_allowed() and budget_left() > 0.6 and not st.session_state.get("eval_llm")
        if e2.button("Run with Claude (about $0.42, once per visit)", disabled=not llm_ok):
            with st.spinner("Scoring 39 cases with Claude – about two minutes…"):
                res = store.evaluate(c)
            record_spend(res["cost_usd"])
            st.session_state.eval_llm = res
        st.caption("Recorded result on 14 Oct 2026: Claude 100% fully correct for $0.42; rules 97.4%.")
        for key, title in (("eval_llm", "Claude"), ("eval_rules", "Rules")):
            ev = st.session_state.get(key)
            if ev:
                st.subheader(f"{title}: {ev['fully_correct']}% fully correct · ${ev['cost_usd']}")
                st.dataframe([ev["accuracy"]], hide_index=True)
                misses = [{"Case": r["id"], **{f: f"{r['expected'][f]} → {r['got'][f]}" for f, ok in r["ok"].items() if not ok}}
                          for r in ev["rows"] if not r["all_ok"]]
                if misses:
                    st.markdown("Misses (expected → got)")
                    st.dataframe(misses, hide_index=True)
    with tab_audit:
        cur = c.execute("SELECT ts, dispute_id, event, detail FROM audit ORDER BY id DESC LIMIT 200")
        st.dataframe([dict(zip(("Time", "Dispute", "Event", "Detail"), row)) for row in cur.fetchall()],
                     hide_index=True, use_container_width=True)


def page_stock():
    st.title("Stock Lookup")
    q = stock_server.QUALITY
    st.caption(f"{q['raw_rows']} raw rows cleaned into {q['lots_after_merge']} sellable lots · "
               f"{q['rows_held_back']} rows held back · {len(stock_server.INBOUND)} inbound shipments · synthetic data")
    tab_chat, tab_tools = st.tabs(["Ask Claude", "Use the tools directly"])
    with tab_chat:
        st.session_state.setdefault("chat", [])        # what is shown
        st.session_state.setdefault("history", [])     # what Claude sees
        if not claude_allowed():
            st.info("Claude is not available right now, so the chat is off. Use the tools directly in the next tab.")
        st.markdown("**Example questions**")
        cols = st.columns(2)
        picked = None
        for i, ex in enumerate(EXAMPLES):
            if cols[i % 2].button(ex, key=f"ex{i}", use_container_width=True, disabled=not claude_allowed()):
                picked = ex
        for turn in st.session_state.chat:
            with st.chat_message(turn["role"]):
                st.markdown(turn["text"])
                for call in turn.get("calls", []):
                    with st.expander(f"Tool call: {call['tool']}({json.dumps(call['input'], ensure_ascii=False)})"):
                        st.json(call["output"])
                if turn.get("cost") is not None:
                    st.caption(f"{len(turn.get('calls', []))} tool calls · ${turn['cost']:.4f}")
        typed = st.chat_input("Ask about stock, incoming supply or data quality", disabled=not claude_allowed())
        question = typed or picked
        if question and claude_allowed():
            st.session_state.chat.append({"role": "user", "text": question})
            if len(st.session_state.history) > 24:      # keep the conversation short and cheap
                st.session_state.history = []
            try:
                with st.spinner("Claude is choosing a tool and looking it up…"):
                    answer, calls, usage = stock_chat.ask(st.session_state.history, question)
                record_spend(usage.cost_usd)
                st.session_state.chat.append({"role": "assistant", "text": answer or "(no answer)",
                                              "calls": calls, "cost": usage.cost_usd})
            except Exception as e:
                st.session_state.history = []
                st.session_state.chat.append({"role": "assistant", "text": f"Claude could not answer: {e}"})
            st.rerun()
        if st.session_state.chat and st.button("Clear chat"):
            st.session_state.chat, st.session_state.history = [], []
            st.rerun()
    with tab_tools:
        st.markdown("The same five tools Claude uses, without Claude. Use them to check any answer.")
        tool = st.selectbox("Tool", list(stock_server.TOOLS), key="tool_pick")
        args = {}
        if tool == "search_stock":
            a = st.columns(4)
            args["query"] = a[0].text_input("Model", "iPhone 13 128GB")
            args["min_grade"] = a[1].selectbox("Worst grade", ["A", "B", "C", "D"], index=1)
            args["site"] = a[2].selectbox("Site", ["", "main", "refurbishment"],
                                          format_func=lambda s: {"": "All sites", "main": "Main warehouse",
                                                                 "refurbishment": "Refurbishment hub"}[s])
            args["unlocked_only"] = a[3].checkbox("Unlocked only", True)
        elif tool == "lot_details":
            args["lot_id"] = st.text_input("Lot id", "L-0078")
        elif tool == "incoming_supply":
            a = st.columns(2)
            args["query"] = a[0].text_input("Model", "iPhone")
            args["days_ahead"] = a[1].slider("Days ahead", 1, 30, 14)
        elif tool == "stock_overview":
            args["group_by"] = st.selectbox("Group by", ["model", "brand", "grade", "site"])
        if st.button("Run tool", type="primary"):
            st.json(stock_chat.run_tool(tool, args))


PAGES = {"Overview": page_overview, "Dispute Copilot": page_disputes, "Stock Lookup": page_stock}
choice = st.sidebar.radio("Demo", list(PAGES), key="page")
mode_badge()
st.sidebar.caption(f"Claude budget left today: ${budget_left():.2f}")
st.sidebar.caption("Synthetic data only. Prototype by Abel Louis.")
PAGES[choice]()
