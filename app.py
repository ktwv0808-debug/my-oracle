from flask import Flask, render_template, request, jsonify
import os
import threading
import time
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


# =====================================================
# Binance
# =====================================================

BINANCE_URL = "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT"


def get_eth_price():

    try:

        r = requests.get(
            BINANCE_URL,
            timeout=10
        )

        data = r.json()

        if "price" in data:
            return float(data["price"])

        print(data)

        return None

    except Exception as e:

        print("BINANCE ERROR:", e)

        return None


# =====================================================
# Keep latest 10000 rows
# =====================================================

def keep_10000_rows(table):

    conn = get_db()

    cur = conn.cursor()

    cur.execute(f"""
        DELETE FROM {table}
        WHERE id IN (
            SELECT id
            FROM {table}
            ORDER BY id ASC
            OFFSET 10000
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
# =====================================
# Render 시작 시 초기화
# =====================================

try:
    init_db()
    insert_test_data()

    threading.Thread(
        target=auto_save_eth,
        daemon=True
    ).start()

    print("System Started")

except Exception as e:
    print("INIT ERROR:", e)


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
# ETH Price
# =====================================

@app.route("/price")
def price():

    live_price = get_eth_price()

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
            INSERT INTO eth_price(price)
            VALUES(%s)
        """, (price,))

        conn.commit()

        message = "Saved Successfully"

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

    cur.execute("""
        SELECT price
        FROM eth_price
        ORDER BY id DESC
        LIMIT 2
    """)

    rows = cur.fetchall()

    signal = "WAIT"

    current = 0

    if len(rows) >= 2:

        current = float(rows[0]["price"])

        previous = float(rows[1]["price"])

        if current > previous:
            signal = "BUY SIGNAL"

        elif current < previous:
            signal = "SELL SIGNAL"

    cur.execute("""
        INSERT INTO trading_records(signal, price)
        VALUES(%s,%s)
    """, (signal, current))

    conn.commit()

    keep_10000_rows("trading_records")

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
        "trade_check.html",
        signal=signal,
        records=records
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
        LIMIT 500
    """)

    records = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "trades.html",
        records=records
    )    
