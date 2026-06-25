from flask import Flask, jsonify, render_template
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
# 데이터베이스 초기화
# =========================

def init_db():

    conn = get_db()

    cursor = conn.cursor()


    # 가격 기록

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prices(

        id SERIAL PRIMARY KEY,

        symbol TEXT,

        price REAL,

        source TEXT,

        created TIMESTAMP

    )
    """)



    # 거래 기록

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


    print("PostgreSQL initialized")



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
    PostgreSQL Blockchain Price Oracle System
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
# ETH 가격 조회
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



        conn=get_db()

        cursor=conn.cursor()



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

            "price":eth


        })



    except Exception as e:


        return jsonify({

            "error":str(e)

        })







# =========================
# 가격 기록
# =========================

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




    except Exception as e:


        return jsonify({

            "error":str(e)

        })








# =========================
# 거래 기록
# =========================

@app.route("/trades")
def trades():


    conn=get_db()

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
# 실행
# =========================

if __name__=="__main__":


    app.run(

        host="0.0.0.0",

        port=5000

    )
