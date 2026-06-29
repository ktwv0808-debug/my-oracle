  1from flask import Flask, jsonify, render_template
import requests
import psycopg2
import os
from datetime import datetime


app = Flask(__name__)



# =========================
# PostgreSQL 연결
# =========================


def get_db():

    return psycopg2.connect(
        os.environ["DATABASE_URL"]
    )





# =========================
# DB 초기화
# =========================


def init_db():

    conn = get_db()

    cursor = conn.cursor()



    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prices(

        id SERIAL PRIMARY KEY,

        symbol TEXT,

        price REAL,

        source TEXT,

        created TIMESTAMP

    )
    """)



    cursor.execute("""
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


    print("PostgreSQL database initialized successfully")




init_db()





# =========================
# 메인
# =========================


@app.route("/")
def home():

    return """

    <h1>
    W-donation Oracle Server Running
    </h1>


    <p>
    Blockchain With Social Responsibility
    </p>

    """






# =========================
# 홈페이지
# =========================


@app.route("/donation")
def donation():

    return render_template(
        "donation.html"
    )






# =========================
# ETH 가격 API
# =========================


def get_eth_price():


    url = (

    "https://api.coinbase.com/v2/prices/ETH-USD/spot"

    )


    r = requests.get(

        url,

        timeout=10

    )


    data = r.json()


    return float(

        data["data"]["amount"]

    )







# =========================
# ETH Price 팝업
# =========================


@app.route("/price-page")
def price_page():

    return render_template(
        "price.html"
    )





@app.route("/price")
def price():

    eth = get_eth_price()


    return jsonify({

        "symbol":"ETH",

        "price_usd":eth,

        "source":"Coinbase"

    })








# =========================
# 저장 팝업
# =========================


@app.route("/save-price-page")
def save_price_page():

    return render_template(
        "save_price.html"
    )






@app.route("/save-price")
def save_price():


    eth = get_eth_price()


    conn = get_db()

    cursor = conn.cursor()



    cursor.execute("""


    INSERT INTO prices

    (symbol,price,source,created)

    VALUES(%s,%s,%s,%s)


    """,

    (

    "ETH",

    eth,

    "Coinbase",

    datetime.now()

    ))



    conn.commit()

    conn.close()



    return jsonify({

        "saved":True,

        "symbol":"ETH",

        "price":eth,

        "database":"PostgreSQL"

    })









# =========================
# 가격 기록
# =========================



@app.route("/history-page")
def history_page():

    return render_template(
        "history.html"
    )






@app.route("/history")
def history():


    conn=get_db()

    cursor=conn.cursor()



    cursor.execute("""

    SELECT *

    FROM prices

    ORDER BY id DESC


    """)


    rows=cursor.fetchall()



    conn.close()



    return jsonify(rows)









# =========================
# 자동매매 신호
# =========================


@app.route("/trade-check-page")
def trade_check_page():

    return render_template(
        "trade_check.html"
    )








@app.route("/trade-check")
def trade_check():


    eth=get_eth_price()


    action="HOLD"



    if eth < 1700:


        action="BUY"



    elif eth > 2000:


        action="SELL"






    conn=get_db()

    cursor=conn.cursor()



    cursor.execute("""


    INSERT INTO trades

    (symbol,action,price,created)

    VALUES(%s,%s,%s,%s)


    """,

    (

    "ETH",

    action,

    eth,

    datetime.now()

    ))



    conn.commit()

    conn.close()




    return jsonify({

        "symbol":"ETH",

        "price":eth,

        "signal":action,

        "mode":"simulation"

    })









# =========================
# 거래 기록
# =========================



@app.route("/trades-page")
def trades_page():

    return render_template(
        "trades.html"
    )







@app.route("/trades")
def trades():


    conn=get_db()

    cursor=conn.cursor()



    cursor.execute("""

    SELECT *

    FROM trades

    ORDER BY id DESC


    """)



    rows=cursor.fetchall()


    conn.close()


    return jsonify(rows)









# =========================
# 자동매매 시스템 팝업
# =========================


@app.route("/trading")
def trading():

    return render_template(
        "trading.html"
    )






# =========================
# 백서 팝업
# =========================


@app.route("/whitepaper")
def whitepaper():

    return render_template(
        "whitepaper.html"
    )





# =========================
# 시 팝업
# =========================


@app.route("/poem")
def poem():

    return render_template(
        "poem.html"
    )







# =========================
# Render 실행
# =========================


if __name__ == "__main__":


    app.run(

        host="0.0.0.0",

        port=5000

    )
  2
  3
  4
  5
  6
  7
  8
  9
 10
 11
 12
 13
 14
 15
