from flask import Flask, render_template, request, jsonify
import os
import psycopg2
from psycopg2.extras import RealDictCursor


app = Flask(__name__)


# =====================================
# Cloud PostgreSQL Connection
# =====================================

def get_db():

    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise Exception(
            "DATABASE_URL is missing"
        )

    return psycopg2.connect(
        database_url
    )



# =====================================
# Create Database Tables
# =====================================

def init_db():

    conn = get_db()

    cur = conn.cursor()


    cur.execute("""
    
    CREATE TABLE IF NOT EXISTS eth_price (

        id SERIAL PRIMARY KEY,

        price NUMERIC(18,6),

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    );

    """)



    cur.execute("""
    
    CREATE TABLE IF NOT EXISTS trading_records (

        id SERIAL PRIMARY KEY,

        signal TEXT,

        price NUMERIC(18,6),

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    );

    """)



    conn.commit()

    cur.close()

    conn.close()



# =====================================
# Main Homepage
# =====================================

@app.route("/")
def home():

    return render_template(
        "donation.html"
    )


# =====================================
# Automatic Trading System
# =====================================

@app.route("/trading")
def trading():

    return render_template(
        "trading.html"
    )



# =====================================
# ETH Price Popup
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


    data = cur.fetchone()



    cur.close()

    conn.close()



    return render_template(

        "price.html",

        price=data

    )



# =====================================
# Save ETH Price
# =====================================

@app.route(
    "/save-price",
    methods=["GET","POST"]
)

def save_price():


    message=""


    if request.method=="POST":


        price=request.form.get(
            "price"
        )


        conn=get_db()


        cur=conn.cursor()



        cur.execute("""
        
        INSERT INTO eth_price(price)

        VALUES(%s)

        """,

        (
            price,
        ))



        conn.commit()



        message="ETH Price Saved Successfully"



        cur.close()

        conn.close()



    return render_template(

        "save_price.html",

        message=message

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

    current_price=0



    if len(rows)>=2:


        current_price=float(
            rows[0]["price"]
        )


        old_price=float(
            rows[1]["price"]
        )



        if current_price > old_price:

            signal="BUY SIGNAL"



        elif current_price < old_price:

            signal="SELL SIGNAL"




    cur.execute("""
    
    INSERT INTO trading_records
    (signal,price)

    VALUES(%s,%s)

    """,

    (

        signal,

        current_price

    ))



    conn.commit()


    cur.close()

    conn.close()



    return render_template(

        "trade_check.html",

        signal=signal

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
# API Price
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
# Render Start
# =====================================

if __name__=="__main__":


    init_db()


    app.run(
        host="0.0.0.0",
        port=5000
    )
