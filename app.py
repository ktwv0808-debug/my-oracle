# =====================================================
# PART 1
# Import
# =====================================================

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for
)

import os
import threading
import time
from datetime import datetime

import requests
import pandas as pd

import psycopg2
from psycopg2.extras import RealDictCursor


# =====================================================
# Flask
# =====================================================

app = Flask(__name__)


# =====================================================
# Kraken API
# =====================================================

KRAKEN_URL = "https://api.kraken.com/0/public/Ticker?pair=ETHUSD"


# =====================================================
# Global Settings
# =====================================================

MAX_PRICE_ROWS = 10000

PRICE_SAVE_INTERVAL = 600      # 10분

MA20_PERIOD = 20

MA60_PERIOD = 60

RSI_PERIOD = 14


# =====================================================
# BUY / SELL Signal
# =====================================================

BUY = "BUY"

SELL = "SELL"

HOLD = "HOLD"


# =====================================================
# PostgreSQL DATABASE_URL
# =====================================================

DATABASE_URL = os.environ.get("DATABASE_URL")


# =====================================================
# End of PART 1
# =====================================================

# =====================================================
# PART 2
# PostgreSQL
# =====================================================

# -----------------------------------------------------
# Database Connection
# -----------------------------------------------------

def get_db():

    if not DATABASE_URL:
        raise Exception("DATABASE_URL not found.")

    return psycopg2.connect(DATABASE_URL)


# -----------------------------------------------------
# Keep latest rows
# -----------------------------------------------------

def keep_10000_rows(table):

    conn = get_db()
    cur = conn.cursor()

    sql = f"""
        DELETE FROM {table}
        WHERE id NOT IN
        (
            SELECT id
            FROM {table}
            ORDER BY id DESC
            LIMIT %s
        )
    """

    cur.execute(sql, (MAX_PRICE_ROWS,))

    conn.commit()

    cur.close()
    conn.close()


# -----------------------------------------------------
# Update Database
# -----------------------------------------------------

def update_database():

    conn = get_db()
    cur = conn.cursor()

    # ===========================
    # ETH PRICE
    # ===========================

    cur.execute("""

    CREATE TABLE IF NOT EXISTS eth_price(

        id SERIAL PRIMARY KEY,

        price NUMERIC,

        ma20 NUMERIC,

        ma60 NUMERIC,

        signal TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )

    """)

    # ===========================
    # Trading Records
    # ===========================

    cur.execute("""

    CREATE TABLE IF NOT EXISTS trading_records(

        id SERIAL PRIMARY KEY,

        signal TEXT,

        price NUMERIC,

        rsi NUMERIC,

        ma20 NUMERIC,

        ma60 NUMERIC,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )

    """)

    # ===========================
    # Donation
    # ===========================

    cur.execute("""

    CREATE TABLE IF NOT EXISTS donation_records(

        id SERIAL PRIMARY KEY,

        quarter TEXT,

        net_profit NUMERIC,

        donation NUMERIC,

        proof TEXT

    )

    """)

    # ===========================
    # Portfolio
    # ===========================

    cur.execute("""

    CREATE TABLE IF NOT EXISTS portfolio(

        id SERIAL PRIMARY KEY,

        cash NUMERIC DEFAULT 100000,

        eth NUMERIC DEFAULT 0,

        avg_price NUMERIC DEFAULT 0

    )

    """)

    # 최초 Portfolio 생성

    cur.execute("""

    INSERT INTO portfolio

    (

        cash,

        eth,

        avg_price

    )

    SELECT

        100000,

        0,

        0

    WHERE NOT EXISTS(

        SELECT 1

        FROM portfolio

    )

    """)

    conn.commit()

    cur.close()
    conn.close()

    print("Database Updated")


# -----------------------------------------------------
# Initialize Database
# -----------------------------------------------------

def init_db():

    update_database()


# =====================================================
# Database Initialize
# =====================================================

init_db()


# =====================================================
# End of PART 2
# =====================================================

# =====================================================
# PART 3
# Indicator
# =====================================================

# -----------------------------------------------------
# Kraken ETH Price
# -----------------------------------------------------

def get_eth_price():

    try:

        r = requests.get(
            KRAKEN_URL,
            timeout=2
        )

        r.raise_for_status()

        data = r.json()

        return float(
            data["result"]["XETHZUSD"]["c"][0]
        )

    except Exception as e:

        print("KRAKEN ERROR :", e)

        return None


# -----------------------------------------------------
# Read Price List
# -----------------------------------------------------

def get_price_list(limit=None):

    conn = get_db()

    cur = conn.cursor(
        cursor_factory=RealDictCursor
    )

    if limit is None:

        cur.execute("""

            SELECT price

            FROM eth_price

            ORDER BY id ASC

        """)

    else:

        cur.execute("""

            SELECT price

            FROM eth_price

            ORDER BY id DESC

            LIMIT %s

        """, (limit,))

    rows = cur.fetchall()

    cur.close()

    conn.close()

    prices = [float(r["price"]) for r in rows]

    if limit is not None:

        prices.reverse()

    return prices


# -----------------------------------------------------
# Moving Average
# -----------------------------------------------------

def calculate_ma(period):

    prices = get_price_list(period)

    if len(prices) < period:

        return None

    return round(

        sum(prices[-period:]) / period,

        2

    )


# -----------------------------------------------------
# Previous Moving Average
# -----------------------------------------------------

def calculate_previous_ma(period):

    prices = get_price_list(period + 1)

    if len(prices) < period + 1:

        return None

    previous = prices[:-1]

    return round(

        sum(previous[-period:]) / period,

        2

    )


# -----------------------------------------------------
# RSI
# -----------------------------------------------------

def calculate_rsi(period=14):

    prices = get_price_list()

    if len(prices) < period + 1:

        return None

    series = pd.Series(prices)

    delta = series.diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()

    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return round(

        float(rsi.iloc[-1]),

        2

    )


# -----------------------------------------------------
# Signal
# -----------------------------------------------------

def calculate_signal():

    ma20 = calculate_ma(20)

    ma60 = calculate_ma(60)

    prev20 = calculate_previous_ma(20)

    prev60 = calculate_previous_ma(60)

    if None in (

        ma20,

        ma60,

        prev20,

        prev60

    ):

        return HOLD

    if prev20 <= prev60 and ma20 > ma60:

        return BUY

    if prev20 >= prev60 and ma20 < ma60:

        return SELL

    return HOLD


# =====================================================
# End of PART 3
# =====================================================

# =====================================================
# PART 4
# Database Save
# =====================================================

# -----------------------------------------------------
# Save Price
# -----------------------------------------------------

def save_eth_price(price):

    conn = get_db()

    cur = conn.cursor(
        cursor_factory=RealDictCursor
    )

    # ----------------------------------------
    # 마지막 가격 확인
    # ----------------------------------------

    cur.execute("""

        SELECT
            id,
            price

        FROM eth_price

        ORDER BY id DESC

        LIMIT 1

    """)

    last = cur.fetchone()

    if last is not None:

        if float(last["price"]) == float(price):

            cur.close()
            conn.close()

            return False

    # ----------------------------------------
    # 먼저 가격 저장
    # ----------------------------------------

    cur.execute("""

        INSERT INTO eth_price
        (
            price
        )
        VALUES
        (
            %s
        )
        RETURNING id

    """,
    (
        price,
    ))

    new_id = cur.fetchone()["id"]

    conn.commit()

    # ----------------------------------------
    # MA 계산
    # ----------------------------------------

    ma20 = calculate_ma(20)

    ma60 = calculate_ma(60)

    signal = calculate_signal()

    # ----------------------------------------
    # 같은 행 UPDATE
    # ----------------------------------------

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

    keep_10000_rows("eth_price")

    cur.close()
    conn.close()

    return True


# -----------------------------------------------------
# Save Trading Record
# -----------------------------------------------------

def save_trade_record(price):

    conn = get_db()

    cur = conn.cursor(
        cursor_factory=RealDictCursor
    )

    signal = calculate_signal()

    rsi = calculate_rsi()

    ma20 = calculate_ma(20)

    ma60 = calculate_ma(60)

    cur.execute("""

        SELECT signal

        FROM trading_records

        ORDER BY id DESC

        LIMIT 1

    """)

    last = cur.fetchone()

    if last is None or last["signal"] != signal:

        cur.execute("""

            INSERT INTO trading_records

            (

                signal,

                price,

                rsi,

                ma20,

                ma60

            )

            VALUES

            (

                %s,

                %s,

                %s,

                %s,

                %s

            )

        """,
        (

            signal,

            price,

            rsi,

            ma20,

            ma60

        ))

        conn.commit()

    keep_10000_rows("trading_records")

    cur.close()
    conn.close()


# =====================================================
# End of PART 4
# =====================================================

# =====================================================
# PART 5
# Auto Save
# =====================================================

# -----------------------------------------------------
# Auto Save ETH
# -----------------------------------------------------

def auto_save_eth():

    while True:

        try:

            # ----------------------------------------
            # 실시간 ETH 가격
            # ----------------------------------------

            price = get_eth_price()

            if price is not None:

                # ----------------------------------------
                # 가격 저장
                # ----------------------------------------

                saved = save_eth_price(price)

                # ----------------------------------------
                # 거래기록 저장
                # ----------------------------------------

                if saved:

                    save_trade_record(price)

                    print(
                        f"[{datetime.now()}] ETH Saved : {price}"
                    )

        except Exception as e:

            print(
                "AUTO SAVE ERROR :",
                e
            )

        # ----------------------------------------
        # 10분마다 저장
        # ----------------------------------------

        time.sleep(600)


# =====================================================
# End of PART 5
# =====================================================

# =====================================================
# PART 6
# Portfolio
# =====================================================

# -----------------------------------------------------
# Portfolio 조회
# -----------------------------------------------------

def get_portfolio():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM portfolio
        LIMIT 1
    """)

    p = cur.fetchone()

    cur.close()
    conn.close()

    return p


# -----------------------------------------------------
# Portfolio 계산
# -----------------------------------------------------

def calculate_portfolio():

    portfolio = get_portfolio()

    cash = float(portfolio["cash"])
    eth = float(portfolio["eth"])
    avg_price = float(portfolio["avg_price"])

    current_price = get_eth_price()

    if current_price is None:
        current_price = 0.0

    asset_value = eth * current_price

    total_assets = cash + asset_value

    profit = asset_value - (eth * avg_price)

    roi = 0

    if eth > 0 and avg_price > 0:

        roi = (
            (current_price - avg_price)
            / avg_price
        ) * 100

    return {

        "cash": cash,

        "eth": eth,

        "avg_price": avg_price,

        "current_price": current_price,

        "asset_value": asset_value,

        "total_assets": total_assets,

        "profit": profit,

        "roi": roi

    }


# -----------------------------------------------------
# ETH 매수
# -----------------------------------------------------

def buy_eth(amount):

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM portfolio
        LIMIT 1
    """)

    p = cur.fetchone()

    current_price = get_eth_price()

    if current_price is None:

        cur.close()
        conn.close()

        return False

    cash = float(p["cash"])
    eth = float(p["eth"])
    avg = float(p["avg_price"])

    cost = amount * current_price

    if cash < cost:

        cur.close()
        conn.close()

        return False

    new_eth = eth + amount

    if new_eth == 0:
        new_avg = 0
    else:
        new_avg = (
            (eth * avg)
            + (amount * current_price)
        ) / new_eth

    new_cash = cash - cost

    cur.execute("""
        UPDATE portfolio
        SET
            cash=%s,
            eth=%s,
            avg_price=%s
    """, (
        new_cash,
        new_eth,
        new_avg
    ))

    conn.commit()

    cur.close()
    conn.close()

    return True


# -----------------------------------------------------
# ETH 매도
# -----------------------------------------------------

def sell_eth(amount):

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM portfolio
        LIMIT 1
    """)

    p = cur.fetchone()

    current_price = get_eth_price()

    if current_price is None:

        cur.close()
        conn.close()

        return False

    cash = float(p["cash"])
    eth = float(p["eth"])
    avg = float(p["avg_price"])

    if eth < amount:

        cur.close()
        conn.close()

        return False

    new_eth = eth - amount

    new_cash = cash + (amount * current_price)

    if new_eth == 0:
        avg = 0

    cur.execute("""
        UPDATE portfolio
        SET
            cash=%s,
            eth=%s,
            avg_price=%s
    """, (
        new_cash,
        new_eth,
        avg
    ))

    conn.commit()

    cur.close()
    conn.close()

    return True


# =====================================================
# End of PART 6
# =====================================================

# =====================================================
# PART 7
# Routes
# =====================================================

# -----------------------------------------------------
# Home
# -----------------------------------------------------

@app.route("/")
def home():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM donation_records
        ORDER BY id
    """)

    donations = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "donation.html",
        donations=donations
    )


# -----------------------------------------------------
# Whitepaper
# -----------------------------------------------------

@app.route("/whitepaper")
def whitepaper():

    return render_template(
        "whitepaper.html"
    )


# -----------------------------------------------------
# Trading
# -----------------------------------------------------

@app.route("/trading")
def trading():

    return render_template(
        "trading.html"
    )


# -----------------------------------------------------
# Poem
# -----------------------------------------------------

@app.route("/poem")
def poem():

    return render_template(
        "poem.html"
    )


# -----------------------------------------------------
# ETH Price
# -----------------------------------------------------

@app.route("/price")
def price():

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
        "price.html",
        live_price=get_eth_price(),
        prices=prices
    )


# -----------------------------------------------------
# Save Price
# -----------------------------------------------------

@app.route("/save-price", methods=["GET", "POST"])
def save_price():

    if request.method == "POST":

        save_current_price()

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


# -----------------------------------------------------
# Price History
# -----------------------------------------------------

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


# -----------------------------------------------------
# Trading Signal
# -----------------------------------------------------

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


# -----------------------------------------------------
# Trading Records
# -----------------------------------------------------

@app.route("/trades")
def trades():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM trading_records
        ORDER BY id DESC
        LIMIT 100
    """)

    records = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "trades.html",
        records=records
    )


# -----------------------------------------------------
# Portfolio
# -----------------------------------------------------

@app.route("/portfolio")
def portfolio():

    portfolio = calculate_portfolio()

    return render_template(
        "portfolio.html",
        portfolio=portfolio
    )


# -----------------------------------------------------
# Buy
# -----------------------------------------------------

@app.route("/buy/<float:amount>")
def buy(amount):

    buy_eth(amount)

    return jsonify({

        "result": "OK"

    })


# -----------------------------------------------------
# Sell
# -----------------------------------------------------

@app.route("/sell/<float:amount>")
def sell(amount):

    sell_eth(amount)

    return jsonify({

        "result": "OK"

    })


# -----------------------------------------------------
# Chart
# -----------------------------------------------------

@app.route("/chart")
def chart():

    return render_template(
        "chart.html"
    )


# =====================================================
# End of PART 7
# =====================================================

# =====================================================
# PART 8
# Chart API
# =====================================================

@app.route("/chart-data")
def chart_data():

    # ----------------------------------------
    # Database Connect
    # ----------------------------------------

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            id,
            created_at,
            price,
            ma20,
            ma60,
            signal
        FROM eth_price
        ORDER BY id ASC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    # ----------------------------------------
    # Arrays
    # ----------------------------------------

    labels = []

    prices = []

    ma20 = []

    ma60 = []

    buy = []

    sell = []

    golden = []

    dead = []

    # ----------------------------------------
    # Previous MA
    # ----------------------------------------

    prev20 = None

    prev60 = None

    # ----------------------------------------
    # Build JSON
    # ----------------------------------------

    for r in rows:

        labels.append(
            r["created_at"].strftime("%H:%M:%S")
        )

        price = float(r["price"])

        prices.append(price)

        m20 = None
        m60 = None

        if r["ma20"] is not None:
            m20 = float(r["ma20"])

        if r["ma60"] is not None:
            m60 = float(r["ma60"])

        ma20.append(m20)
        ma60.append(m60)

        # ------------------------------------
        # BUY / SELL
        # ------------------------------------

        if r["signal"] == "BUY":
            buy.append(price)
        else:
            buy.append(None)

        if r["signal"] == "SELL":
            sell.append(price)
        else:
            sell.append(None)

        # ------------------------------------
        # Golden / Dead Cross
        # ------------------------------------

        if (
            prev20 is not None and
            prev60 is not None and
            m20 is not None and
            m60 is not None
        ):

            if prev20 <= prev60 and m20 > m60:

                golden.append(price)

            else:

                golden.append(None)

            if prev20 >= prev60 and m20 < m60:

                dead.append(price)

            else:

                dead.append(None)

        else:

            golden.append(None)

            dead.append(None)

        prev20 = m20
        prev60 = m60

    # ----------------------------------------
    # JSON Return
    # ----------------------------------------

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

# =====================================================
# END PART 8
# =====================================================

# =====================================================
# PART 9
# Thread & Initialize
# =====================================================

def start_background_thread():

    thread = threading.Thread(

        target=auto_save_eth,

        daemon=True

    )

    thread.start()

    print("Background Thread Started")


# ----------------------------------------
# Initialize Project
# ----------------------------------------

try:

    print("Initializing Database...")

    init_db()

    update_database()

    insert_test_data()

    print("Database Ready")

except Exception as e:

    print("Database Init Error :", e)


# ----------------------------------------
# Start Background Thread
# ----------------------------------------

try:

    start_background_thread()

except Exception as e:

    print("Thread Error :", e)


# =====================================================
# END PART 9
# =====================================================

# ============================================================
# PART 10  Flask Start
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
