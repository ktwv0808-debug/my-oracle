# ==========================================================
# Part 1
# Import / Flask / PostgreSQL / 기본설정
# ==========================================================

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    jsonify,
    url_for
)

import psycopg2
from psycopg2.extras import RealDictCursor

import requests

import pandas as pd
import numpy as np

from datetime import datetime

import os



# ==========================================================
# Flask
# ==========================================================

app = Flask(__name__)

app.secret_key = "worldvision"



# ==========================================================
# PostgreSQL
# (Render Free PostgreSQL)
# ==========================================================

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_db():

    conn = psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )

    return conn



print("✅ PostgreSQL Connected")



# ==========================================================
# Binance API
# ==========================================================

BINANCE_URL = "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT"



# ==========================================================
# 기본 투자금
# ==========================================================

START_CASH = 100000



# ==========================================================
# 프로그램 시작
# ==========================================================

print("======================================")
print(" World Vision Trading System")
print(" Flask + PostgreSQL")
print("======================================")

# ==========================================================
# Part 2
# ETH Live Price
# ==========================================================

# -----------------------------
# Binance에서 현재 ETH 가격 가져오기
# -----------------------------
def get_eth_price():

    try:

        response = requests.get(BINANCE_URL, timeout=10)

        data = response.json()

        return float(data["price"])

    except Exception as e:

        print("ETH Price Error :", e)

        return 0


# -----------------------------
# ETH 현재 가격(JSON API)
# -----------------------------
@app.route("/live-price")
def live_price():

    return jsonify({

        "price": get_eth_price()

    })



# ==========================================================
# Part 3
# Price History / RSI / Moving Average
# ==========================================================

# ----------------------------------------------------------
# 최근 ETH 가격 가져오기(DataFrame)
# ----------------------------------------------------------
def get_price_dataframe(limit=200):

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            price,
            created_at
        FROM eth_price
        ORDER BY id DESC
        LIMIT %s
    """, (limit,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    if len(rows) == 0:

        return pd.DataFrame(columns=["price", "created_at"])

    df = pd.DataFrame(rows)

    # 오래된 데이터 → 최신 데이터 순으로 정렬
    df = df.iloc[::-1].reset_index(drop=True)

    df["price"] = df["price"].astype(float)

    return df


# ----------------------------------------------------------
# MA 계산
# ----------------------------------------------------------
def calculate_ma(period):

    df = get_price_dataframe()

    if len(df) < period:

        return None

    ma = df["price"].rolling(period).mean()

    return round(float(ma.iloc[-1]), 2)


# ----------------------------------------------------------
# 이전 MA 계산
# 골든크로스 / 데드크로스 확인용
# ----------------------------------------------------------
def calculate_previous_ma(period):

    df = get_price_dataframe()

    if len(df) < period + 1:

        return None

    ma = df["price"].rolling(period).mean()

    return round(float(ma.iloc[-2]), 2)


# ----------------------------------------------------------
# RSI 계산
# ----------------------------------------------------------
def calculate_rsi(period=14):

    df = get_price_dataframe()

    if len(df) < period + 1:

        return None

    delta = df["price"].diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()

    avg_loss = loss.rolling(period).mean()

    if avg_loss.iloc[-1] == 0:

        return 100

    rs = avg_gain.iloc[-1] / avg_loss.iloc[-1]

    rsi = 100 - (100 / (1 + rs))

    return round(float(rsi), 2)

# ==========================================================
# Part 4
# Trading Signal
# ==========================================================

def generate_signal():

    rsi = calculate_rsi()

    ma20 = calculate_ma(20)
    ma60 = calculate_ma(60)

    prev20 = calculate_previous_ma(20)
    prev60 = calculate_previous_ma(60)

    signal = "HOLD"

    golden = False
    dead = False

    # -----------------------------
    # 데이터 부족
    # -----------------------------
    if None in (rsi, ma20, ma60, prev20, prev60):

        signal = "HOLD"

    else:

        # =====================================
        # GOLDEN CROSS
        # =====================================
        if prev20 <= prev60 and ma20 > ma60:

            golden = True

            if rsi <= 70:
                signal = "BUY"
            else:
                signal = "HOLD"

        # =====================================
        # DEAD CROSS
        # =====================================
        elif prev20 >= prev60 and ma20 < ma60:

            dead = True

            if rsi >= 30:
                signal = "SELL"
            else:
                signal = "HOLD"

        else:

            # RSI만 이용한 보조신호

            if rsi <= 30:
                signal = "BUY"

            elif rsi >= 70:
                signal = "SELL"

            else:
                signal = "HOLD"

    return {

        "signal": signal,

        "golden": golden,

        "dead": dead,

        "rsi": rsi,

        "ma20": ma20,

        "ma60": ma60

    }


# ==========================================================
# Trading Signal Page
# ==========================================================

@app.route("/trade-check")
def trade_check():

    result = generate_signal()

    return render_template(

        "trade_check.html",

        signal=result["signal"],

        golden=result["golden"],

        dead=result["dead"],

        rsi=result["rsi"],

        ma20=result["ma20"],

        ma60=result["ma60"]

    )

# ==========================================================
# Part 5
# Portfolio
# ==========================================================

# ----------------------------------------------------------
# Portfolio 읽기
# ----------------------------------------------------------
def get_portfolio():

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM portfolio
        WHERE id=1
    """)

    portfolio = cur.fetchone()
    print(portfolio)

    cur.close()
    conn.close()

    return portfolio


# ----------------------------------------------------------
# Portfolio 저장
# ----------------------------------------------------------
def update_portfolio(cash, eth, avg_buy):

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""
        UPDATE portfolio
        SET

            cash=%s,

            eth=%s,

            avg_buy=%s

        WHERE id=1
    """,(cash,eth,avg_buy))

    conn.commit()

    cur.close()
    conn.close()


# ----------------------------------------------------------
# Portfolio 계산
# ----------------------------------------------------------
def calculate_portfolio():

    portfolio = get_portfolio()

    current_price = get_eth_price()

    cash = float(portfolio["cash"])

    eth = float(portfolio["eth"])

    avg_buy = float(portfolio["avg_buy"])

    asset_value = eth * current_price

    total_assets = cash + asset_value

    cost = eth * avg_buy

    profit = asset_value - cost

    roi = 0

    if cost > 0:

        roi = (profit / cost) * 100

    return {

        "cash": round(cash,2),

        "eth": round(eth,8),

        "avg_buy": round(avg_buy,2),

        "current_price": round(current_price,2),

        "asset_value": round(asset_value,2),

        "total_assets": round(total_assets,2),

        "profit": round(profit,2),

        "roi": round(roi,2)

    }


# ----------------------------------------------------------
# Portfolio Page
# ----------------------------------------------------------
@app.route("/portfolio")
def portfolio():

    p = calculate_portfolio()

    return render_template(

        "portfolio.html",

        portfolio=p

    )

# ==========================================================
# Part 6
# Auto Trading Engine
# ==========================================================

# ----------------------------------------------------------
# Trading Record 저장
# ----------------------------------------------------------
def save_trade(signal, price, rsi, ma20, ma60):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO trading_records
        (signal, price, rsi, ma20, ma60)

        VALUES

        (%s,%s,%s,%s,%s)
    """,(signal,price,rsi,ma20,ma60))

    conn.commit()

    cur.close()
    conn.close()


# ----------------------------------------------------------
# BUY
# ----------------------------------------------------------
def execute_buy(price):

    p = get_portfolio()

    cash = float(p["cash"])
    eth = float(p["eth"])
    avg_buy = float(p["avg_buy"])

    # 전액 매수
    if cash <= 0:
        return

    buy_eth = cash / price

    total_cost = (eth * avg_buy) + cash

    eth += buy_eth

    avg_buy = total_cost / eth

    cash = 0

    update_portfolio(cash, eth, avg_buy)


# ----------------------------------------------------------
# SELL
# ----------------------------------------------------------
def execute_sell(price):

    p = get_portfolio()

    cash = float(p["cash"])
    eth = float(p["eth"])
    avg_buy = float(p["avg_buy"])

    if eth <= 0:
        return

    cash += eth * price

    eth = 0

    avg_buy = 0

    update_portfolio(cash, eth, avg_buy)


# ----------------------------------------------------------
# Auto Trading
# ----------------------------------------------------------
@app.route("/auto-trade")
def auto_trade():

    signal = generate_signal()

    current_price = get_eth_price()

    if signal["signal"] == "BUY":

        execute_buy(current_price)

    elif signal["signal"] == "SELL":

        execute_sell(current_price)

    save_trade(

        signal["signal"],

        current_price,

        signal["rsi"],

        signal["ma20"],

        signal["ma60"]

    )

    return redirect("/portfolio")

# ==========================================================
# PART 7
# HTML PAGE ROUTES
# ==========================================================


# ----------------------------------------------------------
# Donation (Main Page)
# URL : /
# ----------------------------------------------------------
@app.route("/")
@app.route("/donation")
def donation():
    return render_template("donation.html")


# ----------------------------------------------------------
# Trading Dashboard
# URL : /trading
# ----------------------------------------------------------
@app.route("/trading")
def trading():
    return render_template("trading.html")


# ----------------------------------------------------------
# Live Price Page
# URL : /price
# ----------------------------------------------------------
@app.route("/price")
def price():
    return render_template("price.html")


# ----------------------------------------------------------
# Price History
# URL : /history
# ----------------------------------------------------------
@app.route("/history")
def history():
    return render_template("history.html")


# ----------------------------------------------------------
# Save ETH Price
# 실제 저장 기능은 PART9에서 구현
# ----------------------------------------------------------
@app.route("/save-price", methods=["GET", "POST"])
def save_price():
    pass


# ----------------------------------------------------------
# Trading Signal
# 실제 기능은 PART9
# ----------------------------------------------------------
@app.route("/trade-check")
def trade_check():
    pass


# ----------------------------------------------------------
# Trading Records
# 실제 기능은 PART9
# ----------------------------------------------------------
@app.route("/trades")
def trades():
    pass


# ----------------------------------------------------------
# Portfolio
# 실제 기능은 PART9
# ----------------------------------------------------------
@app.route("/portfolio")
def portfolio():
    pass


# ----------------------------------------------------------
# Whitepaper
# URL : /whitepaper
# ----------------------------------------------------------
@app.route("/whitepaper")
def whitepaper():
    return render_template("whitepaper.html")


# ----------------------------------------------------------
# Poem
# URL : /poem
# ----------------------------------------------------------
@app.route("/poem")
def poem():
    return render_template("poem.html")


# ----------------------------------------------------------
# Trading Chart
# URL : /chart
# ----------------------------------------------------------
@app.route("/chart")
def chart():
    return render_template("chart.html")

# ==========================================================
# Part8
# Trading Signal + Trading Record
# ==========================================================

def generate_signal():

    rsi = calculate_rsi()
    ma20 = calculate_ma(20)
    ma60 = calculate_ma(60)

    prev20 = calculate_previous_ma(20)
    prev60 = calculate_previous_ma(60)

    signal = "HOLD"

    if None in (rsi, ma20, ma60, prev20, prev60):

        signal = "HOLD"

    else:

        # -----------------------------
        # Golden Cross
        # -----------------------------
        if prev20 <= prev60 and ma20 > ma60:

            signal = "BUY"

        # -----------------------------
        # Dead Cross
        # -----------------------------
        elif prev20 >= prev60 and ma20 < ma60:

            signal = "SELL"

        else:

            # RSI 추가조건

            if rsi <= 30:
                signal = "BUY"

            elif rsi >= 70:
                signal = "SELL"

            else:
                signal = "HOLD"

    return {

        "signal": signal,
        "rsi": rsi,
        "ma20": ma20,
        "ma60": ma60

    }


# ==========================================================
# Save Trading Record
# ==========================================================

def save_trade_record():

    signal = generate_signal()

    price = get_eth_price()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""

        INSERT INTO trading_records
        (
            signal,
            price,
            rsi,
            ma20,
            ma60
        )

        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s
        )

    """,

    (

        signal["signal"],
        price,
        signal["rsi"],
        signal["ma20"],
        signal["ma60"]

    ))

    conn.commit()

    cur.close()
    conn.close()


# ==========================================================
# Trade Check Page
# ==========================================================

@app.route("/trade-check")
def trade_check():

    signal = generate_signal()

    return render_template(

        "trade_check.html",

        signal=signal["signal"],

        rsi=signal["rsi"],

        ma20=signal["ma20"],

        ma60=signal["ma60"]

    )


# ==========================================================
# Trading Records Page
# ==========================================================

@app.route("/trades")
def trades():

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""

        SELECT *

        FROM trading_records

        ORDER BY id DESC

        LIMIT 200

    """)

    records = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(

        "trades.html",

        records=records

    )

# ==========================================================
# Part9
# Database Initialize
# PostgreSQL (Render)
# ==========================================================

def init_db():

    conn = get_db()

    cur = conn.cursor()

    # ======================================================
    # ETH PRICE
    # ======================================================

    cur.execute("""

    CREATE TABLE IF NOT EXISTS eth_price(

        id SERIAL PRIMARY KEY,

        price DOUBLE PRECISION NOT NULL,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    );

    """)

    # ======================================================
    # Trading Records
    # ======================================================

    cur.execute("""

    CREATE TABLE IF NOT EXISTS trading_records(

        id SERIAL PRIMARY KEY,

        signal VARCHAR(20),

        price DOUBLE PRECISION,

        rsi DOUBLE PRECISION,

        ma20 DOUBLE PRECISION,

        ma60 DOUBLE PRECISION,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    );

    """)

    # ======================================================
    # Portfolio
    # ======================================================

    cur.execute("""

    CREATE TABLE IF NOT EXISTS portfolio(

        id INTEGER PRIMARY KEY,

        cash DOUBLE PRECISION DEFAULT 100000,

        eth DOUBLE PRECISION DEFAULT 0,

        avg_buy DOUBLE PRECISION DEFAULT 0

    );

    """)

    # ======================================================
    # Portfolio 기본값
    # ======================================================

    cur.execute("""

    INSERT INTO portfolio
    (
        id,
        cash,
        eth,
        avg_buy
    )

    VALUES
    (
        1,
        100000,
        0,
        0
    )

    ON CONFLICT(id)

    DO NOTHING;

    """)

    conn.commit()

    cur.close()

    conn.close()


# ==========================================================
# Initialize Database
# ==========================================================

init_db()

# ==========================================================
# Part10
# Save Price / Portfolio / Chart Data / Run
# ==========================================================


# ----------------------------------------------------------
# Save ETH Price
# ----------------------------------------------------------
@app.route("/save-price", methods=["GET", "POST"])
def save_price():

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    message = ""

    if request.method == "POST":

        price = request.form["price"]

        cur.execute("""

            INSERT INTO eth_price(price)

            VALUES(%s)

        """,(price,))

        conn.commit()

        message = "ETH Price Saved!"

    cur.execute("""

        SELECT *

        FROM eth_price

        ORDER BY id DESC

        LIMIT 100

    """)

    prices = cur.fetchall()

    cur.close()

    conn.close()

    return render_template(

        "save_price.html",

        prices=prices,

        live_price=get_eth_price(),

        message=message

    )


# ----------------------------------------------------------
# Portfolio
# ----------------------------------------------------------
@app.route("/portfolio")
def portfolio():

    p = calculate_portfolio()

    return render_template(

        "portfolio.html",

        portfolio=p

    )


# ----------------------------------------------------------
# Chart Data API
# ----------------------------------------------------------
@app.route("/chart-data")
def chart_data():

    df = get_price_dataframe()

    prices = df["price"].tolist()

    labels = [

        str(x)

        for x in df["created_at"]

    ]

    ma20 = df["price"].rolling(20).mean().tolist()

    ma60 = df["price"].rolling(60).mean().tolist()

    buy = [None] * len(df)

    sell = [None] * len(df)

    golden = [None] * len(df)

    dead = [None] * len(df)

    for i in range(60, len(df)):

        p20 = ma20[i-1]

        p60 = ma60[i-1]

        c20 = ma20[i]

        c60 = ma60[i]

        if (

            p20 is None

            or p60 is None

            or c20 is None

            or c60 is None

        ):

            continue

        # -------------------------
        # Golden Cross
        # -------------------------

        if p20 <= p60 and c20 > c60:

            golden[i] = prices[i]

            buy[i] = prices[i]

        # -------------------------
        # Dead Cross
        # -------------------------

        elif p20 >= p60 and c20 < c60:

            dead[i] = prices[i]

            sell[i] = prices[i]

    return jsonify({

        "labels": labels,

        "prices": prices,

        "ma20": ma20,

        "ma60": ma60,

        "buy": buy,

        "sell": sell,

        "golden": golden,

        "dead": dead

    })


# ----------------------------------------------------------
# Auto Save Trade
# ----------------------------------------------------------
@app.route("/auto-save")
def auto_save():

    save_trade_record()

    return "OK"


# ----------------------------------------------------------
# Flask Run
# ----------------------------------------------------------
if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )
