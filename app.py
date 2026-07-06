from flask import Flask, render_template, request, jsonify
import os
import threading
import time
import requests

import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# =====================================================
# Binance
# =====================================================

BINANCE_URL = "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT"


# =====================================================
# PostgreSQL
# =====================================================

def get_db():

    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL missing")

    return psycopg2.connect(database_url)
    # =====================================================
# Binance ETH
# =====================================================

def get_eth_price():

    try:

        r = requests.get(BINANCE_URL, timeout=10)

        data = r.json()

        return float(data["price"])

    except Exception as e:

        print("BINANCE ERROR:", e)

        return None
        # =====================================================
# Keep 10000 rows
# =====================================================

def keep_10000_rows(table):

    conn = get_db()

    cur = conn.cursor()

    cur.execute(f"""

        DELETE FROM {table}

        WHERE id IN (

            SELECT id

            FROM {table}

            ORDER BY id DESC

            OFFSET 10000

        )

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

            price = get_eth_price()

            if price is not None:

                conn = get_db()

                cur = conn.cursor()

                cur.execute("""

                    INSERT INTO eth_price(price)

                    VALUES(%s)

                """, (price,))

                conn.commit()

                cur.close()

                conn.close()

                keep_10000_rows("eth_price")

                print("ETH Saved:", price)

     except Exception as e:

            print("AUTO SAVE ERROR:", e)

        time.sleep(600)
        
    try:

    init_db()

    insert_test_data()

    threading.Thread(
        target=auto_save_eth,
        daemon=True
    ).start()

    except Exception as e:

    print("DATABASE ERROR:", e)
        
