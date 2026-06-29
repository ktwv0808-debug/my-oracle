from flask import Flask, render_template, jsonify
import requests
import psycopg2
import os
from datetime import datetime


app = Flask(__name__)


# =========================
# PostgreSQL
# =========================

def get_db():

    return psycopg2.connect(
        os.environ["DATABASE_URL"]
    )




def init_db():

    conn=get_db()

    cur=conn.cursor()


    cur.execute("""
    CREATE TABLE IF NOT EXISTS prices(

        id SERIAL PRIMARY KEY,
        symbol TEXT,
        price REAL,
        source TEXT,
        created TIMESTAMP

    )
    """)



    cur.execute("""
    CREATE TABLE IF NOT EXISTS trades(

        id SERIAL PRIMARY KEY,
        symbol TEXT,
        action TEXT,
        price REAL,
        created TIMESTAMP

    )
    """)



    conn.commit()

    conn.close()


    print(
    "PostgreSQL database initialized successfully"
    )



init_db()



# =========================
# Home
# =========================


@app.route("/")
def home():

    return render_template(
        "donation.html"
    )



# =========================
# Donation
# =========================


@app.route("/donation")
def donation():

    return render_template(
        "donation.html"
    )





# =========================
# Trading main popup
# =========================


@app.route("/trading")
def trading():

    return render_template(
        "trading.html"
    )





# =========================
# ETH API
# =========================


def get_eth_price():

    url="https://api.coinbase.com/v2/prices/ETH-USD/spot"


    r=requests.get(
        url,
        timeout=10
    )


    data=r.json()


    return float(
        data["data"]["amount"]
    )





# =========================
# ETH Price popup
# =========================


@app.route("/price-page")
def price_page():

    price=get_eth_price()


    return render_template(

        "price.html",

        price=price

    )






# =========================
# Save price popup
# =========================


@app.route("/save-price-page")
def save_price_page():


    price=get_eth_price()


    conn=get_db()

    cur=conn.cursor()



    cur.execute("""
    INSERT INTO prices
    (symbol,price,source,created)

    VALUES(%s,%s,%s,%s)

    """,

    (

    "ETH",

    price,

    "Coinbase",

    datetime.now()

    ))



    conn.commit()

    conn.close()



    return render_template(

        "save_price.html",

        price=price

    )





# =========================
# History popup
# =========================


@app.route("/history-page")
def history_page():


    conn=get_db()

    cur=conn.cursor()



    cur.execute("""
    SELECT *

    FROM prices

    ORDER BY id DESC

    """)



    rows=cur.fetchall()



    conn.close()



    return render_template(

        "history.html",

        prices=rows

    )







# =========================
# Trade signal popup
# =========================


@app.route("/trade-check-page")
def trade_check_page():


    price=get_eth_price()


    signal="HOLD"


    if price < 1700:

        signal="BUY"



    elif price > 2000:

        signal="SELL"




    conn=get_db()

    cur=conn.cursor()



    cur.execute("""
    INSERT INTO trades

    (symbol,action,price,created)

    VALUES(%s,%s,%s,%s)

    """,

    (

    "ETH",

    signal,

    price,

    datetime.now()

    ))



    conn.commit()

    conn.close()



    return render_template(

        "trade_check.html",

        price=price,

        signal=signal

    )






# =========================
# Trade records popup
# =========================


@app.route("/trades-page")
def trades_page():


    conn=get_db()

    cur=conn.cursor()



    cur.execute("""
    SELECT *

    FROM trades

    ORDER BY id DESC

    """)



    rows=cur.fetchall()



    conn.close()



    return render_template(

        "trades.html",

        trades=rows

    )






# =========================
# API JSON
# =========================


@app.route("/price")
def price():

    return jsonify({

        "ETH":

        get_eth_price()

    })






@app.route("/save-price")
def save_price():

    return jsonify({

        "status":"use popup"

    })






@app.route("/history")
def history():

    return jsonify({

        "status":"use popup"

    })






@app.route("/trade-check")
def trade_check():

    return jsonify({

        "status":"use popup"

    })






@app.route("/trades")
def trades():

    return jsonify({

        "status":"use popup"

    })







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






if __name__=="__main__":


    app.run(

        host="0.0.0.0",

        port=5000

    )
