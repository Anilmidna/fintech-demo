"""
database.py — SigmaPay Fraud Detective
SQLite setup + seed data with embedded fraud patterns
"""

import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "sigmapay.db"

# ─────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    city        TEXT NOT NULL,
    phone       TEXT NOT NULL,
    upi_id      TEXT UNIQUE NOT NULL,
    account_age_days INTEGER,
    is_dormant  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    city          TEXT NOT NULL,
    is_flagged    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id         TEXT PRIMARY KEY,
    timestamp      TEXT NOT NULL,
    user_id        TEXT NOT NULL,
    merchant_id    TEXT NOT NULL,
    amount         REAL NOT NULL,
    txn_type       TEXT NOT NULL,
    status         TEXT NOT NULL,
    device_id      TEXT,
    ip_address     TEXT,
    FOREIGN KEY (user_id)     REFERENCES users(user_id),
    FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
);
"""

# ─────────────────────────────────────────────
# SEED DATA
# ─────────────────────────────────────────────
INDIAN_NAMES = [
    "Arjun Sharma", "Priya Nair", "Rahul Verma", "Ananya Singh",
    "Kiran Reddy", "Deepa Pillai", "Amit Joshi", "Sneha Kulkarni",
    "Vikram Mehta", "Pooja Iyer", "Suresh Babu", "Kavitha Rao",
    "Rajesh Gupta", "Divya Menon", "Nikhil Patil", "Shweta Agarwal",
    "Harish Nair", "Meena Desai", "Sanjay Patel", "Lakshmi Venkat",
    "Arun Kumar", "Ritu Bhatia", "Manoj Tiwari", "Gayathri Murthy",
    "Vijay Hegde"
]

CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai",
    "Pune", "Kolkata", "Jaipur", "Ahmedabad", "Kochi"
]

MERCHANT_DATA = [
    ("M001", "BigBasket", "Grocery", "Mumbai", 0),
    ("M002", "Swiggy", "Food Delivery", "Bengaluru", 0),
    ("M003", "PhonePe Store", "Electronics", "Delhi", 0),
    ("M004", "Zomato", "Food Delivery", "Mumbai", 0),
    ("M005", "Reliance Digital", "Electronics", "Chennai", 0),
    ("M006", "MakeMyTrip", "Travel", "Delhi", 0),
    ("M007", "Nykaa", "Beauty", "Mumbai", 0),
    ("M008", "BookMyShow", "Entertainment", "Pune", 0),
    ("M009", "Meesho", "Fashion", "Bengaluru", 0),
    ("M010", "FastCash ATM", "Cash Withdrawal", "Hyderabad", 0),
    # Flagged merchants for collusive pattern
    ("M011", "QuickGain Shop", "Misc", "Delhi", 1),
    ("M012", "EasyMoney Kart", "Misc", "Mumbai", 1),
]

BASE_DATE = datetime(2024, 1, 1, 8, 0, 0)


def random_upi(name):
    handle = name.lower().replace(" ", "").replace(".", "")[:8]
    banks = ["okaxis", "oksbi", "okicici", "paytm", "ybl", "upi"]
    return f"{handle}@{random.choice(banks)}"


def random_device():
    return f"DEV_{random.randint(10000, 99999)}"


def random_ip():
    return f"103.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"


def get_connection():
    return sqlite3.connect(DB_PATH)


def setup_database():
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript(SCHEMA_SQL)

    # Check if already seeded
    cur.execute("SELECT COUNT(*) FROM transactions")
    if cur.fetchone()[0] > 0:
        conn.close()
        return

    # ── USERS ──────────────────────────────────
    users = []
    for i, name in enumerate(INDIAN_NAMES):
        uid = f"U{i+1:03d}"
        city = random.choice(CITIES)
        phone = f"9{random.randint(100000000, 999999999)}"
        upi = random_upi(name)
        age = random.randint(30, 1800)
        dormant = 0
        users.append((uid, name, city, phone, upi, age, dormant))

    # Mark U020-U022 as dormant
    users[19] = (users[19][0], users[19][1], users[19][2],
                 users[19][3], users[19][4], 5, 1)
    users[20] = (users[20][0], users[20][1], users[20][2],
                 users[20][3], users[20][4], 8, 1)
    users[21] = (users[21][0], users[21][1], users[21][2],
                 users[21][3], users[21][4], 3, 1)

    cur.executemany(
        "INSERT OR IGNORE INTO users VALUES (?,?,?,?,?,?,?)", users
    )

    # ── MERCHANTS ──────────────────────────────
    cur.executemany(
        "INSERT OR IGNORE INTO merchants VALUES (?,?,?,?,?)", MERCHANT_DATA
    )

    # ── TRANSACTIONS (normal baseline) ─────────
    txns = []
    txn_counter = 1

    def add_txn(ts, uid, mid, amount, ttype="UPI", status="SUCCESS",
                dev=None, ip=None):
        nonlocal txn_counter
        tid = f"TXN{txn_counter:06d}"
        txn_counter += 1
        txns.append((
            tid,
            ts.strftime("%Y-%m-%d %H:%M:%S"),
            uid,
            mid,
            round(amount, 2),
            ttype,
            status,
            dev or random_device(),
            ip or random_ip()
        ))

    # Normal transactions: Days 1–7, daytime hours
    # Exclude fraud-pattern user IDs from the random "noise" pool — otherwise
    # their seeded patterns get diluted with random amounts/merchants, which
    # breaks "always / exactly" claims used in the Module 2 investigation cases
    # (e.g. U008 "always sends round amounts", U015 "always ₹9,800–9,999").
    fraud_pattern_user_ids = {"U003", "U005", "U008", "U012", "U015"}
    normal_merchants = [f"M{i:03d}" for i in range(1, 11)]
    normal_users = [f"U{i:03d}" for i in range(1, 16) if f"U{i:03d}" not in fraud_pattern_user_ids]
    random.seed(42)

    for day in range(7):
        for _ in range(40):
            ts = BASE_DATE + timedelta(days=day,
                                       hours=random.randint(8, 21),
                                       minutes=random.randint(0, 59))
            uid = random.choice(normal_users)
            mid = random.choice(normal_merchants)
            amount = round(random.uniform(50, 3000), 2)
            add_txn(ts, uid, mid, amount)

    # ──────────────────────────────────────────
    # FRAUD PATTERN 1 (Easy): HIGH-FREQUENCY
    # U005 makes 18 txns in 30 minutes on Day 2
    # ──────────────────────────────────────────
    hi_freq_base = BASE_DATE + timedelta(days=1, hours=14)
    for i in range(18):
        ts = hi_freq_base + timedelta(minutes=i * 1.5)
        add_txn(ts, "U005", "M002", random.uniform(200, 800))

    # ──────────────────────────────────────────
    # FRAUD PATTERN 2 (Easy): ROUND NUMBERS
    # U008 always pays exact round amounts
    # ──────────────────────────────────────────
    round_amounts = [500, 1000, 2000, 500, 1500, 1000, 2000,
                     500, 1000, 5000, 500, 1000]
    for i, amt in enumerate(round_amounts):
        ts = BASE_DATE + timedelta(days=i % 7, hours=random.randint(9, 18),
                                   minutes=random.randint(0, 59))
        add_txn(ts, "U008", "M003", amt)

    # ──────────────────────────────────────────
    # FRAUD PATTERN 3 (Easy): ODD HOURS (2–4 AM)
    # U012 transacts at 2–4 AM repeatedly
    # ──────────────────────────────────────────
    for i in range(10):
        ts = BASE_DATE + timedelta(days=i % 7, hours=random.randint(2, 4),
                                   minutes=random.randint(0, 59))
        add_txn(ts, "U012", "M010", random.uniform(500, 3000))

    # ──────────────────────────────────────────
    # FRAUD PATTERN 4 (Medium): JUST BELOW ₹10,000
    # U015 always sends ₹9,800–₹9,999
    # ──────────────────────────────────────────
    for i in range(9):
        ts = BASE_DATE + timedelta(days=i % 7, hours=random.randint(10, 20))
        add_txn(ts, "U015", "M005", round(random.uniform(9800, 9999), 2))

    # ──────────────────────────────────────────
    # FRAUD PATTERN 5 (Medium): DORMANT ACCOUNT REACTIVATION
    # U020/U021 (dormant) suddenly make 8+ txns on Day 5
    # ──────────────────────────────────────────
    for uid in ["U020", "U021"]:
        for i in range(8):
            ts = BASE_DATE + timedelta(days=4, hours=random.randint(9, 22),
                                       minutes=random.randint(0, 59))
            add_txn(ts, uid, random.choice(["M002", "M004", "M009"]),
                    random.uniform(200, 2000))

    # ──────────────────────────────────────────
    # FRAUD PATTERN 6 (Medium): SAME AMOUNT TO MULTIPLE ACCOUNTS
    # U003 sends exactly ₹1,337 to 7 different merchants
    # ──────────────────────────────────────────
    same_amt_merchants = ["M001", "M002", "M003", "M004",
                          "M005", "M006", "M007"]
    for i, mid in enumerate(same_amt_merchants):
        ts = BASE_DATE + timedelta(days=2, hours=10 + i,
                                   minutes=random.randint(5, 55))
        add_txn(ts, "U003", mid, 1337.00)

    # ──────────────────────────────────────────
    # FRAUD PATTERN 7 (Hard): CARD TESTING
    # U018: 5 small txns (₹1–₹10) then 1 large (₹48,000)
    # ──────────────────────────────────────────
    card_test_base = BASE_DATE + timedelta(days=3, hours=11)
    ct_device = "DEV_FRAUD01"
    ct_ip = "182.73.44.99"
    for i in range(5):
        ts = card_test_base + timedelta(minutes=i * 3)
        add_txn(ts, "U018", "M001",
                round(random.uniform(1, 10), 2), dev=ct_device, ip=ct_ip)
    # The big hit
    add_txn(card_test_base + timedelta(minutes=18), "U018", "M005",
            48000.00, dev=ct_device, ip=ct_ip)

    # ──────────────────────────────────────────
    # FRAUD PATTERN 8 (Hard): COLLUSIVE MERCHANTS
    # M011 & M012 receive money from 6 users → refund back to U025
    # ──────────────────────────────────────────
    collude_users = ["U001", "U002", "U004", "U006", "U007", "U009"]
    collude_ip = "103.45.67.89"
    collude_device = "DEV_COLLU99"
    for i, uid in enumerate(collude_users):
        ts = BASE_DATE + timedelta(days=5, hours=9 + i, minutes=10)
        mid = "M011" if i % 2 == 0 else "M012"
        add_txn(ts, uid, mid, round(random.uniform(800, 2500), 2),
                ip=collude_ip)
    # U025 receives refund-like credits from flagged merchants
    for i in range(4):
        ts = BASE_DATE + timedelta(days=5, hours=15 + i, minutes=30)
        mid = "M011" if i % 2 == 0 else "M012"
        add_txn(ts, "U025", mid, 2000.00, ttype="REFUND",
                ip=collude_ip, dev=collude_device)

    cur.executemany(
        "INSERT OR IGNORE INTO transactions VALUES (?,?,?,?,?,?,?,?,?)",
        txns
    )
    conn.commit()
    conn.close()
    print(f"✅ Database seeded: {len(txns)} transactions")


def run_query(sql: str):
    """Run arbitrary SELECT query, return (columns, rows, error)."""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        conn.close()
        return cols, [list(r) for r in rows], None
    except Exception as e:
        return [], [], str(e)


def get_schema_info():
    """Return dict of table → list of (col_name, col_type)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    schema = {}
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        schema[t] = [(r[1], r[2]) for r in cur.fetchall()]
    conn.close()
    return schema


if __name__ == "__main__":
    setup_database()
    schema = get_schema_info()
    for tbl, cols in schema.items():
        print(f"\n📋 {tbl}")
        for col in cols:
            print(f"   {col[0]} ({col[1]})")
