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

    conn.close# =====================================================
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
    
        
