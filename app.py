from flask import Flask, render_template, jsonify
import os
import psycopg2
from datetime import datetime


app = Flask(__name__)



# =========================
# PostgreSQL
# =========================

def get_db():

    return psycopg2.connect(
        os.environ["DATABASE_URL"]
    )



# =========================
# Database Init
# =========================

def init_db():

    conn = get_db()

    cur = conn.cursor()


    cur.execute("""
    CREATE TABLE IF NOT EXISTS price_history(

        id SERIAL PRIMARY KEY,

        eth_price FLOAT,

        created_at TIMESTAMP

    )
    """)


    cur.execute("""
    CREATE TABLE IF NOT EXISTS trades(

        id SERIAL PRIMARY KEY,

        action TEXT,

        price FLOAT,

        created_at TIMESTAMP

    )
    """)


    conn.commit()

    cur.close()

    conn.close()


    print("Database initialized")





# =========================
# MAIN HOMEPAGE
# =========================

@app.route("/")
def donation():

    return render_template(
        "donation.html"
    )





# =========================
# Trading Popup
# =========================

@app.route("/trading")
def trading():

    return render_template(
        "trading.html"
    )





# =========================
# ETH PRICE
# =========================

@app.route("/price")
def price():

    return render_template(

        "price.html",

        price=1578.325

    )





# =========================
# SAVE PRICE
# =========================

@app.route("/save-price")
def save_price():


    conn=get_db()

    cur=conn.cursor()


    cur.execute(

    """

    INSERT INTO price_history

    (eth_price,created_at)

    VALUES(%s,%s)

    """,

    (

    1578.325,

    datetime.now()

    )

    )


    conn.commit()


    cur.close()

    conn.close()



    return render_template(

        "save_price.html"

    )





# =========================
# HISTORY
# =========================

@app.route("/history")
def history():


    conn=get_db()

    cur=conn.cursor()



    cur.execute(

    """

    SELECT eth_price,created_at

    FROM price_history

    ORDER BY id DESC

    """

    )



    rows=cur.fetchall()



    cur.close()

    conn.close()



    return render_template(

        "history.html",

        history=rows

    )





# =========================
# TRADE SIGNAL
# =========================

@app.route("/trade-check")
def trade_check():


    return render_template(

        "trade_check.html",

        signal="BUY SIGNAL"

    )






# =========================
# TRADING RECORD
# =========================

@app.route("/trades")
def trades():


    conn=get_db()

    cur=conn.cursor()



    cur.execute(

    """

    SELECT action,price,created_at

    FROM trades

    ORDER BY id DESC

    """

    )


    rows=cur.fetchall()



    cur.close()

    conn.close()



    return render_template(

        "trades.html",

        trades=rows

    )





# =========================
# Whitepaper
# =========================

@app.route("/whitepaper")
def whitepaper():

    return render_template(

        "whitepaper.html"

    )





# =========================
# Poem
# =========================

@app.route("/poem")
def poem():

    return render_template(

        "poem.html"

    )





# =========================
# TEST API
# =========================

@app.route("/api/price")
def api_price():

    return jsonify({

        "ETH":1578.325

    })





if __name__=="__main__":


    init_db()


    app.run(

        host="0.0.0.0",

        port=5000

    )
