"""
SigmaPay Fraud Detective
Streamlit app for Data + AI + FinTech training webinar
"""

import os
import streamlit as st
import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv
from database import setup_database, run_query, get_schema_info

# Load .env for local development (no-op on Streamlit Cloud)
load_dotenv()

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="SigmaPay Fraud Detective",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# INIT DB
# ─────────────────────────────────────────────
setup_database()

# ─────────────────────────────────────────────
# API KEY
# ─────────────────────────────────────────────
def get_api_key():
    # 1. Streamlit secrets (Cloud deploy) — safe .get() avoids crash if no secrets.toml
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    # 2. Environment variable / local .env
    return os.getenv("ANTHROPIC_API_KEY", "")

# ─────────────────────────────────────────────
# MODULE 1 — SQL QUIZ QUESTIONS
# ─────────────────────────────────────────────
SQL_QUESTIONS = [
    {
        "id": 1,
        "level": "🟢 Easy",
        "title": "Total Transactions",
        "prompt": "How many total transactions exist in the transactions table?",
        "hint_context": "Use COUNT(*) to count all rows in a table.",
        "expected_sql": "SELECT COUNT(*) as total FROM transactions",
        "check": lambda cols, rows: (
            len(rows) == 1 and
            abs(float(rows[0][0]) - _expected_count()) < 5
        ),
        "expected_display": "A single number — the total count of all transactions",
    },
    {
        "id": 2,
        "level": "🟢 Easy",
        "title": "Mumbai Merchants",
        "prompt": "List all merchant names and categories based in Mumbai.",
        "hint_context": "Use WHERE city = 'Mumbai' to filter merchants by city.",
        "expected_sql": "SELECT name, category FROM merchants WHERE city = 'Mumbai'",
        "check": lambda cols, rows: len(rows) >= 2 and len(cols) >= 2,
        "expected_display": "Merchant names + categories where city is Mumbai",
    },
    {
        "id": 3,
        "level": "🟡 Medium",
        "title": "Day 1 Revenue",
        "prompt": "Find the total transaction value (sum of amount) for Day 1 only (2024-01-01).",
        "hint_context": "Use SUM(amount) and filter with WHERE timestamp LIKE '2024-01-01%'",
        "expected_sql": "SELECT SUM(amount) as total FROM transactions WHERE timestamp LIKE '2024-01-01%'",
        "check": lambda cols, rows: len(rows) == 1 and float(rows[0][0] or 0) > 0,
        "expected_display": "A single ₹ total — sum of all amounts on January 1st",
    },
    {
        "id": 4,
        "level": "🟡 Medium",
        "title": "Top Spenders",
        "prompt": "Show top 5 users by total spend. Use GROUP BY user_id, ORDER BY total spend highest first, LIMIT 5.",
        "hint_context": "SELECT user_id, SUM(amount) FROM transactions GROUP BY user_id ORDER BY 2 DESC LIMIT 5",
        "expected_sql": "SELECT user_id, SUM(amount) FROM transactions GROUP BY user_id ORDER BY 2 DESC LIMIT 5",
        "check": lambda cols, rows: len(rows) == 5,
        "expected_display": "5 rows — user_id + total spend, highest first",
    },
    {
        "id": 5,
        "level": "🔴 Hard",
        "title": "Suspicious Midnight Activity",
        "prompt": "Find all transactions between midnight and 5 AM. Use strftime('%H', timestamp) to extract the hour.",
        "hint_context": "SELECT * FROM transactions WHERE strftime('%H',timestamp)<'05'",
        "expected_sql": "SELECT * FROM transactions WHERE strftime('%H',timestamp)<'05'",
        "check": lambda cols, rows: len(rows) > 0,
        "expected_display": "Rows of transactions that happened in the 12AM–5AM window",
    },
]

def _expected_count():
    _, rows, _ = run_query("SELECT COUNT(*) FROM transactions")
    return float(rows[0][0]) if rows else 0

# ─────────────────────────────────────────────
# MODULE 2 — FRAUD CASE CARDS (5 cases)
# ─────────────────────────────────────────────
FRAUD_CASES = [
    # EASY
    {
        "id": 1,
        "difficulty": "🟢 Easy",
        "title": "The Speed Merchant",
        "story": "Our risk engine flagged user U005. They made an unusually high number of transactions in a very short window. Can you find the evidence?",
        "question": "Show me all transactions by user U005, ordered by timestamp.",
        "fraud_type": "High-Frequency Transactions",
        "what_to_look_for": "Count the rows — how many txns did they make? How quickly?",
    },
    {
        "id": 2,
        "difficulty": "🟢 Easy",
        "title": "The Round Number Rule",
        "story": "Fraudsters often send round amounts to test stolen accounts. User U008 is suspected of this pattern.",
        "question": "Show all transactions by user U008. Look at the amounts — are they suspiciously round?",
        "fraud_type": "Round Number Pattern",
        "what_to_look_for": "Are all amounts multiples of 500 or 1000? That's a red flag.",
    },
    # MEDIUM
    {
        "id": 3,
        "difficulty": "🟡 Medium",
        "title": "The Threshold Dodger",
        "story": "In India, transactions above ₹10,000 trigger extra KYC checks. Someone seems to know this rule very well and is deliberately staying just under it.",
        "question": "Find all transactions where amount is between 9500 and 9999. Who keeps sending amounts just below ₹10,000?",
        "fraud_type": "Threshold Skirting (Structuring)",
        "what_to_look_for": "Look for one user with many txns clustering just under ₹10,000.",
    },
    {
        "id": 4,
        "difficulty": "🟡 Medium",
        "title": "The Sleeping Giant Wakes",
        "story": "A few accounts are flagged 'dormant' — meaning they've been inactive for a long time. Suddenly, they each fire off 8+ transactions in a single day. Genuine dormant accounts don't just wake up and go on a spending spree. Something's off — let's check how 'old' these accounts really are.",
        "question": "Find users where is_dormant = 1. For each, show account_age_days AND how many transactions they made in a single day. What do BOTH numbers tell you?",
        "fraud_type": "Mule Account (fake-dormant setup)",
        "what_to_look_for": "These 'dormant' accounts are only 3-8 days old — that's not dormant, that's brand new. Fraudsters open fresh accounts, label them dormant to look harmless, then activate them in a burst (8+ txns/day) to move stolen money. One red flag (sudden burst) plus one giveaway (impossibly young 'old' account) = the same scam.",
    },
    # HARD
    {
        "id": 5,
        "difficulty": "🔴 Hard",
        "title": "The Card Tester",
        "story": "When criminals steal a card, they first send tiny test amounts (₹1–₹10) to check if the card is active. If it works, they immediately make a huge purchase. Classic card testing fraud.",
        "question": "Show all transactions by user U018, ordered by timestamp and amount. Can you spot the tiny test payments followed by a massive transaction?",
        "fraud_type": "Card Testing Pattern",
        "what_to_look_for": "Look for several tiny amounts (under ₹15) and then one huge amount (₹48,000). That's the fraud pattern.",
    },
]

# ─────────────────────────────────────────────
# CLAUDE HAIKU HELPER
# ─────────────────────────────────────────────
def call_haiku(system_prompt: str, user_message: str) -> str:
    api_key = get_api_key()
    if not api_key:
        return "⚠️ API key not configured. Add ANTHROPIC_API_KEY to Streamlit secrets or .env file."
    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except Exception as e:
        return f"⚠️ Claude API error: {e}"


def get_sql_hint(question_prompt: str, hint_context: str, student_sql: str) -> str:
    system = (
        "You are a friendly SQL tutor for beginners. "
        "Give a short, encouraging hint (2-3 sentences max). "
        "Do NOT give the complete SQL answer. "
        "Point them in the right direction only. "
        "Use simple language suitable for freshers with zero SQL background."
    )
    user_msg = (
        f"Question: {question_prompt}\n"
        f"Hint context: {hint_context}\n"
        f"Student's attempt: {student_sql}\n\n"
        "Give a short hint to help them fix their query without revealing the answer."
    )
    return call_haiku(system, user_msg)


def nl_to_sql(natural_language: str, schema_summary: str) -> str:
    system = (
        "You are a SQL expert working with a SQLite database for SigmaPay, "
        "an Indian UPI payments company. "
        "Convert the natural language question to a valid SQLite SELECT query. "
        "Return ONLY the SQL query, no explanation, no markdown, no code blocks. "
        "Use only tables and columns from the schema provided."
    )
    user_msg = (
        f"Database schema:\n{schema_summary}\n\n"
        f"Question: {natural_language}\n\n"
        "Return only the SQL SELECT query."
    )
    return call_haiku(system, user_msg)


# ─────────────────────────────────────────────
# SCHEMA SUMMARY for NL→SQL context
# ─────────────────────────────────────────────
def build_schema_summary() -> str:
    schema = get_schema_info()
    lines = []
    for table, cols in schema.items():
        col_str = ", ".join(f"{c[0]} ({c[1]})" for c in cols)
        lines.append(f"Table {table}: {col_str}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f1923 0%, #1a2a3a 100%);
    }
    [data-testid="stSidebar"] .stRadio label {
        color: #e0e0e0 !important;
        font-size: 1rem;
    }

    /* Cards */
    .fraud-card {
        background: #1e2d3d;
        border: 1px solid #2a4a6a;
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1rem;
    }
    .fraud-card h4 { color: #00d4ff; margin: 0 0 0.4rem 0; }
    .fraud-card p { color: #b0c4de; margin: 0.2rem 0; font-size: 0.9rem; }

    .quiz-card {
        background: #1a2535;
        border: 1px solid #2a3f5a;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
    }
    .quiz-card .level { font-size: 0.85rem; margin-bottom: 0.3rem; }
    .quiz-card h4 { color: #7ecfff; margin: 0 0 0.5rem 0; }

    /* SQL display box */
    .sql-box {
        background: #0d1b2a;
        border: 1px solid #1a6b8a;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        color: #64ffda;
        white-space: pre-wrap;
        word-break: break-word;
    }

    /* Score badge */
    .score-good { color: #00e676; font-weight: bold; font-size: 1.1rem; }
    .score-bad  { color: #ff5252; font-weight: bold; font-size: 1.1rem; }

    /* Hint box */
    .hint-box {
        background: #1a2e1a;
        border-left: 4px solid #66bb6a;
        padding: 0.7rem 1rem;
        border-radius: 4px;
        color: #c8e6c9;
        font-size: 0.9rem;
        margin-top: 0.5rem;
    }

    /* Hero */
    .hero {
        background: linear-gradient(135deg, #0f1923 0%, #1a3a5c 100%);
        border: 1px solid #2a5a8a;
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        margin-bottom: 2rem;
    }
    .hero h1 { color: #00d4ff; font-size: 2.2rem; margin: 0; }
    .hero p { color: #90caf9; font-size: 1.1rem; margin-top: 0.5rem; }

    /* Metric cards */
    .metric-row {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
        flex-wrap: wrap;
    }
    .metric-card {
        background: #1e2d3d;
        border: 1px solid #2a4a6a;
        border-radius: 10px;
        padding: 1rem 1.5rem;
        flex: 1;
        min-width: 140px;
        text-align: center;
    }
    .metric-card .val { font-size: 1.8rem; font-weight: bold; color: #00d4ff; }
    .metric-card .lbl { font-size: 0.8rem; color: #90caf9; margin-top: 0.2rem; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 SigmaPay")
    st.markdown("**Fraud Detective**")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["🏠 Home", "📝 Module 1: SQL Practice", "🕵️ Module 2: Fraud Detective"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("**Your Progress**")

    if "m1_scores" not in st.session_state:
        st.session_state.m1_scores = {}
    if "m2_results" not in st.session_state:
        st.session_state.m2_results = {}

    total_q = len(SQL_QUESTIONS)
    correct_q = sum(1 for v in st.session_state.m1_scores.values() if v)
    st.progress(correct_q / total_q if total_q else 0)
    st.caption(f"Module 1: {correct_q}/{total_q} correct")

    cases_solved = len(st.session_state.m2_results)
    st.progress(cases_solved / len(FRAUD_CASES))
    st.caption(f"Module 2: {cases_solved}/{len(FRAUD_CASES)} cases run")

    st.markdown("---")
    st.caption("🏢 SigmaPay | Indian UPI Fintech")
    st.caption("📊 Data + AI + FinTech Training")


# ─────────────────────────────────────────────
# HOME PAGE
# ─────────────────────────────────────────────
if page == "🏠 Home":
    st.markdown("""
    <div class="hero">
        <h1>🔍 SigmaPay Fraud Detective</h1>
        <p>India's #1 UPI Payments Platform — Internal Fraud Investigation Tool</p>
        <p style="color:#546e7a; font-size:0.85rem; margin-top:1rem;">
            Training Simulation | Data + AI + FinTech Program
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Live DB metrics
    _, r1, _ = run_query("SELECT COUNT(*) FROM transactions")
    _, r2, _ = run_query("SELECT SUM(amount) FROM transactions")
    _, r3, _ = run_query("SELECT COUNT(*) FROM users")
    _, r4, _ = run_query("SELECT COUNT(*) FROM merchants")
    total_txns = int(r1[0][0]) if r1 else 0
    total_vol  = float(r2[0][0]) if r2 and r2[0][0] else 0
    total_users = int(r3[0][0]) if r3 else 0
    total_merch = int(r4[0][0]) if r4 else 0

    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-card">
            <div class="val">{total_txns:,}</div>
            <div class="lbl">Total Transactions</div>
        </div>
        <div class="metric-card">
            <div class="val">₹{total_vol/100000:.1f}L</div>
            <div class="lbl">Total Volume</div>
        </div>
        <div class="metric-card">
            <div class="val">{total_users}</div>
            <div class="lbl">Registered Users</div>
        </div>
        <div class="metric-card">
            <div class="val">{total_merch}</div>
            <div class="lbl">Merchants</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🗺️ Database Schema")
        schema = get_schema_info()
        for table, cols in schema.items():
            with st.expander(f"📋 `{table}` — {len(cols)} columns"):
                df = pd.DataFrame(cols, columns=["Column", "Type"])
                st.dataframe(df, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("#### 🎯 What You'll Learn Today")
        st.markdown("""
        **Module 1 — SQL Fundamentals**
        - Write real SELECT queries
        - Filter, aggregate, and sort data
        - Instant AI hints when you're stuck

        **Module 2 — Fraud Detection**
        - Investigate 5 real-world fraud cases
        - Questions are pre-loaded — just click Investigate
        - AI converts plain English to SQL automatically
        - Uncover hidden fraud in SigmaPay's data
        """)

        st.markdown("#### 🔒 Fraud Patterns Hidden in the Data")
        patterns = [
            ("🟢", "High-frequency transactions"),
            ("🟢", "Round number amounts"),
            ("🟡", "Threshold skirting (just below ₹10K)"),
            ("🟡", "Dormant account reactivation"),
            ("🔴", "Card testing pattern"),
        ]
        for emoji, pattern in patterns:
            st.markdown(f"{emoji} {pattern}")


# ─────────────────────────────────────────────
# MODULE 1 — SQL PRACTICE
# ─────────────────────────────────────────────
elif page == "📝 Module 1: SQL Practice":
    st.markdown("## 📝 Module 1: SQL Practice")
    st.markdown("Write SQL queries against SigmaPay's live database. Use the table reference below — no need to switch pages!")

    # ── Quick Schema Reference ──────────────────
    with st.expander("📋 Quick Reference — Tables & Columns (click to expand)", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**`transactions`**")
            st.markdown("""
- `txn_id` — unique ID
- `timestamp` — date & time
- `user_id` — who paid
- `merchant_id` — paid to
- `amount` — ₹ amount
- `txn_type` — UPI / REFUND
- `status` — SUCCESS / FAIL
- `device_id`
- `ip_address`
""")
        with c2:
            st.markdown("**`users`**")
            st.markdown("""
- `user_id` — unique ID
- `name` — full name
- `city`
- `phone`
- `upi_id`
- `account_age_days`
- `is_dormant` — 0 or 1
""")
        with c3:
            st.markdown("**`merchants`**")
            st.markdown("""
- `merchant_id` — unique ID
- `name` — shop name
- `category` — type of shop
- `city`
- `is_flagged` — 0 or 1
""")

    # Score summary bar
    correct_count = sum(1 for v in st.session_state.m1_scores.values() if v)
    st.info(f"**Score: {correct_count} / {len(SQL_QUESTIONS)}** correct so far")

    schema_summary = build_schema_summary()

    for q in SQL_QUESTIONS:
        qid = q["id"]
        with st.container():
            st.markdown(f"""
            <div class="quiz-card">
                <div class="level">{q['level']} &nbsp;|&nbsp; Question {qid} of {len(SQL_QUESTIONS)}</div>
                <h4>Q{qid}: {q['title']}</h4>
                <p style="color:#cfd8dc;">{q['prompt']}</p>
            </div>
            """, unsafe_allow_html=True)

            key_sql = f"sql_input_{qid}"
            key_sub = f"submitted_{qid}"
            key_hint = f"hint_{qid}"

            sql_input = st.text_area(
                f"Your SQL for Q{qid}:",
                key=key_sql,
                height=80,
                placeholder="SELECT ...",
                label_visibility="collapsed",
            )

            col_run, col_hint, col_status = st.columns([1, 1, 3])

            with col_run:
                run_clicked = st.button("▶ Run Query", key=f"run_{qid}")
            with col_hint:
                hint_clicked = st.button("💡 Get Hint", key=f"hint_btn_{qid}")

            if run_clicked and sql_input.strip():
                cols, rows, err = run_query(sql_input)
                if err:
                    st.error(f"SQL Error: {err}")
                    st.session_state.m1_scores[qid] = False
                else:
                    try:
                        is_correct = q["check"](cols, rows)
                    except Exception:
                        is_correct = False

                    if is_correct:
                        st.session_state.m1_scores[qid] = True
                        st.markdown('<p class="score-good">✅ Correct! Great job!</p>', unsafe_allow_html=True)
                    else:
                        st.session_state.m1_scores[qid] = False
                        st.markdown('<p class="score-bad">❌ Not quite. Check your query.</p>', unsafe_allow_html=True)

                    if cols and rows:
                        df = pd.DataFrame(rows, columns=cols)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    else:
                        st.caption("Query returned no rows.")

                    if not is_correct:
                        st.caption(f"💬 Expected: {q['expected_display']}")

            if hint_clicked and sql_input.strip():
                with st.spinner("Getting AI hint..."):
                    hint_text = get_sql_hint(q["prompt"], q["hint_context"], sql_input)
                st.markdown(f'<div class="hint-box">💡 <strong>Hint:</strong> {hint_text}</div>',
                            unsafe_allow_html=True)
            elif hint_clicked:
                st.warning("Type your SQL attempt first, then ask for a hint.")

            # Show tick if already correct
            if st.session_state.m1_scores.get(qid):
                with col_status:
                    st.markdown("✅ **Solved!**")

            st.markdown("---")


# ─────────────────────────────────────────────
# MODULE 2 — FRAUD DETECTIVE
# ─────────────────────────────────────────────
elif page == "🕵️ Module 2: Fraud Detective":
    st.markdown("## 🕵️ Module 2: Fraud Detective")
    st.info(
        "👇 **How it works:** Read each case story → The investigation question is already loaded for you → "
        "Click **🔍 Investigate** → See the data → Spot the fraud pattern!"
    )

    schema_summary = build_schema_summary()

    for case in FRAUD_CASES:
        cid = case["id"]

        st.markdown(f"""
        <div class="fraud-card">
            <h4>🔎 Case {cid} of {len(FRAUD_CASES)}: {case['title']} &nbsp; {case['difficulty']}</h4>
            <p><strong>Fraud Type:</strong> {case['fraud_type']}</p>
            <p style="margin-top:0.6rem; color:#90caf9; font-size:1rem;">{case['story']}</p>
        </div>
        """, unsafe_allow_html=True)

        # Pre-fill with case question — shown as read-only looking label + text area
        nl_key = f"nl_input_{cid}"
        if nl_key not in st.session_state:
            st.session_state[nl_key] = case["question"]

        st.caption("📌 Investigation question (pre-loaded — just click Investigate):")
        nl_input = st.text_area(
            f"nl_input_label_{cid}",
            value=st.session_state[nl_key],
            key=nl_key,
            height=68,
            label_visibility="collapsed",
        )

        col_inv, col_tip = st.columns([1, 4])
        with col_inv:
            investigate = st.button(f"🔍 Investigate", key=f"inv_{cid}")
        with col_tip:
            st.caption(f"💡 After results appear — look for: *{case['what_to_look_for']}*")

        result_key = f"result_{cid}"

        if investigate and nl_input.strip():
            with st.spinner("🤖 AI is writing the SQL..."):
                generated_sql = nl_to_sql(nl_input, schema_summary)

            # Clean up in case model wraps in markdown
            clean_sql = generated_sql.strip()
            if clean_sql.startswith("```"):
                clean_sql = clean_sql.split("```")[1]
                if clean_sql.lower().startswith("sql"):
                    clean_sql = clean_sql[3:]
            clean_sql = clean_sql.strip()

            st.markdown("**Generated SQL:**")
            st.markdown(f'<div class="sql-box">{clean_sql}</div>', unsafe_allow_html=True)

            cols, rows, err = run_query(clean_sql)
            if err:
                st.error(f"SQL Error: {err}")
                st.caption("Tip: Edit the SQL above or rephrase your question.")
            else:
                if rows:
                    df = pd.DataFrame(rows, columns=cols) if cols else pd.DataFrame(rows)
                    st.markdown(f"**Results — {len(rows)} row(s) found:**")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.session_state.m2_results[cid] = True
                else:
                    st.info("Query ran successfully but returned no rows. Try rephrasing.")

                st.markdown("""
                <div class="hint-box">
                    📋 <strong>Next step:</strong> Analyse the results above.
                    Report your findings on AhaSlides — the trainer will discuss!
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

    if len(st.session_state.m2_results) == len(FRAUD_CASES):
        st.balloons()
        st.success("🎉 You've investigated all 8 cases! Outstanding detective work!")
