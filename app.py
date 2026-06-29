from flask import Flask, render_template, jsonify
import os
import psycopg2
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


    print("PostgreSQL database initialized successfully")





# =========================
# 메인 홈페이지
# =========================

@app.route("/")
def home():

    return render_template(
        "donation.html"
    )





# =========================
# 자동매매 시스템 팝업
# =========================

@app.route("/trading")
def trading():

    return render_template(
        "trading.html"
    )






# =========================
# ETH Price 팝업
# =========================

@app.route("/price")
def price():


    eth_price = 1578.325


    return render_template(

        "price.html",

        price=eth_price

    )






# =========================
# ETH 가격 저장
# =========================

@app.route("/save-price")
def save_price():


    eth_price = 1578.325


    conn=get_db()

    cur=conn.cursor()



    cur.execute(

    """

    INSERT INTO price_history

    (eth_price,created_at)

    VALUES(%s,%s)

    """,

    (

    eth_price,

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
# 가격 기록
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


    data=cur.fetchall()



    cur.close()

    conn.close()



    return render_template(

        "history.html",

        history=data

    )







# =========================
# 자동거래 신호
# =========================

@app.route("/trade-check")
def trade_check():


    signal="BUY SIGNAL"



    return render_template(

        "trade_check.html",

        signal=signal

    )







# =========================
# 거래 기록
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


    records=cur.fetchall()



    cur.close()

    conn.close()



    return render_template(

        "trades.html",

        trades=records

    )








# =========================
# 테스트 API
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
