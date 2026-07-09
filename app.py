from flask import Flask, render_template, request, jsonify
import os
import threading
import time
import pandas as pd
from datetime import datetime

import requests
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)



# =====================================================
# PostgreSQL
# =====================================================

def get_db():

    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL missing")

    return psycopg2.connect(database_url)
    
def get_portfolio():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM portfolio
        LIMIT 1
    """)

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row
def update_database():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        ALTER TABLE trading_records
        ADD COLUMN IF NOT EXISTS rsi NUMERIC;
    """)

    cur.execute("""
        ALTER TABLE trading_records
        ADD COLUMN IF NOT EXISTS ma20 NUMERIC;
    """)

    cur.execute("""
        ALTER TABLE trading_records
        ADD COLUMN IF NOT EXISTS ma60 NUMERIC;
    """)
    # ------------------------------------
    # Portfolio Table
    # ------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (

            id SERIAL PRIMARY KEY,

            cash NUMERIC DEFAULT 100000,

            eth NUMERIC DEFAULT 0,

            avg_price NUMERIC DEFAULT 0

        );
    """)

    # 최초 1회만 데이터 생성
    cur.execute("""
        INSERT INTO portfolio (cash, eth, avg_price)
        SELECT 100000, 0, 0
        WHERE NOT EXISTS (
            SELECT 1 FROM portfolio
        );
    """)
    conn.commit()

    cur.close()
    conn.close()

    print("Database Updated")

update_database()
# =====================================================
# COINGECKO
# =====================================================

KRAKEN_URL = "https://api.kraken.com/0/public/Ticker?pair=ETHUSD"

def get_eth_price():

    try:

        r = requests.get(
            KRAKEN_URL,
            timeout=3
        )

        r.raise_for_status()

        data = r.json()

        return float(
            data["result"]["XETHZUSD"]["c"][0]
        )

    except Exception as e:

        print("KRAKEN ERROR:", e)

        return None
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

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return round(float(rsi.iloc[-1]), 2)
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

    return sum(prices) / period

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

    # 가장 최근 가격을 제외한 이전 period개의 평균
    previous_prices = prices[1:]

    return sum(previous_prices) / period
# =====================================================
# Keep latest 10000 rows
# =====================================================

def keep_10000_rows(table):

    conn = get_db()
    cur = conn.cursor()

    cur.execute(f"""
        DELETE FROM {table}
        WHERE id NOT IN (
            SELECT id
            FROM {table}
            ORDER BY id DESC
            LIMIT 10000
        )
    """)

    conn.commit()

    cur.close()
    conn.close()

# =====================================================
# Database Create
# =====================================================

def init_db():

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS eth_price(

            id SERIAL PRIMARY KEY,

            price NUMERIC(18,6),

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS trading_records(

            id SERIAL PRIMARY KEY,

            signal TEXT,

            price NUMERIC(18,6),

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS donation_records(

            id SERIAL PRIMARY KEY,

            quarter TEXT,

            net_profit NUMERIC(18,6),

            donation NUMERIC(18,6),

            proof TEXT

        )
    """)

    conn.commit()

    cur.close()

    conn.close()
# =====================================================
# Test Data
# =====================================================

def insert_test_data():

    conn = get_db()
    cur = conn.cursor()

    # ETH Price
    cur.execute("SELECT COUNT(*) FROM eth_price")

    if cur.fetchone()[0] == 0:

        cur.execute("""

            INSERT INTO eth_price(price)

            VALUES

            (1578.325),

            (1585.500),

            (1602.750)

        """)

    # Trading Records
    cur.execute("SELECT COUNT(*) FROM trading_records")

    if cur.fetchone()[0] == 0:

        cur.execute("""

            INSERT INTO trading_records(signal,price)

            VALUES

            ('BUY SIGNAL',1578.325),

            ('SELL SIGNAL',1585.500),

            ('BUY SIGNAL',1602.750)

        """)

    # Donation Records
    cur.execute("SELECT COUNT(*) FROM donation_records")

    if cur.fetchone()[0] == 0:

        cur.execute("""

            INSERT INTO donation_records
            (quarter,net_profit,donation,proof)

            VALUES

            ('Q1 2026',0,0,'Preparing'),

            ('Q2 2026',0,0,'Preparing')

        """)

    conn.commit()

    cur.close()

    conn.close()


# =====================================================
# Auto Save ETH
# =====================================================

def auto_save_eth():

    while True:

        try:

            eth = get_eth_price()

            if eth is not None:

                conn = get_db()

                cur = conn.cursor()

                cur.execute("""

                    INSERT INTO eth_price(price)

                    VALUES(%s)

                """, (eth,))

                conn.commit()

                cur.close()

                conn.close()

                keep_10000_rows("eth_price")

                print(
                    f"[{datetime.now()}] ETH Saved : {eth}"
                )

        except Exception as e:

            print("AUTO SAVE ERROR :", e)

        # 10분 대기
        time.sleep(600)


# =====================================
# DB 초기화
# =====================================

def init_db():

    conn = get_db()
    cur = conn.cursor()

    # ETH 가격
    cur.execute("""
    CREATE TABLE IF NOT EXISTS eth_price(

        id SERIAL PRIMARY KEY,

        price NUMERIC(18,6),

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)

    # 거래 기록
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trading_records(

        id SERIAL PRIMARY KEY,

        signal TEXT,

        price NUMERIC(18,6),

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)

    # 기부 기록
    cur.execute("""
    CREATE TABLE IF NOT EXISTS donation_records(

        id SERIAL PRIMARY KEY,

        quarter TEXT,

        net_profit NUMERIC(18,6),

        donation NUMERIC(18,6),

        proof TEXT

    )
    """)

    conn.commit()

    cur.close()
    conn.close()


# =====================================
# 테스트 데이터
# =====================================

def insert_test_data():

    conn = get_db()
    cur = conn.cursor()

    # ETH
    cur.execute("SELECT COUNT(*) FROM eth_price")

    if cur.fetchone()[0] == 0:

        cur.execute("""

        INSERT INTO eth_price(price)

        VALUES

        (1500),

        (1520),

        (1540)

        """)

    # Trading
    cur.execute("SELECT COUNT(*) FROM trading_records")

    if cur.fetchone()[0] == 0:

        cur.execute("""

        INSERT INTO trading_records(signal,price)

        VALUES

        ('BUY',1500),

        ('SELL',1520),

        ('BUY',1540)

        """)

    # Donation
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

# =====================================================
# Initialize
# =====================================================

try:

    init_db()

    insert_test_data()

    threading.Thread(

        target=auto_save_eth,

        daemon=True

    ).start()

except Exception as e:

    print("DATABASE INIT ERROR :", e)

# =====================================
# Flask Start
# =====================================

  
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
# =====================================
# 메인 홈페이지
# =====================================

@app.route("/")
def home():

    conn = get_db()

    cur = conn.cursor(
        cursor_factory=RealDictCursor
    )

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
# =====================================
# Automatic Trading System
# =====================================

@app.route("/trading")
def trading():
    return render_template("trading.html")


# =====================================
# Whitepaper
# =====================================

@app.route("/whitepaper")
def whitepaper():
    return render_template("whitepaper.html")


# =====================================
# Toward Victory
# =====================================

@app.route("/poem")
def poem():
    return render_template("poem.html")   
# =====================================
# ETH Price
# =====================================

@app.route("/price")
def price():

    live_price = get_eth_price()

    # 첫 호출 실패 방지
    if live_price is None:
        live_price = 0.0

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
        live_price=live_price,
        prices=prices
    )
# =====================================
# Save ETH Price
# =====================================

@app.route("/save-price", methods=["GET", "POST"])
def save_price():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    message = ""

    if request.method == "POST":

        price = request.form.get("price")

        cur.execute("""
            SELECT price
            FROM eth_price
            ORDER BY id DESC
            LIMIT 1
        """)

        last = cur.fetchone()

        if last is None or float(last["price"]) != float(price):

            cur.execute("""
                INSERT INTO eth_price(price)
                VALUES(%s)
            """, (price,))

            conn.commit()

            message = "Saved Successfully"

        else:

            message = "Same price. Not Saved."

    cur.execute("""
        SELECT *
        FROM eth_price
        ORDER BY id DESC
        LIMIT 100
    """)

    prices = cur.fetchall()

    cur.close()
    conn.close()

    live_price = get_eth_price()

    return render_template(
        "save_price.html",
        prices=prices,
        live_price=live_price,
        message=message
    )
# =====================================
# Price History
# =====================================

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
# =====================================
# Auto Trading Signal
# =====================================

@app.route("/trade-check")
def trade_check():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 최근 가격 2개 조회
    cur.execute("""
        SELECT price
        FROM eth_price
        ORDER BY id DESC
        LIMIT 2
    """)

    rows = cur.fetchall()

    current = 0
    previous = 0

    if len(rows) >= 2:
        current = float(rows[0]["price"])
        previous = float(rows[1]["price"])

    # RSI / 이동평균 계산
    rsi = calculate_rsi()

    ma20 = calculate_ma(20)
    ma60 = calculate_ma(60)

    prev_ma20 = calculate_previous_ma(20)
    prev_ma60 = calculate_previous_ma(60)

    # 기본 신호
    signal = "⚪ HOLD"

    if None in (rsi, ma20, ma60, prev_ma20, prev_ma60):

        signal = "Not enough data"

    # 골든크로스 + RSI
    elif prev_ma20 <= prev_ma60 and ma20 > ma60:

        if rsi < 30:
            signal = "🔥 STRONG BUY"
        else:
            signal = "🟢 BUY"

    # 데드크로스 + RSI
    elif prev_ma20 >= prev_ma60 and ma20 < ma60:

        if rsi > 70:
            signal = "🚨 STRONG SELL"
        else:
            signal = "🔴 SELL"

    else:

        signal = "⚪ HOLD"

    # 이전 저장 신호 확인
    cur.execute("""
        SELECT signal
        FROM trading_records
        ORDER BY id DESC
        LIMIT 1
    """)

    last = cur.fetchone()

    # 같은 신호는 저장하지 않음
    if last is None or last["signal"] != signal:

        cur.execute("""
            INSERT INTO trading_records
            (signal, price, rsi, ma20, ma60)
            VALUES (%s,%s,%s,%s,%s)
        """,
        (
            signal,
            current,
            rsi,
            ma20,
            ma60
        ))

        conn.commit()

    keep_10000_rows("trading_records")

    cur.close()
    conn.close()

    return render_template(
        "trade_check.html",
        rsi=rsi,
        ma20=ma20,
        ma60=ma60,
        signal=signal
    )
# =====================================
# Trading Records
# =====================================

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
@app.route("/chart")
def chart():
    return render_template("chart.html")

@app.route("/chart-data")
def chart_data():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT id,
               price,
               created_at
        FROM eth_price
        ORDER BY id ASC
        LIMIT 100
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    labels = []
    prices = []

    for r in rows:

        labels.append(
            r["created_at"].strftime("%H:%M:%S")
        )

        prices.append(
            float(r["price"])
        )

    # -----------------------------
    # RSI
    # -----------------------------
    rsi = calculate_rsi()

    # -----------------------------
    # 이동평균
    # -----------------------------
    ma20 = calculate_ma(20)
    ma60 = calculate_ma(60)

    # -----------------------------
    # 신호
    # -----------------------------
    signal = "HOLD"

    if rsi is not None and ma20 is not None and ma60 is not None:

        if rsi <= 30 and ma20 > ma60:
            signal = "BUY"

        elif rsi >= 70 and ma20 < ma60:
            signal = "SELL"

        else:
            signal = "HOLD"

    # -----------------------------
    # BUY / SELL 화살표 표시
    # -----------------------------
    buy_points = []
    sell_points = []

    for i in range(len(prices)):

        buy_points.append(None)
        sell_points.append(None)

        if i == 0:
            continue

        if prices[i] > prices[i - 1]:
            buy_points[i] = prices[i]

        elif prices[i] < prices[i - 1]:
            sell_points[i] = prices[i]

    return jsonify({

        "labels": labels,

        "prices": prices,

        "buy": buy_points,

        "sell": sell_points,

        "rsi": rsi,

        "ma20": ma20,

        "ma60": ma60,

        "signal": signal

    })
