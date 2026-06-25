from flask import Flask, jsonify, render_template
import requests
import sqlite3
from datetime import datetime


app = Flask(__name__)


DB = "price.db"



# =========================
# SQLite 초기화
# =========================

def init_db():

    conn = sqlite3.connect(DB)

    cursor = conn.cursor()


    # 가격 저장 테이블

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prices(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        symbol TEXT,

        price REAL,

        source TEXT,

        created TEXT

    )
    """)



    # 거래 기록 테이블

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trades(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        symbol TEXT,

        action TEXT,

        price REAL,

        created TEXT

    )
    """)



    conn.commit()

    conn.close()


    print("SQLite price.db initialized successfully")


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

    Blockchain Price Oracle System

    </p>

    """





# =========================
# Donation 홈페이지
# =========================

@app.route("/donation")
def donation():


    return render_template(
        "donation.html"
    )







# =========================
# Coinbase ETH 가격
# =========================

def get_eth_price():


    url = (
    "https://api.coinbase.com/v2/prices/ETH-USD/spot"
    )


    response = requests.get(
        url,
        timeout=10
    )


    data=response.json()


    price=float(
        data["data"]["amount"]
    )


    return price







# =========================
# ETH 가격 API
# =========================

@app.route("/price")
def price():


    try:


        eth=get_eth_price()



        return jsonify({

            "symbol":"ETH",

            "price_usd":eth,

            "source":"Coinbase"

        })



    except Exception as e:


        return jsonify({

            "error":str(e)

        })







# =========================
# 가격 저장
# =========================

@app.route("/save-price")
def save_price():


    try:


        eth=get_eth_price()



        conn=sqlite3.connect(DB)

        cursor=conn.cursor()



        cursor.execute("""
        INSERT INTO prices

        (symbol,price,source,created)

        VALUES(?,?,?,?)

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

        "price":eth


        })



    except Exception as e:


        return jsonify({

            "error":str(e)

        })







# =========================
# 가격 기록 조회
# =========================

@app.route("/history")
def history():


    conn=sqlite3.connect(DB)

    cursor=conn.cursor()



    cursor.execute(
        """
        SELECT *
        FROM prices
        ORDER BY id DESC
        """
    )


    rows=cursor.fetchall()


    conn.close()



    return jsonify(rows)







# =========================
# W-donation 테스트 가격
# =========================

@app.route("/ktw-price")
def ktw_price():


    return jsonify({


        "symbol":"W-donation",

        "price_usd":"0.0001",

        "source":"Oracle Test Price"


    })








# =========================
# 자동매매 시뮬레이션
# =========================

@app.route("/trade-check")
def trade_check():


    try:


        eth=get_eth_price()



        action="HOLD"



        # 테스트 전략

        if eth < 1700:


            action="BUY"



        elif eth > 2000:


            action="SELL"






        conn=sqlite3.connect(DB)

        cursor=conn.cursor()



        cursor.execute("""

        INSERT INTO trades

        (symbol,action,price,created)

        VALUES(?,?,?,?)

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



    except Exception as e:


        return jsonify({

            "error":str(e)

        })








# =========================
# 거래 기록
# =========================

@app.route("/trades")
def trades():


    conn=sqlite3.connect(DB)

    cursor=conn.cursor()



    cursor.execute("""

    SELECT *

    FROM trades

    ORDER BY id DESC


    """)


    data=cursor.fetchall()



    conn.close()



    return jsonify(data)









# =========================
# Render 실행
# =========================

if __name__=="__main__":


    app.run(

        host="0.0.0.0",

        port=5000

    )
