# ============================================================
# PART 1
# Import
# ============================================================

# -----------------------------
# Flask
# -----------------------------
from flask import (
    Flask,
    render_template,
    request,
    jsonify
)

# -----------------------------
# PostgreSQL
# -----------------------------
import psycopg2
from psycopg2.extras import RealDictCursor

# -----------------------------
# Thread
# -----------------------------
import threading
import time

# -----------------------------
# Date
# -----------------------------
from datetime import datetime

# -----------------------------
# HTTP
# -----------------------------
import requests

# -----------------------------
# Numeric
# -----------------------------
import pandas as pd
import numpy as np

# -----------------------------
# Environment
# -----------------------------
import os

# -----------------------------
# Flask App
# -----------------------------
app = Flask(__name__)

# ============================================================
# PART 2
# PostgreSQL Connection
# ============================================================

# -----------------------------
# Render PostgreSQL URL
# -----------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

# -----------------------------
# PostgreSQL Connection
# -----------------------------
def get_db():

    conn = psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )

    return conn


# -----------------------------
# Test Connection
# -----------------------------
try:

    conn = get_db()

    cur = conn.cursor()

    cur.execute("SELECT NOW();")

    print("✅ PostgreSQL Connected")

    cur.close()
    conn.close()

except Exception as e:

    print("❌ PostgreSQL Connection Error")
    print(e)

# ============================================================
# PART 3
# Database Initialization
# ============================================================

# -----------------------------
# Create Tables
# -----------------------------
def init_db():

    conn = get_db()
    cur = conn.cursor()

    # =====================================================
    # ETH Price Table
    # =====================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS eth_price(

        id SERIAL PRIMARY KEY,

        price DOUBLE PRECISION NOT NULL,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    );
    """)

    # =====================================================
    # Trading Records Table
    # =====================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trading_records(

        id SERIAL PRIMARY KEY,

        signal VARCHAR(20),

        price DOUBLE PRECISION,

        rsi DOUBLE PRECISION,

        ma20 DOUBLE PRECISION,

        ma60 DOUBLE PRECISION,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    );
    """)

    # =====================================================
    # Portfolio Table
    # 항상 한 행(ID=1)만 사용
    # =====================================================
    cur.execute("""
    CREATE TABLE IF NOT EXISTS portfolio(

        id INTEGER PRIMARY KEY,

        cash DOUBLE PRECISION,

        eth DOUBLE PRECISION,

        avg_buy DOUBLE PRECISION

    );
    """)

    # -----------------------------
    # Portfolio Default Value
    # -----------------------------
    cur.execute("""
    INSERT INTO portfolio(id,cash,eth,avg_buy)

    VALUES(1,100000,0,0)

    ON CONFLICT(id)

    DO NOTHING;
    """)

    conn.commit()

    cur.close()
    conn.close()


# -----------------------------
# Initialize Database
# -----------------------------
init_db()

# ============================================================
# PART 4
# Indicator
# ============================================================

# ------------------------------------------------------------
# Get Live ETH Price (Binance)
# ------------------------------------------------------------
def get_eth_price():

    try:

        url = "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT"

        response = requests.get(url, timeout=10)

        data = response.json()

        return float(data["price"])

    except Exception:

        return None


# ------------------------------------------------------------
# Get Price History
# ------------------------------------------------------------
def get_price_history(limit=200):

    conn = get_db()

    cur = conn.cursor()

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

    prices.reverse()

    return prices


# ------------------------------------------------------------
# Moving Average
# ------------------------------------------------------------
def calculate_ma(period):

    prices = get_price_history(period)

    if len(prices) < period:

        return None

    return round(sum(prices[-period:]) / period, 2)


# ------------------------------------------------------------
# Previous Moving Average
# ------------------------------------------------------------
def calculate_previous_ma(period):

    prices = get_price_history(period + 1)

    if len(prices) < period + 1:

        return None

    return round(sum(prices[-period-1:-1]) / period, 2)


# ------------------------------------------------------------
# RSI
# ------------------------------------------------------------
def calculate_rsi(period=14):

    prices = get_price_history(period + 1)

    if len(prices) < period + 1:

        return None

    delta = np.diff(prices)

    gain = np.where(delta > 0, delta, 0)

    loss = np.where(delta < 0, -delta, 0)

    avg_gain = gain.mean()

    avg_loss = loss.mean()

    if avg_loss == 0:

        return 100.0

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return round(rsi, 2)


# ------------------------------------------------------------
# Trading Signal
# ------------------------------------------------------------
def generate_signal():

    price = get_eth_price()

    rsi = calculate_rsi()

    ma20 = calculate_ma(20)

    ma60 = calculate_ma(60)

    prev20 = calculate_previous_ma(20)

    prev60 = calculate_previous_ma(60)

    signal = "HOLD"

    if None in (price, rsi, ma20, ma60, prev20, prev60):

        signal = "HOLD"

    else:

        # 골든크로스
        if prev20 <= prev60 and ma20 > ma60:

            signal = "BUY"

        # 데드크로스
        elif prev20 >= prev60 and ma20 < ma60:

            signal = "SELL"

        else:

            signal = "HOLD"

    return {

        "price": price,

        "signal": signal,

        "rsi": rsi,

        "ma20": ma20,

        "ma60": ma60

    }

# ============================================================
# PART 5
# Auto Save
# ============================================================

# ------------------------------------------------------------
# Auto Save ETH Price & Trading Signal
# ------------------------------------------------------------
def auto_save_eth():

    while True:

        try:

            # ------------------------------------------
            # Signal 생성
            # ------------------------------------------
            signal = generate_signal()

            # 가격이 없으면 저장하지 않음
            if signal["price"] is None:

                time.sleep(10)
                continue

            conn = get_db()
            cur = conn.cursor()

            # ------------------------------------------
            # ETH Price 저장
            # ------------------------------------------
            cur.execute("""
                INSERT INTO eth_price(price)

                VALUES(%s)
            """, (

                signal["price"],

            ))

            # ------------------------------------------
            # Trading Signal 저장
            # ------------------------------------------
            cur.execute("""
                INSERT INTO trading_records(

                    signal,
                    price,
                    rsi,
                    ma20,
                    ma60

                )

                VALUES(

                    %s,
                    %s,
                    %s,
                    %s,
                    %s

                )
            """, (

                signal["signal"],
                signal["price"],
                signal["rsi"],
                signal["ma20"],
                signal["ma60"]

            ))

            conn.commit()

            cur.close()
            conn.close()

            print(

                f"[AUTO SAVE] "

                f"{signal['signal']} | "

                f"{signal['price']}"

            )

        except Exception as e:

            print("Auto Save Error :", e)

        # ------------------------------------------
        # 10초마다 저장
        # ------------------------------------------
        time.sleep(10)

# ============================================================
# PART 6
# Portfolio
# ============================================================

# ------------------------------------------------------------
# Calculate Portfolio
# ------------------------------------------------------------
def calculate_portfolio():

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ------------------------------------------
    # Portfolio 정보 읽기
    # ------------------------------------------
    cur.execute("""

        SELECT *

        FROM portfolio

        WHERE id=1

    """)

    row = cur.fetchone()

    cur.close()
    conn.close()

    # ------------------------------------------
    # 기본값
    # ------------------------------------------
    cash = float(row["cash"])

    eth = float(row["eth"])

    avg_buy = float(row["avg_buy"])

    # ------------------------------------------
    # 현재가격
    # ------------------------------------------
    current_price = get_eth_price()

    if current_price is None:

        current_price = 0

    # ------------------------------------------
    # ETH 자산
    # ------------------------------------------
    asset_value = eth * current_price

    # ------------------------------------------
    # 총자산
    # ------------------------------------------
    total_assets = cash + asset_value

    # ------------------------------------------
    # 투자원금
    # ------------------------------------------
    invested = cash + (eth * avg_buy)

    # ------------------------------------------
    # 손익
    # ------------------------------------------
    profit = total_assets - invested

    # ------------------------------------------
    # 수익률
    # ------------------------------------------
    if invested > 0:

        roi = (profit / invested) * 100

    else:

        roi = 0

    return {

        "cash": round(cash,2),

        "eth": round(eth,6),

        "avg_buy": round(avg_buy,2),

        "current_price": round(current_price,2),

        "asset_value": round(asset_value,2),

        "total_assets": round(total_assets,2),

        "profit": round(profit,2),

        "roi": round(roi,2)

    }


# ------------------------------------------------------------
# Buy ETH
# ------------------------------------------------------------
def buy_eth(amount):

    portfolio = calculate_portfolio()

    price = portfolio["current_price"]

    if price <= 0:

        return

    conn = get_db()

    cur = conn.cursor()

    cash = portfolio["cash"]

    eth = portfolio["eth"]

    avg = portfolio["avg_buy"]

    if cash < amount:

        cur.close()

        conn.close()

        return

    qty = amount / price

    new_eth = eth + qty

    if eth == 0:

        new_avg = price

    else:

        new_avg = ((eth * avg) + (qty * price)) / new_eth

    new_cash = cash - amount

    cur.execute("""

        UPDATE portfolio

        SET

            cash=%s,

            eth=%s,

            avg_buy=%s

        WHERE id=1

    """,(

        new_cash,

        new_eth,

        new_avg

    ))

    conn.commit()

    cur.close()

    conn.close()


# ------------------------------------------------------------
# Sell ETH
# ------------------------------------------------------------
def sell_eth():

    portfolio = calculate_portfolio()

    conn = get_db()

    cur = conn.cursor()

    cash = portfolio["cash"]

    eth = portfolio["eth"]

    price = portfolio["current_price"]

    new_cash = cash + (eth * price)

    cur.execute("""

        UPDATE portfolio

        SET

            cash=%s,

            eth=0,

            avg_buy=0

        WHERE id=1

    """,(

        new_cash,

    ))

    conn.commit()

    cur.close()

    conn.close()

# ============================================================
# PART 7
# ROUTES
# ============================================================

from flask import render_template, request, jsonify, redirect


# ------------------------------------------------------------
# HOME
# donation.html
# ------------------------------------------------------------
@app.route("/")
def home():

    return render_template("donation.html")


# ------------------------------------------------------------
# Whitepaper
# ------------------------------------------------------------
@app.route("/whitepaper")
def whitepaper():

    return render_template("whitepaper.html")


# ------------------------------------------------------------
# Toward Victory
# ------------------------------------------------------------
@app.route("/toward-victory")
def toward_victory():

    return render_template("toward_victory.html")


# ------------------------------------------------------------
# Trading Main
# ------------------------------------------------------------
@app.route("/trading")
def trading():

    return render_template("trading.html")


# ------------------------------------------------------------
# Live Price API
# ------------------------------------------------------------
@app.route("/price")
def price():

    return jsonify({

        "price": get_eth_price()

    })


# ------------------------------------------------------------
# Save ETH Price
# ------------------------------------------------------------
@app.route("/save-price", methods=["GET", "POST"])
def save_price():

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    message = ""

    if request.method == "POST":

        signal = generate_signal()

        cur.execute("""

            INSERT INTO eth_price(price)

            VALUES(%s)

        """, (

            signal["price"],

        ))

        conn.commit()

        message = "ETH Price Saved!"

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

        live_price=get_eth_price(),

        message=message

    )


# ------------------------------------------------------------
# Price History
# ------------------------------------------------------------
@app.route("/history")
def history():

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""

        SELECT *

        FROM eth_price

        ORDER BY id DESC

        LIMIT 300

    """)

    prices = cur.fetchall()

    cur.close()

    conn.close()

    return render_template(

        "history.html",

        prices=prices

    )


# ------------------------------------------------------------
# Trade Check
# ------------------------------------------------------------
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


# ------------------------------------------------------------
# Trading Records
# ------------------------------------------------------------
@app.route("/trades")
def trades():

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""

        SELECT *

        FROM trading_records

        ORDER BY id DESC

        LIMIT 300

    """)

    records = cur.fetchall()

    cur.close()

    conn.close()

    return render_template(

        "trades.html",

        records=records

    )


# ------------------------------------------------------------
# Portfolio
# ------------------------------------------------------------
@app.route("/portfolio")
def portfolio():

    portfolio = calculate_portfolio()

    return render_template(

        "portfolio.html",

        portfolio=portfolio

    )


# ------------------------------------------------------------
# Chart
# ------------------------------------------------------------
@app.route("/chart")
def chart():

    return render_template("chart.html")


# ------------------------------------------------------------
# Chart API
# (Part8에서 실제 구현)
# ------------------------------------------------------------
@app.route("/chart-data")
def chart_data():

    return jsonify({})

# ============================================================
# PART 8
# CHART DATA API
# ============================================================

@app.route("/chart-data")
def chart_data():

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""

        SELECT
            id,
            price,
            created_at

        FROM eth_price

        ORDER BY id ASC

    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    prices = []
    labels = []

    # -----------------------------
    # 가격 / 시간
    # -----------------------------
    for r in rows:

        prices.append(float(r["price"]))

        labels.append(r["created_at"].strftime("%H:%M"))

    # -----------------------------
    # MA20
    # -----------------------------
    ma20 = []

    for i in range(len(prices)):

        if i < 19:

            ma20.append(None)

        else:

            avg = sum(prices[i-19:i+1]) / 20

            ma20.append(round(avg,2))

    # -----------------------------
    # MA60
    # -----------------------------
    ma60 = []

    for i in range(len(prices)):

        if i < 59:

            ma60.append(None)

        else:

            avg = sum(prices[i-59:i+1]) / 60

            ma60.append(round(avg,2))

    # -----------------------------
    # BUY
    # -----------------------------
    buy = [None]*len(prices)

    # -----------------------------
    # SELL
    # -----------------------------
    sell = [None]*len(prices)

    # -----------------------------
    # GOLDEN
    # -----------------------------
    golden = [None]*len(prices)

    # -----------------------------
    # DEAD
    # -----------------------------
    dead = [None]*len(prices)

    # -----------------------------
    # Cross Detection
    # -----------------------------
    for i in range(60,len(prices)):

        if None in (

            ma20[i],

            ma60[i],

            ma20[i-1],

            ma60[i-1]

        ):

            continue

        # -------------------------
        # GOLDEN CROSS
        # -------------------------
        if (

            ma20[i-1] <= ma60[i-1]

            and

            ma20[i] > ma60[i]

        ):

            golden[i] = prices[i]

            buy[i] = prices[i]

        # -------------------------
        # DEAD CROSS
        # -------------------------
        elif (

            ma20[i-1] >= ma60[i-1]

            and

            ma20[i] < ma60[i]

        ):

            dead[i] = prices[i]

            sell[i] = prices[i]

    return jsonify({

        "labels":labels,

        "prices":prices,

        "ma20":ma20,

        "ma60":ma60,

        "buy":buy,

        "sell":sell,

        "golden":golden,

        "dead":dead

    })

# ============================================================
# PART 9
# BACKGROUND THREAD
# ============================================================

import threading
import time


# ------------------------------------------------------------
# Auto Save ETH Price
# ------------------------------------------------------------
def auto_save_eth():

    while True:

        try:

            signal = generate_signal()

            conn = get_db()

            cur = conn.cursor()

            # ----------------------------
            # ETH PRICE 저장
            # ----------------------------
            cur.execute("""

                INSERT INTO eth_price(price)

                VALUES(%s)

            """, (

                signal["price"],

            ))

            # ----------------------------
            # Trading Signal 저장
            # ----------------------------
            cur.execute("""

                INSERT INTO trading_records(

                    signal,
                    price,
                    rsi,
                    ma20,
                    ma60

                )

                VALUES(

                    %s,
                    %s,
                    %s,
                    %s,
                    %s

                )

            """, (

                signal["signal"],
                signal["price"],
                signal["rsi"],
                signal["ma20"],
                signal["ma60"]

            ))

            conn.commit()

            cur.close()

            conn.close()

            print(

                "Saved :",

                signal["signal"],

                signal["price"]

            )

        except Exception as e:

            print(e)

        # ----------------------------
        # 저장 주기
        # ----------------------------
        time.sleep(60)


# ------------------------------------------------------------
# Thread Start
# ------------------------------------------------------------
threading.Thread(

    target=auto_save_eth,

    daemon=True

).start()

# ============================================================
# PART 10
# Run Flask
# ============================================================

import os

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=int(os.environ.get("PORT", 10000)),

        debug=True

    )
