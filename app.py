from flask import Flask, render_template, request, jsonify
import os
import psycopg2
from psycopg2.extras import RealDictCursor


app = Flask(__name__)


# =====================================
# Cloud PostgreSQL 연결
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
# DB 테이블 생성
# =====================================

def init_db():

    conn = get_db()

    cur = conn.cursor()



    cur.execute("""
    
    CREATE TABLE IF NOT EXISTS eth_price(

        id SERIAL PRIMARY KEY,

        price NUMERIC(18,6),

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    );

    """)



    cur.execute("""
    
    CREATE TABLE IF NOT EXISTS trading_records(

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
# 메인 홈페이지
# =====================================

@app.route("/")
def home():

    return render_template(
        "donation.html"
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
# ETH 가격
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
# ETH 가격 저장
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
# 가격 기록
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
# 자동 거래 신호
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

    price=0



    if len(rows)>=2:


        now=float(
            rows[0]["price"]
        )


        before=float(
            rows[1]["price"]
        )



        price=now



        if now > before:

            signal="BUY SIGNAL"



        elif now < before:

            signal="SELL SIGNAL"




    cur.execute("""
    
    INSERT INTO trading_records
    (signal,price)

    VALUES(%s,%s)

    """,

    (

        signal,

        price

    ))



    conn.commit()



    cur.close()

    conn.close()



    return render_template(

        "trade_check.html",

        signal=signal

    )



# =====================================
# 거래 기록
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
# 백서
# =====================================

@app.route("/whitepaper")
def whitepaper():

    return render_template(
        "whitepaper.html"
    )



# =====================================
# 시
# =====================================

@app.route("/poem")
def poem():

    return render_template(
        "poem.html"
    )



# =====================================
# API ETH 가격
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
# Render 배포용 DB 초기화
# =====================================

try:

    init_db()


except Exception as e:

    print(
        "Database init error:",
        e
    )




# =====================================
# 실행
# =====================================

if __name__=="__main__":


    app.run(

        host="0.0.0.0",

        port=5000

    )
