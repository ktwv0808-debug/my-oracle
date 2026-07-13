# ============================================================
# PART 1 : Import
# ============================================================

from flask import (
    Flask,
    render_template,
    request,
    jsonify
)

import os
import threading
import time
from datetime import datetime

import requests
import pandas as pd

import psycopg2
from psycopg2.extras import RealDictCursor


# ------------------------------------------------------------
# Flask
# ------------------------------------------------------------

app = Flask(__name__)

# ============================================================
# PART 2 : PostgreSQL
# ============================================================

# ------------------------------------------------------------
# PostgreSQL Connection
# ------------------------------------------------------------

def get_db():
    """
    Render PostgreSQL 연결
    """

    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL is not set.")

    return psycopg2.connect(database_url)


# ------------------------------------------------------------
# Execute SELECT (Multiple Rows)
# ------------------------------------------------------------

def fetch_all(sql, params=None):

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(sql, params)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


# ------------------------------------------------------------
# Execute SELECT (Single Row)
# ------------------------------------------------------------

def fetch_one(sql, params=None):

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(sql, params)

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row


# ------------------------------------------------------------
# Execute INSERT / UPDATE / DELETE
# ------------------------------------------------------------

def execute(sql, params=None):

    conn = get_db()

    cur = conn.cursor()

    cur.execute(sql, params)

    conn.commit()

    cur.close()
    conn.close()


# ------------------------------------------------------------
# Keep Latest Rows
# ------------------------------------------------------------

def keep_latest_rows(table_name, limit_count=10000):

    conn = get_db()

    cur = conn.cursor()

    cur.execute(f"""
        DELETE FROM {table_name}
        WHERE id NOT IN
        (
            SELECT id
            FROM {table_name}
            ORDER BY id DESC
            LIMIT %s
        )
    """, (limit_count,))

    conn.commit()

    cur.close()
    conn.close()

# ============================================================
# PART 3 : Database
# ============================================================

# ------------------------------------------------------------
# Database Initialize
# ------------------------------------------------------------

def init_db():

    conn = get_db()
    cur = conn.cursor()

    # --------------------------------------------------------
    # ETH PRICE
    # --------------------------------------------------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS eth_price(

        id SERIAL PRIMARY KEY,

        price NUMERIC(18,6),

        ma20 NUMERIC,

        ma60 NUMERIC,

        signal TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)

    # --------------------------------------------------------
    # TRADING RECORDS
    # --------------------------------------------------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS trading_records(

        id SERIAL PRIMARY KEY,

        signal TEXT,

        price NUMERIC(18,6),

        rsi NUMERIC,

        ma20 NUMERIC,

        ma60 NUMERIC,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)

    # --------------------------------------------------------
    # DONATION
    # --------------------------------------------------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS donation_records(

        id SERIAL PRIMARY KEY,

        quarter TEXT,

        net_profit NUMERIC,

        donation NUMERIC,

        proof TEXT

    )
    """)

    # --------------------------------------------------------
    # PORTFOLIO
    # --------------------------------------------------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS portfolio(

        id SERIAL PRIMARY KEY,

        cash NUMERIC DEFAULT 100000,

        eth NUMERIC DEFAULT 0,

        avg_price NUMERIC DEFAULT 0

    )
    """)

    conn.commit()

    cur.close()
    conn.close()


# ------------------------------------------------------------
# Update Old Database
# ------------------------------------------------------------

def update_database():

    conn = get_db()
    cur = conn.cursor()

    # ETH PRICE

    cur.execute("""
    ALTER TABLE eth_price
    ADD COLUMN IF NOT EXISTS ma20 NUMERIC
    """)

    cur.execute("""
    ALTER TABLE eth_price
    ADD COLUMN IF NOT EXISTS ma60 NUMERIC
    """)

    cur.execute("""
    ALTER TABLE eth_price
    ADD COLUMN IF NOT EXISTS signal TEXT
    """)

    # TRADING RECORDS

    cur.execute("""
    ALTER TABLE trading_records
    ADD COLUMN IF NOT EXISTS rsi NUMERIC
    """)

    cur.execute("""
    ALTER TABLE trading_records
    ADD COLUMN IF NOT EXISTS ma20 NUMERIC
    """)

    cur.execute("""
    ALTER TABLE trading_records
    ADD COLUMN IF NOT EXISTS ma60 NUMERIC
    """)

    conn.commit()

    cur.close()
    conn.close()

    print("Database Updated")


# ------------------------------------------------------------
# Insert Default Portfolio
# ------------------------------------------------------------

def insert_default_portfolio():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""

        INSERT INTO portfolio
        (cash,eth,avg_price)

        SELECT
            100000,
            0,
            0

        WHERE NOT EXISTS
        (
            SELECT 1
            FROM portfolio
        )

    """)

    conn.commit()

    cur.close()
    conn.close()


# ------------------------------------------------------------
# Insert Test Data
# ------------------------------------------------------------

def insert_test_data():

    conn = get_db()
    cur = conn.cursor()

    # ETH PRICE

    cur.execute("SELECT COUNT(*) FROM eth_price")

    if cur.fetchone()[0] == 0:

        cur.execute("""

        INSERT INTO eth_price
        (price)

        VALUES

        (1578.325),

        (1585.500),

        (1602.750)

        """)

    # TRADING RECORDS

    cur.execute("SELECT COUNT(*) FROM trading_records")

    if cur.fetchone()[0] == 0:

        cur.execute("""

        INSERT INTO trading_records
        (signal,price)

        VALUES

        ('BUY',1578.325),

        ('SELL',1585.500),

        ('BUY',1602.750)

        """)

    # DONATION

    cur.execute("SELECT COUNT(*) FROM donation_records")

    if cur.fetchone()[0] == 0:

        cur.execute("""

        INSERT INTO donation_records

        (quarter,net_profit,donation,proof)

        VALUES

        ('2026 Q1',0,0,'Preparing'),

        ('2026 Q2',0,0,'Preparing')

        """)

    conn.commit()

    cur.close()
    conn.close()

# ============================================================
# PART 4 : Indicator
# ============================================================

# ------------------------------------------------------------
# RSI Calculation
# ------------------------------------------------------------

def calculate_rsi(period=14):

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT price
        FROM eth_price
        ORDER BY id ASC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    if len(rows) < period + 1:
        return None

    prices = pd.Series([float(r["price"]) for r in rows])

    delta = prices.diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()

    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return round(float(rsi.iloc[-1]), 2)


# ------------------------------------------------------------
# Moving Average
# ------------------------------------------------------------

def calculate_ma(period):

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT price
        FROM eth_price
        ORDER BY id DESC
        LIMIT %s
    """, (period,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    if len(rows) < period:
        return None

    prices = [float(r["price"]) for r in rows]

    prices.reverse()

    return round(sum(prices) / period, 2)


# ------------------------------------------------------------
# Previous Moving Average
# ------------------------------------------------------------

def calculate_previous_ma(period):

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT price
        FROM eth_price
        ORDER BY id DESC
        LIMIT %s
    """, (period + 1,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    if len(rows) < period + 1:
        return None

    prices = [float(r["price"]) for r in rows]

    prices.reverse()

    previous_prices = prices[:-1]

    return round(sum(previous_prices) / period, 2)


# ------------------------------------------------------------
# Trading Signal
# ------------------------------------------------------------

def generate_signal():

    rsi = calculate_rsi()

    ma20 = calculate_ma(20)

    ma60 = calculate_ma(60)

    prev20 = calculate_previous_ma(20)

    prev60 = calculate_previous_ma(60)

    signal = "HOLD"

    if None in (rsi, ma20, ma60, prev20, prev60):

        signal = "HOLD"

    else:

        # 골든크로스
        if prev20 <= prev60 and ma20 > ma60:

            if rsi < 30:
                signal = "BUY"
            else:
                signal = "BUY"

        # 데드크로스
        elif prev20 >= prev60 and ma20 < ma60:

            if rsi > 70:
                signal = "SELL"
            else:
                signal = "SELL"

        else:

            signal = "HOLD"

    return {

        "signal": signal,

        "rsi": rsi,

        "ma20": ma20,

        "ma60": ma60

    }
# ------------------------------------------------------------
# Live ETH Price
# ------------------------------------------------------------

KRAKEN_URL = "https://api.kraken.com/0/public/Ticker?pair=ETHUSD"

def get_eth_price():

    try:

        response = requests.get(
            KRAKEN_URL,
            timeout=5
        )

        response.raise_for_status()

        data = response.json()

        price = float(
            data["result"]["XETHZUSD"]["c"][0]
        )

        return price

    except Exception as e:

        print("KRAKEN ERROR :", e)

        return None
# ============================================================
# PART 5 : Auto Save
# ============================================================

def auto_save_eth():

    while True:

        try:

            # ------------------------------------------------
            # 현재 ETH 가격
            # ------------------------------------------------

            price = get_eth_price()

            if price is None:

                time.sleep(30)
                continue

            # ------------------------------------------------
            # DB 저장 (가격만 먼저 저장)
            # ------------------------------------------------

            conn = get_db()

            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""

                INSERT INTO eth_price(price)

                VALUES(%s)

                RETURNING id

            """,(price,))

            new_id = cur.fetchone()["id"]

            conn.commit()

            # ------------------------------------------------
            # 이동평균 계산
            # ------------------------------------------------

            ma20 = calculate_ma(20)

            ma60 = calculate_ma(60)

            # ------------------------------------------------
            # 신호 계산
            # ------------------------------------------------

            signal_data = generate_signal()

            signal = signal_data["signal"]

            # ------------------------------------------------
            # 같은 행 UPDATE
            # ------------------------------------------------

            cur.execute("""

                UPDATE eth_price

                SET

                    ma20=%s,

                    ma60=%s,

                    signal=%s

                WHERE id=%s

            """,

            (

                ma20,

                ma60,

                signal,

                new_id

            ))

            conn.commit()

            cur.close()

            conn.close()

            print(

                f"[AUTO] "

                f"Price={price:.2f} "

                f"MA20={ma20} "

                f"MA60={ma60} "

                f"Signal={signal}"

            )

        except Exception as e:

            print("AUTO SAVE ERROR :", e)

        # ------------------------------------------------
        # 10분마다 저장
        # ------------------------------------------------

        time.sleep(600)

# ==========================================================
# PART 6 : Portfolio
# ==========================================================

# --------------------------------------
# Portfolio 조회
# --------------------------------------
def calculate_portfolio():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Portfolio가 없으면 생성
    cur.execute("""
        SELECT *
        FROM portfolio
        LIMIT 1
    """)

    portfolio = cur.fetchone()

    if portfolio is None:

        cur.execute("""
            INSERT INTO portfolio
            (
                cash,
                eth,
                avg_price
            )
            VALUES
            (
                100000,
                0,
                0
            )
        """)

        conn.commit()

        cur.execute("""
            SELECT *
            FROM portfolio
            LIMIT 1
        """)

        portfolio = cur.fetchone()

    # 현재 ETH 가격
    cur.execute("""
        SELECT price
        FROM eth_price
        ORDER BY id DESC
        LIMIT 1
    """)

    row = cur.fetchone()

    current_price = 0

    if row:
        current_price = float(row["price"])

    cash = float(portfolio["cash"])
    eth = float(portfolio["eth"])
    avg_price = float(portfolio["avg_price"])

    asset_value = eth * current_price
    total_assets = cash + asset_value

    if eth > 0:
        profit = asset_value - (eth * avg_price)
    else:
        profit = 0

    if eth > 0 and avg_price > 0:
        roi = ((current_price - avg_price) / avg_price) * 100
    else:
        roi = 0

    cur.close()
    conn.close()

    return {

        "cash": round(cash, 2),

        "eth": round(eth, 8),

        "avg_price": round(avg_price, 2),

        "current_price": round(current_price, 2),

        "asset_value": round(asset_value, 2),

        "total_assets": round(total_assets, 2),

        "profit": round(profit, 2),

        "roi": round(roi, 2)

    }

# ==========================================================
# PART 7  Routes
# ==========================================================

# -----------------------------
# Home
# -----------------------------
@app.route("/")
def home():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM donation_records
        ORDER BY id DESC
    """)

    donations = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "donation.html",
        donations=donations
    )


# -----------------------------
# Trading Menu
# -----------------------------
@app.route("/trading")
def trading():
    return render_template("trading.html")


# -----------------------------
# Whitepaper
# -----------------------------
@app.route("/whitepaper")
def whitepaper():
    return render_template("whitepaper.html")


# -----------------------------
# Poem
# -----------------------------
@app.route("/poem")
def poem():
    return render_template("poem.html")


# -----------------------------
# Save Price
# -----------------------------
@app.route("/save-price")
def save_price():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM eth_price
        ORDER BY id DESC
        LIMIT 100
    """)

    prices = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "save_price.html",
        prices=prices,
        live_price=get_eth_price()
    )


# -----------------------------
# Price History
# -----------------------------
@app.route("/history")
def history():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM eth_price
        ORDER BY id DESC
        LIMIT 500
    """)

    prices = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "history.html",
        prices=prices
    )

# ----------------------------------------------------------
# Price Page
# ----------------------------------------------------------
@app.route("/price")
def price():

    live_price = get_eth_price()

    conn = get_db()

    cur = conn.cursor(
        cursor_factory=RealDictCursor
    )

    cur.execute("""

        SELECT *

        FROM eth_price

        ORDER BY id DESC

        LIMIT 100

    """)

    prices = cur.fetchall()

    cur.close()

    conn.close()

    return render_template(

        "price.html",

        live_price=live_price,

        prices=prices

    )
# -----------------------------
# Trade Check
# -----------------------------
@app.route("/trade-check")
def trade_check():

    signal = generate_signal()

    return render_template(
        "trade_check.html",
        signal=signal["signal"],
        rsi=signal["rsi"],
        ma20=signal["ma20"],
        ma60=signal["ma60"]
    )


# -----------------------------
# Trading Records
# -----------------------------
@app.route("/trades")
def trades():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM trading_records
        ORDER BY id DESC
        LIMIT 200
    """)

    records = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "trades.html",
        records=records
    )


# -----------------------------
# Portfolio
# -----------------------------
@app.route("/portfolio")
def portfolio():

    portfolio = calculate_portfolio()

    return render_template(
        "portfolio.html",
        portfolio=portfolio
    )


# -----------------------------
# Chart
# -----------------------------
@app.route("/chart")
def chart():

    return render_template("chart.html")

# =====================================
# PART 8 Chart API
# =====================================

@app.route("/chart-data")
def chart_data():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            created_at,
            price
        FROM eth_price
        ORDER BY id ASC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    labels = []
    prices = []

    ma20 = []
    ma60 = []

    buy = []
    sell = []

    golden = []
    dead = []

    prev_ma20 = None
    prev_ma60 = None

    for i, row in enumerate(rows):

        price = float(row["price"])

        labels.append(
            row["created_at"].strftime("%H:%M:%S")
        )

        prices.append(price)

        # ------------------------
        # MA20
        # ------------------------

        if i >= 19:
            current_ma20 = sum(prices[i-19:i+1]) / 20
        else:
            current_ma20 = None

        ma20.append(current_ma20)

        # ------------------------
        # MA60
        # ------------------------

        if i >= 59:
            current_ma60 = sum(prices[i-59:i+1]) / 60
        else:
            current_ma60 = None

        ma60.append(current_ma60)

        # ------------------------
        # 기본값
        # ------------------------

        buy.append(None)
        sell.append(None)
        golden.append(None)
        dead.append(None)

        # ------------------------
        # Cross Check
        # ------------------------

        if (
            prev_ma20 is not None
            and prev_ma60 is not None
            and current_ma20 is not None
            and current_ma60 is not None
        ):

            # 골든크로스
            if prev_ma20 <= prev_ma60 and current_ma20 > current_ma60:

                golden[-1] = price
                buy[-1] = price

            # 데드크로스
            elif prev_ma20 >= prev_ma60 and current_ma20 < current_ma60:

                dead[-1] = price
                sell[-1] = price

        prev_ma20 = current_ma20
        prev_ma60 = current_ma60

    return jsonify({

        "labels": labels,

        "prices": prices,

        "ma20": ma20,

        "ma60": ma60,

        "buy": buy,

        "sell": sell,

        "golden": golden,

        "dead": dead

    })

# ==========================================================
# PART 9 : Thread
# ==========================================================

# ---------------------------------------------
# Start Auto Save Thread
# ---------------------------------------------

threading.Thread(
    target=auto_save_eth,
    daemon=True
).start()

# ==========================================================
# PART 10 : app.run()
# ==========================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )
