from flask import Flask, render_template, request, jsonify

import os
import psycopg2
from psycopg2.extras import RealDictCursor

import requests
import threading
import time

from datetime import datetime
app = Flask(__name__)


# =====================================
# PostgreSQL Cloud 연결
# =====================================

def get_db():

    database_url = os.environ.get(
        "DATABASE_URL"
    )

    if not database_url:
        raise Exception(
            "DATABASE_URL missing"
        )

    return psycopg2.connect(
        database_url
    )
# =====================================
# Binance API
# =====================================

def get_eth_price():

    try:

        url = "https://api.binance.com/api/v3/ticker/24hr?symbol=ETHUSDT"

        r = requests.get(url, timeout=10)

        data = r.json()

        return {

            "price": float(data["lastPrice"]),

            "high": float(data["highPrice"]),

            "low": float(data["lowPrice"]),

            "change": float(data["priceChangePercent"]),

            "volume": float(data["volume"])

        }

    except Exception as e:

        print("BINANCE ERROR:", e)

        return None
# =====================================
# keep latest 10000 rows
# =====================================

def keep_10000_rows(table):

    conn=get_db()

    cur=conn.cursor()

    cur.execute(f"""

    DELETE FROM {table}

    WHERE id IN(

        SELECT id

        FROM {table}

        ORDER BY id DESC

        OFFSET 10000

    )

    """)

    conn.commit()

    cur.close()

    conn.close()   
# =====================================
# Auto Save ETH
# =====================================

def auto_save_eth():

    while True:

        try:

            live = get_eth_price()

            if live is not None:

                price = live["price"]

                conn = get_db()

                cur = conn.cursor()

                cur.execute("""

                INSERT INTO eth_price(price)

                VALUES(%s)

                """,

                (

                    price,

                ))

                conn.commit()

                cur.close()

                conn.close()

                keep_10000_rows("eth_price")

                print(

                    f"[AUTO SAVE] {price} USD"

                )

        except Exception as e:

            print(

                "AUTO SAVE ERROR:",

                e

            )

        time.sleep(600)
# =====================================
# DB 테이블 생성
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



    # Donation 기록

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
# 테스트 데이터 생성
# =====================================

def insert_test_data():

    conn=get_db()

    cur=conn.cursor()



    # ETH

    cur.execute("""
    SELECT COUNT(*)
    FROM eth_price
    """)


    if cur.fetchone()[0] == 0:


        cur.execute("""
        INSERT INTO eth_price(price)

        VALUES

        (1578.325),

        (1585.500),

        (1602.750)

        """)




    # Trading

    cur.execute("""
    SELECT COUNT(*)
    FROM trading_records
    """)


    if cur.fetchone()[0] == 0:


        cur.execute("""
        INSERT INTO trading_records
        (signal,price)

        VALUES

        ('BUY SIGNAL',1578.325),

        ('SELL SIGNAL',1585.500),

        ('BUY SIGNAL',1602.750)

        """)




    # Donation

    cur.execute("""
    SELECT COUNT(*)
    FROM donation_records
    """)


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

# =====================================
# Background Thread
# =====================================

threading.Thread(
    target=auto_save_eth,
    daemon=True
).start()


# =====================================
# 메인 홈페이지
# =====================================

@app.route("/")
def home():


    conn=get_db()


    cur=conn.cursor(

        cursor_factory=RealDictCursor

    )


    cur.execute("""
    SELECT *

    FROM donation_records

    ORDER BY id

    """)



    donations=cur.fetchall()



    cur.close()

    conn.close()



    return render_template(

        "donation.html",

        donations=donations

    )




# =====================================
# 자동매매 시스템
# =====================================

@app.route("/trading")
def trading():

    return render_template(
        "trading.html"
    )




# =====================================
# ETH Price
# =====================================

@app.route("/price")
def price():

    conn = get_db()

    cur = conn.cursor(
        cursor_factory=RealDictCursor
    )

    cur.execute("""

    SELECT *

    FROM eth_price

    ORDER BY id DESC

    LIMIT 1

    """)

    db_price = cur.fetchone()

    cur.close()

    conn.close()

    live = get_eth_price()

    return render_template(

        "price.html",

        price=db_price,

        live=live

    )

# =====================================
# Save ETH Price
# =====================================

@app.route(
    "/save-price",
    methods=["GET", "POST"]
)
def save_price():

    message = ""

    conn = get_db()

    cur = conn.cursor(

        cursor_factory=RealDictCursor

    )

    if request.method == "POST":

        live = get_eth_price()

        if live:

            price = live["price"]

            cur.execute("""

            INSERT INTO eth_price(price)

            VALUES(%s)

            """,

            (

                price,

            ))

            conn.commit()

            keep_10000_rows(

                "eth_price"

            )

            message = "ETH Price Saved Successfully"

    cur.execute("""

    SELECT *

    FROM eth_price

    ORDER BY id DESC

    LIMIT 100

    """)

    prices = cur.fetchall()

    cur.close()

    conn.close()

    live = get_eth_price()

  return render_template(

        "save_price.html",

        message=message,

        prices=prices,

        live=live

    )

# =====================================
# Price History
# =====================================

@app.route("/history")
def history():

    conn=get_db()


    cur=conn.cursor(
        cursor_factory=RealDictCursor
    )


    cur.execute("""
    
    SELECT *

    FROM eth_price

    ORDER BY id DESC

    LIMIT 100

    """)


    prices=cur.fetchall()



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

    conn=get_db()

    cur=conn.cursor(
        cursor_factory=RealDictCursor
    )


    cur.execute("""
    
    SELECT price

    FROM eth_price

    ORDER BY id DESC

    LIMIT 2

    """)


    rows=cur.fetchall()


    signal="WAIT"

    current=0



    if len(rows)>=2:


        current=float(
            rows[0]["price"]
        )


        before=float(
            rows[1]["price"]
        )


        if current > before:

            signal="BUY SIGNAL"


        elif current < before:

            signal="SELL SIGNAL"




    cur.execute("""
    
    INSERT INTO trading_records
    (signal,price)

    VALUES(%s,%s)

    """,

    (
        signal,
        current
    ))


    conn.commit()



    cur.execute("""
    
    SELECT *

    FROM trading_records

    ORDER BY id DESC

    LIMIT 100

    """)


    records=cur.fetchall()



    cur.close()

    conn.close()



    live = get_eth_price()

return render_template(

    "trade_check.html",

    signal=signal,

    records=records,

    live=live

)

# =====================================
# Trading Records
# =====================================

@app.route("/trades")
def trades():


    conn=get_db()


    cur=conn.cursor(

        cursor_factory=RealDictCursor

    )


    cur.execute("""
    
    SELECT *

    FROM trading_records

    ORDER BY id DESC

    LIMIT 100

    """)



    records=cur.fetchall()



    cur.close()

    conn.close()



    return render_template(

        "trades.html",

        records=records

    )


# =====================================
# Whitepaper
# =====================================

@app.route("/whitepaper")
def whitepaper():

    return render_template(
        "whitepaper.html"
    )




# =====================================
# Poem
# =====================================

@app.route("/poem")
def poem():

    return render_template(
        "poem.html"
    )




# =====================================
# API
# =====================================

@app.route("/api/price")
def api_price():


    conn=get_db()


    cur=conn.cursor(

        cursor_factory=RealDictCursor

    )


    cur.execute("""
    SELECT price

    FROM eth_price

    ORDER BY id DESC

    LIMIT 1

    """)



    data=cur.fetchone()



    cur.close()

    conn.close()



    return jsonify(data)




# =====================================
# Render 시작 시 실행
# =====================================

try:

    init_db()

    insert_test_data()


except Exception as e:

    print(
        "DATABASE ERROR:",
        e
    )




if __name__=="__main__":

    app.run(

        host="0.0.0.0",

        port=5000

    )
