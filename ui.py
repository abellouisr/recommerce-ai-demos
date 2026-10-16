"""Look and feel: one stylesheet plus small HTML building blocks for Streamlit pages."""
from html import escape

import streamlit as st

# Palette (same family as the architecture PDFs): teal = positive / automated, blue = needs a look,
# slate = did not pass, plum = data. No red or orange anywhere: nothing in a demo is an error.
# Layout: sidebar navigation, summary before detail, list on the left and the open item on the right.
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
:root{
  --bg:#f5f7f6; --surface:#ffffff; --ink:#17212b; --muted:#5a6772; --line:#dde3e1;
  --accent:#0d7a64; --accent-soft:#e3f2ee; --ext:#2e5c9a; --ext-soft:#e8eef8;
  --warn:#2e5c9a; --warn-soft:#e8eef8; --bad:#3d4f5c; --bad-soft:#e7ecef; --data:#6a4c93; --data-soft:#efe9f7;
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
}
html, body, .stApp, [data-testid="stAppViewContainer"]{background:var(--bg)!important;color:var(--ink);font-family:var(--sans)}
.stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button{font-family:var(--sans)}
[data-testid="stIconMaterial"], .material-symbols-rounded, .material-icons{font-family:"Material Symbols Rounded"!important}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"]{display:none!important}
header[data-testid="stHeader"]{background:transparent}
.block-container{padding-top:2.2rem!important;padding-bottom:4rem!important;max-width:1280px}
h1,h2,h3{font-family:var(--sans)!important;color:var(--ink);letter-spacing:-.01em}
[data-testid="stSidebar"]{background:var(--surface);border-right:1px solid var(--line)}
[data-testid="stSidebar"] .block-container{padding-top:1.2rem}
.stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button{
  border-radius:8px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font-weight:500;min-height:40px}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:var(--accent);color:var(--accent)}
.stButton>button[kind="primary"],[data-testid="stFormSubmitButton"]>button[kind="primaryFormSubmit"],
[data-testid="stFormSubmitButton"]>button[kind="primary"]{background:var(--accent);border-color:var(--accent);color:#fff}
.stButton>button[kind="primary"]:hover{background:#0a6553;color:#fff}
[data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid var(--line)}
[data-baseweb="tab"]{font-weight:500}
[data-baseweb="tab-highlight"]{background-color:var(--accent)!important}
[data-testid="stExpander"] details{border:1px solid var(--line);border-radius:10px;background:var(--surface)}
[data-testid="stTextArea"] textarea{font-family:var(--sans);font-size:14.5px;line-height:1.55}
[data-testid="stChatMessage"]{background:var(--surface);border:1px solid var(--line);border-radius:12px}

.eyebrow{font:500 12px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin-bottom:8px}
.hero h1{font-size:34px;line-height:1.15;margin:0 0 8px;font-weight:700}
.hero p{color:var(--muted);font-size:16.5px;max-width:72ch;margin:0}
.hero{margin-bottom:22px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:6px 0 22px}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.stat .v{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.2}
.stat .l{color:var(--muted);font-size:13px;margin-top:2px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px 22px;margin-bottom:14px}
.card h3{font-size:19px;margin:0 0 6px}
.card p{color:var(--muted);margin:0 0 10px;font-size:15px}
.card ul{margin:6px 0 0;padding-left:18px;color:var(--ink);font-size:14.5px}
.card li{margin:3px 0}
.tag{display:inline-block;font:500 12px/1 var(--mono);padding:5px 8px;border-radius:6px;margin:0 6px 6px 0;
  background:var(--accent-soft);color:var(--accent);white-space:nowrap}
.tag.ext{background:var(--ext-soft);color:var(--ext)} .tag.warn{background:var(--warn-soft);color:var(--warn)}
.tag.bad{background:var(--bad-soft);color:var(--bad)} .tag.data{background:var(--data-soft);color:var(--data)}
.tag.plain{background:var(--bg);color:var(--muted);border:1px solid var(--line)}
.mail{background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;margin-bottom:14px}
.mail .head{padding:14px 18px;border-bottom:1px solid var(--line)}
.mail .subj{font-weight:600;font-size:16px}
.mail .meta{color:var(--muted);font-size:13px;margin-top:3px}
.mail .body{padding:14px 18px;white-space:pre-wrap;font-size:14.5px;line-height:1.6;max-height:340px;overflow:auto}
.decision{border-radius:14px;padding:16px 18px;margin-bottom:12px;border:1px solid var(--line);background:var(--surface)}
.decision .big{font-size:22px;font-weight:700;margin:2px 0 8px}
.decision.esc{border-color:#b9cbe6;background:var(--warn-soft)}
.checks{display:grid;gap:6px;margin:4px 0 14px}
.check{display:grid;grid-template-columns:52px 1fr;gap:10px;align-items:start;background:var(--surface);
  border:1px solid var(--line);border-radius:10px;padding:9px 12px;font-size:14px}
.check .d{color:var(--muted);font-size:13px;word-break:break-word}
.badge{font:600 11px/1 var(--mono);padding:5px 0;border-radius:5px;text-align:center}
.badge.ok{background:var(--accent-soft);color:var(--accent)} .badge.no{background:var(--bad-soft);color:var(--bad)}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px 16px;font-size:14px}
.kv div span{display:block;color:var(--muted);font-size:12px}
.section-label{font:500 12px/1 var(--mono);letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin:16px 0 8px}
.pre{background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:12px 14px;font:13px/1.55 var(--mono);white-space:pre-wrap;word-break:break-word}
.side-brand{font-weight:700;font-size:17px;line-height:1.25}
.side-sub{color:var(--muted);font-size:12.5px;margin-top:2px}
.status{border-radius:10px;padding:10px 12px;font-size:13px;line-height:1.4}
.status.ok{background:var(--accent-soft);color:var(--accent)} .status.off{background:var(--bad-soft);color:var(--bad)}
.side-status{font-size:13px;color:var(--muted);display:flex;align-items:center;gap:8px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--accent);display:inline-block}
.dot.off{background:#9aa7b1}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within,[data-baseweb="select"]>div:focus-within{border-color:var(--accent)!important}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:6px 4px}
.bars{display:grid;gap:8px}
.barrow{display:grid;grid-template-columns:minmax(120px,38%) 1fr 56px;gap:10px;align-items:center;font-size:14px}
.bartrack{background:var(--bg);border-radius:5px;height:12px;overflow:hidden;border:1px solid var(--line)}
.barfill{background:var(--accent);height:100%;border-radius:5px}
.barrow .n{text-align:right;font-variant-numeric:tabular-nums;color:var(--ink);font-weight:600}
.explain{color:var(--muted);font-size:13.5px;margin:-4px 0 12px}
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.kpi .v{font-size:28px;font-weight:700;font-variant-numeric:tabular-nums}
.kpi .t{font-weight:600;font-size:14.5px;margin-top:2px}
.kpi .x{color:var(--muted);font-size:13px;margin-top:4px;line-height:1.45}
.kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:22px}
@media (max-width:900px){.kpis{grid-template-columns:1fr}}
.casehead{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:10px}
.empty{border:1px dashed var(--line);border-radius:14px;padding:26px;text-align:center;color:var(--muted);background:var(--surface)}
.login{max-width:440px;margin:8vh auto 0}
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def html(s):
    st.markdown(s, unsafe_allow_html=True)


def e(x):
    return escape(str(x if x is not None else ""))


def hero(eyebrow, title, lede):
    html(f'<div class="hero"><div class="eyebrow">{e(eyebrow)}</div><h1>{e(title)}</h1><p>{e(lede)}</p></div>')


def stats(items):
    html('<div class="stats">' + "".join(f'<div class="stat"><div class="v">{e(v)}</div><div class="l">{e(l)}</div></div>'
                                         for v, l in items) + "</div>")


def tag(text, kind=""):
    return f'<span class="tag {kind}">{e(text)}</span>'


def label(text):
    html(f'<div class="section-label">{e(text)}</div>')


ACTION_KIND = {"UPHOLD": "plain", "CORRECT_AND_CREDIT": "", "REQUEST_INFO": "ext", "INVESTIGATE": "warn", "MANUAL_REVIEW": "warn"}


def nice(code):
    return str(code or "").replace("_", " ").capitalize()


def bars(items, fmt=lambda v: f"{v}"):
    """Simple horizontal bars: list of (label, value). Same colour for all; the length carries the meaning."""
    items = [(k, v) for k, v in items if v]
    if not items:
        html('<div class="empty">Nothing yet.</div>')
        return
    top = max(v for _, v in items) or 1
    html('<div class="bars">' + "".join(
        f'<div class="barrow"><div>{e(k)}</div><div class="bartrack"><div class="barfill" style="width:{v / top * 100:.0f}%"></div></div>'
        f'<div class="n">{e(fmt(v))}</div></div>' for k, v in sorted(items, key=lambda kv: -kv[1])) + "</div>")


def kpis(items):
    """items: (value, title, explanation)."""
    html('<div class="kpis">' + "".join(f'<div class="kpi"><div class="v">{e(v)}</div><div class="t">{e(t)}</div>'
                                        f'<div class="x">{e(x)}</div></div>' for v, t, x in items) + "</div>")


TOPIC = {"GRADE_DISPUTE": "Grade", "PRICE_CHANGE": "Payout", "LOCK": "Device lock", "IMEI_MISMATCH": "IMEI mismatch",
         "MISSING_DEVICE": "Missing device", "OTHER": "Other"}
ACTION = {"UPHOLD": "Keep the original result", "CORRECT_AND_CREDIT": "Correct and credit the partner",
          "REQUEST_INFO": "Ask the partner for information", "INVESTIGATE": "Investigate internally",
          "MANUAL_REVIEW": "Send to a person to review"}
STATUS = {"NEW": "New", "DRAFTED": "Ready for review", "CLOSED": "Approved", "WITH_TEAM": "With team", "REJECTED": "Rejected"}
