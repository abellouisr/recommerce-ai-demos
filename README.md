# Recommerce AI demos

A password-protected web version of two prototypes for a phone recommerce business, built with Streamlit:

1. **Dispute Copilot**: a partner disputes a grade, payout, lock or missing device by email. The copilot reads the email with Claude, checks it against the device record, recommends a decision with the exact credit, drafts the reply and routes it. A person approves every reply.
2. **Stock Lookup**: a messy stock export is cleaned into sellable lots, and Claude answers stock questions by calling five read-only tools. Every number comes from the tools, with lot ids you can check.

All data is synthetic (invented partners, devices, prices and stock). This is my own prototype, not a tool of any company.
Architecture: [docs/Dispute_Copilot_Architecture.pdf](docs/Dispute_Copilot_Architecture.pdf) · [docs/Stock_Lookup_Architecture.pdf](docs/Stock_Lookup_Architecture.pdf)

## What is different in the public version

- **Password gate** (`DEMO_PASSWORD`), five attempts per visit.
- **Each visitor gets their own copy** of the dispute data, so testers never see each other's approvals. "Reset data" starts over.
- **No real outbound actions.** Replies, Jira tickets and Slack alerts are shown as previews. No Jira or Slack credentials are on the server.
- **Spend caps.** Claude use stops for the day at `DAILY_BUDGET_USD` across all visitors, and at `SESSION_CLAUDE_LIMIT` actions per visitor; the app then runs in offline rules mode. Also set a monthly spend limit on the API key in the Anthropic Console.
- **Stock Lookup without setup.** Visitors chat in the browser; the app runs the same tool-use loop Claude Desktop runs over MCP. The "Use the tools directly" tab lets them check any answer without Claude.

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repository.
2. On share.streamlit.io, sign in with GitHub → **Create app** → pick the repo, branch `main`, file `streamlit_app.py`. Under **Advanced settings** choose Python 3.12 and paste the secrets from `.streamlit/secrets.toml.example` with real values.
3. Deploy. Share the app link and the password.

## Run locally

```
pip install streamlit
streamlit run streamlit_app.py
```
Put the same settings in `.streamlit/secrets.toml` (git-ignored), or as environment variables.

## Files

```
streamlit_app.py     password gate, pages, spend caps
stock_chat.py        Claude tool-use loop over the stock tools
stock_server.py      the same tools as an MCP server (stdio) for Claude Desktop
stock/               synthetic messy export and the cleaning step
copilot/             dispute pipeline: rules, synthetic data, agent, Claude client, store, evaluation
docs/                architecture PDFs
```
