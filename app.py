# ============================================================
# PART 1 : Import
# ============================================================

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session
)

import os
import threading
import time
from datetime import datetime
import traceback
import requests
import pandas as pd

import psycopg2
from psycopg2.extras import RealDictCursor


# ------------------------------------------------------------
# Flask
# ------------------------------------------------------------

app = Flask(__name__)

# ------------------------------------------------------------
# Session 암호키
# ------------------------------------------------------------
app.secret_key = "WDM_ADMIN_SECRET_KEY_2026"
# ============================================================
# PART 2 : PostgreSQL
# ============================================================

# ------------------------------------------------------------
# PostgreSQL Connection
# ------------------------------------------------------------

def get_db():
    """
    Render PostgreSQL 연결
    """

    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL is not set.")

    return psycopg2.connect(database_url)


# ------------------------------------------------------------
# Execute SELECT (Multiple Rows)
# ------------------------------------------------------------

def fetch_all(sql, params=None):

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(sql, params)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows

# ============================================================
# Load WDM History
# ============================================================

def load_wdm_history():

    return fetch_all(

        """

        SELECT

            created_at,

            price

        FROM

            wdm_price_history

        ORDER BY

            id ASC

        LIMIT 100

        """

    )
# ------------------------------------------------------------
# Execute SELECT (Single Row)
# ------------------------------------------------------------

def fetch_one(sql, params=None):

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(sql, params)

    row = cur.fetchone()

    cur.close()
    conn.close()

    return row


# ------------------------------------------------------------
# Execute INSERT / UPDATE / DELETE
# ------------------------------------------------------------

def execute(sql, params=None):

    conn = get_db()

    cur = conn.cursor()

    cur.execute(sql, params)

    conn.commit()

    cur.close()
    conn.close()


# ------------------------------------------------------------
# Keep Latest Rows
# ------------------------------------------------------------

def keep_latest_rows(table_name, limit_count=10000):

    conn = get_db()

    cur = conn.cursor()

    cur.execute(f"""
        DELETE FROM {table_name}
        WHERE id NOT IN
        (
            SELECT id
            FROM {table_name}
            ORDER BY id DESC
            LIMIT %s
        )
    """, (limit_count,))

    conn.commit()

    cur.close()
    conn.close()

# ============================================================
# PART 3 : Database
# ============================================================

# ------------------------------------------------------------
# Database Initialize
# ------------------------------------------------------------

def init_db():

    conn = get_db()
    cur = conn.cursor()

    # --------------------------------------------------------
    # ETH PRICE
    # --------------------------------------------------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS eth_price(

        id SERIAL PRIMARY KEY,

        price NUMERIC(18,6),

        ma20 NUMERIC,

        ma60 NUMERIC,

        signal TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)

    # --------------------------------------------------------
    # TRADING RECORDS
    # --------------------------------------------------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS trading_records(

        id SERIAL PRIMARY KEY,

        signal TEXT,

        price NUMERIC(18,6),

        quantity NUMERIC DEFAULT 0,

        trade_amount NUMERIC DEFAULT 0,

        profit NUMERIC DEFAULT 0,

        roi NUMERIC DEFAULT 0,

        trade_type TEXT DEFAULT 'AUTO',

        rsi NUMERIC,

        ma20 NUMERIC,

        ma60 NUMERIC,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)
    # --------------------------------------------------------
    # DONATION
    # --------------------------------------------------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS donation_records(

        id SERIAL PRIMARY KEY,

        quarter TEXT,

        net_profit NUMERIC,

        donation NUMERIC,

        proof TEXT

    )
    """)

    # --------------------------------------------------------
    # PORTFOLIO
    # --------------------------------------------------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS portfolio(

        id SERIAL PRIMARY KEY,

        cash NUMERIC DEFAULT 100000,

        eth NUMERIC DEFAULT 0,

        wdm NUMERIC DEFAULT 0,

        avg_price NUMERIC DEFAULT 0

    )
    """)
    # --------------------------------------------------------
    # WDM PRICE
    # --------------------------------------------------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS wdm_price(

        id SERIAL PRIMARY KEY,

        price NUMERIC(18,8),

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)
    # =====================================================
    # WDM Price Table 컬럼 추가
    # =====================================================
    cur.execute("""
    ALTER TABLE wdm_price
    ADD COLUMN IF NOT EXISTS ma20 DOUBLE PRECISION;
    """)

    cur.execute("""
    ALTER TABLE wdm_price
    ADD COLUMN IF NOT EXISTS ma60 DOUBLE PRECISION;
    """)

    cur.execute("""
    ALTER TABLE wdm_price
    ADD COLUMN IF NOT EXISTS signal VARCHAR(20);
    """)
   
    # --------------------------------------------------------
    # WDM PRICE HISTORY
    # --------------------------------------------------------

    cur.execute("""

    CREATE TABLE IF NOT EXISTS wdm_price_history(

        id SERIAL PRIMARY KEY,

        price NUMERIC(18,8),

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)
    # --------------------------------------------------------
    # WDM INFORMATION
    # --------------------------------------------------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS wdm_info(

        id SERIAL PRIMARY KEY,

        name TEXT,

        symbol TEXT,

        total_supply NUMERIC

    )
    """)
    # --------------------------------------------------------
    # WDM COIN
    # --------------------------------------------------------

    cur.execute("""
    CREATE TABLE IF NOT EXISTS meme_coin(

        id SERIAL PRIMARY KEY,

        name TEXT,

        symbol TEXT,

        total_supply NUMERIC,

        circulating_supply NUMERIC,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)
    
    conn.commit()

    cur.close()
    
        
    conn.close()


# ------------------------------------------------------------
# Update Old Database
# ------------------------------------------------------------

def update_database():

    conn = get_db()
    cur = conn.cursor()

    # ETH PRICE

    cur.execute("""
    ALTER TABLE eth_price
    ADD COLUMN IF NOT EXISTS ma20 NUMERIC
    """)

    cur.execute("""
    ALTER TABLE eth_price
    ADD COLUMN IF NOT EXISTS ma60 NUMERIC
    """)

    cur.execute("""
    ALTER TABLE eth_price
    ADD COLUMN IF NOT EXISTS signal TEXT
    """)

    # TRADING RECORDS

    cur.execute("""
    ALTER TABLE trading_records
    ADD COLUMN IF NOT EXISTS rsi NUMERIC
    """)

    cur.execute("""
    ALTER TABLE trading_records
    ADD COLUMN IF NOT EXISTS ma20 NUMERIC
    """)

    cur.execute("""
    ALTER TABLE trading_records
    ADD COLUMN IF NOT EXISTS ma60 NUMERIC
    """)
    # --------------------------------------------------------
    # Trading Records New Columns
    # --------------------------------------------------------

    cur.execute("""
    ALTER TABLE trading_records
    ADD COLUMN IF NOT EXISTS quantity NUMERIC DEFAULT 0
    """)

    cur.execute("""
    ALTER TABLE trading_records
    ADD COLUMN IF NOT EXISTS trade_amount NUMERIC DEFAULT 0
    """)

    cur.execute("""
    ALTER TABLE trading_records
    ADD COLUMN IF NOT EXISTS profit NUMERIC DEFAULT 0
    """)

    cur.execute("""
    ALTER TABLE trading_records
    ADD COLUMN IF NOT EXISTS roi NUMERIC DEFAULT 0
    """)

    cur.execute("""
    ALTER TABLE trading_records
    ADD COLUMN IF NOT EXISTS trade_type TEXT DEFAULT 'AUTO'
    """)

    # --------------------------------------------------------
    # Portfolio New Column
    # --------------------------------------------------------

    cur.execute("""
    ALTER TABLE portfolio
    ADD COLUMN IF NOT EXISTS wdm NUMERIC DEFAULT 0
    """)
   
    
    conn.commit()

    cur.close()
    conn.close()

    print("Database Updated")


# ------------------------------------------------------------
# Insert Default Portfolio
# ------------------------------------------------------------

def insert_default_portfolio():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""

        INSERT INTO portfolio
        (
          cash,
          eth,
          wdm,
          avg_price
        )

        SELECT
            100000,
            0,
            0,
            0

        WHERE NOT EXISTS
        (
            SELECT 1
            FROM portfolio
        )

    """)

    conn.commit()

    cur.close()
    conn.close()

# ------------------------------------------------------------
# Insert Default WDM Coin
# ------------------------------------------------------------

def insert_default_meme():

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""

        INSERT INTO meme_coin
        (

            name,

            symbol,

            total_supply,

            circulating_supply

        )

        SELECT

            'W-donation',

            'WDM',

            50000000,

            50000000

        WHERE NOT EXISTS
        (

            SELECT 1

            FROM meme_coin

        )

    """)

    conn.commit()

    cur.close()

    conn.close()
# ------------------------------------------------------------
# Insert Test Data
# ------------------------------------------------------------

def insert_test_data():

    conn = get_db()
    cur = conn.cursor()

    # ETH PRICE

    cur.execute("SELECT COUNT(*) FROM eth_price")

    if cur.fetchone()[0] == 0:

        cur.execute("""

        INSERT INTO eth_price
        (price)

        VALUES

        (1578.325),

        (1585.500),

        (1602.750)

        """)

    # TRADING RECORDS

    cur.execute("SELECT COUNT(*) FROM trading_records")

    if cur.fetchone()[0] == 0:

       cur.execute("""

        INSERT INTO trading_records
        (
            signal,
            price,
            quantity,
            trade_amount,
            profit,
            roi,
            trade_type
        )

        VALUES

        (
            'BUY',
            1578.325,
            2,
            3156.65,
            0,
            0,
            'AUTO'
        ),

        (
            'SELL',
            1585.500,
            2,
            3171.00,
            14.35,
            0.45,
            'AUTO'
        ),

        (
            'BUY',
            1602.750,
            1,
            1602.75,
            0,
            0,
            'MANUAL'
        )

        """)

    # DONATION

    cur.execute("SELECT COUNT(*) FROM donation_records")

    if cur.fetchone()[0] == 0:

        cur.execute("""

        INSERT INTO donation_records

        (quarter,net_profit,donation,proof)

        VALUES

        ('2026 Q1',0,0,'Preparing'),

        ('2026 Q2',0,0,'Preparing')

        """)

    # --------------------------------------------------------
    # WDM
    # --------------------------------------------------------

    cur.execute("SELECT COUNT(*) FROM wdm_info")

    if cur.fetchone()[0] == 0:

        cur.execute("""

        INSERT INTO wdm_info
        (
            name,
            symbol,
            total_supply
        )

        VALUES
        (
            'W-donation',
            'WDM',
            50000000
        )

        """)
    # --------------------------------------------------------
    # WDM 최초 가격
    # --------------------------------------------------------

    cur.execute("SELECT COUNT(*) FROM wdm_price")

    if cur.fetchone()[0] == 0:

        cur.execute("""

        INSERT INTO wdm_price(price)

        VALUES(0.00100000)

        """)   
    conn.commit()

    cur.close()
    conn.close()
    
# ============================================================
# PART 4 : Indicator
# ============================================================
# ============================================================
# ETH Price (CoinGecko)
# ============================================================

def get_eth_price():

    try:

        url = "https://api.coingecko.com/api/v3/simple/price"

        params = {
            "ids": "ethereum",
            "vs_currencies": "usd"
        }

        r = requests.get(url, params=params, timeout=10)

        # 응답 확인
        print("STATUS :", r.status_code)

        data = r.json()

        print("RESPONSE :", data)

        # ethereum 키가 없으면 None 반환
        if "ethereum" not in data:

            return None

        return float(data["ethereum"]["usd"])

    except Exception as e:

        print("ETH PRICE ERROR :", e)

        return None
# ------------------------------------------------------------
# Latest Price (DB)
# 팝업창 즉시 표시용
# ------------------------------------------------------------
def get_latest_price():

    row = fetch_one("""

        SELECT price

        FROM eth_price

        ORDER BY id DESC

        LIMIT 1

    """)

    if row:

        return float(row["price"])

    return None

# ------------------------------------------------------------
# Latest WDM Price
# ------------------------------------------------------------

def get_latest_wdm_price():

    row = fetch_one("""
    

        SELECT price

        FROM wdm_price

        ORDER BY id DESC

        LIMIT 1

    """)

    if row:

        return float(row["price"])

    return 0.001
# ============================================================
# Save ETH Price
# ============================================================

def save_eth_price(price):

    execute(

        """

        INSERT INTO

            eth_price

            (

                price

            )

        VALUES

            (

                %s

            )

        """,

        (price,)

    )

    keep_latest_rows(

        "eth_price",

        10000

    )
@app.route("/save-wdm-price", methods=["GET", "POST"])
def save_wdm_price():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    message = ""

    # ------------------------------------------------------
    # 저장 버튼 클릭
    # ------------------------------------------------------
    if request.method == "POST":

        price = float(request.form["price"])

        # ----------------------------------------------
        # 가격 저장
        # ----------------------------------------------
        cur.execute("""
            INSERT INTO wdm_price(price)
            VALUES(%s)
            RETURNING id
        """, (price,))

        new_id = cur.fetchone()["id"]

        conn.commit()

        # ----------------------------------------------
        # MA20 계산
        # ----------------------------------------------
        cur.execute("""
            SELECT price
            FROM wdm_price
            ORDER BY id DESC
            LIMIT 20
        """)

        rows = cur.fetchall()

        ma20 = None

        if len(rows) == 20:

            ma20 = sum(float(r["price"]) for r in rows) / 20

        # ----------------------------------------------
        # MA60 계산
        # ----------------------------------------------
        cur.execute("""
            SELECT price
            FROM wdm_price
            ORDER BY id DESC
            LIMIT 60
        """)

        rows = cur.fetchall()

        ma60 = None

        if len(rows) == 60:

            ma60 = sum(float(r["price"]) for r in rows) / 60

        # ----------------------------------------------
        # 이전 MA 조회
        # ----------------------------------------------
        cur.execute("""
            SELECT
                ma20,
                ma60
            FROM wdm_price
            WHERE id < %s
            ORDER BY id DESC
            LIMIT 1
        """, (new_id,))

        prev = cur.fetchone()

        signal = "HOLD"

        if prev:

            prev20 = prev["ma20"]
            prev60 = prev["ma60"]

            if None not in (prev20, prev60, ma20, ma60):

                # --------------------------
                # Golden Cross
                # --------------------------
                if prev20 <= prev60 and ma20 > ma60:

                    signal = "BUY"

                # --------------------------
                # Dead Cross
                # --------------------------
                elif prev20 >= prev60 and ma20 < ma60:

                    signal = "SELL"

        # ----------------------------------------------
        # MA / Signal 업데이트
        # ----------------------------------------------
        cur.execute("""
            UPDATE wdm_price
            SET
                ma20=%s,
                ma60=%s,
                signal=%s
            WHERE id=%s
        """, (
            ma20,
            ma60,
            signal,
            new_id
        ))

        # ----------------------------------------------
        # 저장 완료
        # ----------------------------------------------
        conn.commit()

        message = f"WDM Saved ({signal})"
    # ==========================================================
    # 저장 완료
    # (signal은 위에서 이미 계산되어 있음)
    # ==========================================================

    conn.commit()

    message = f"WDM Saved ({signal})"

    # ------------------------------------------------------
    # 최근 데이터 표시
    # ------------------------------------------------------
    cur.execute("""
        SELECT *
        FROM wdm_price
        ORDER BY id DESC
        LIMIT 100
    """)

    prices = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(

        "save_wdm_price.html",

        prices=prices,

        live_price=get_latest_wdm_price(),

        message=message

    )
# ==========================================================
# WDM Moving Average
# MA 계산
# 기존 calculate_wdm_ma() 함수 전체 교체
# ==========================================================

def calculate_wdm_ma(period):

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT price
        FROM wdm_price
        ORDER BY id DESC
        LIMIT %s
    """, (period,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    # ------------------------------------------
    # 데이터 부족
    # ------------------------------------------
    if len(rows) < period:

        return None

    prices = [float(r["price"]) for r in rows]

    return round(sum(prices) / period, 8)


# ==========================================================
# WDM Previous Moving Average
# 이전 MA 계산
# 기존 calculate_previous_wdm_ma() 함수 전체 교체
# ==========================================================

def calculate_previous_wdm_ma(period):

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT price
        FROM wdm_price
        ORDER BY id DESC
        LIMIT %s
    """, (period + 1,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    # ------------------------------------------
    # 데이터 부족
    # ------------------------------------------
    if len(rows) < period + 1:

        return None

    # 최근 가격 제외
    prices = [float(r["price"]) for r in rows[1:]]

    return round(sum(prices) / period, 8)    
# ==========================================================
# WDM RSI
# RSI 계산
# calculate_previous_wdm_ma() 바로 아래 붙여넣기
# ==========================================================

def calculate_wdm_rsi(period=14):

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ------------------------------------------------------
    # 최근 period+1개의 가격 조회
    # ------------------------------------------------------
    cur.execute("""
        SELECT price
        FROM wdm_price
        ORDER BY id DESC
        LIMIT %s
    """, (period + 1,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    # ------------------------------------------------------
    # 데이터 부족
    # ------------------------------------------------------
    if len(rows) < period + 1:

        return None

    # 오래된 가격 → 최신 가격 순으로 정렬
    prices = [float(r["price"]) for r in reversed(rows)]

    gains = []
    losses = []

    # ------------------------------------------------------
    # 상승 / 하락 계산
    # ------------------------------------------------------
    for i in range(1, len(prices)):

        diff = prices[i] - prices[i - 1]

        if diff > 0:

            gains.append(diff)
            losses.append(0)

        else:

            gains.append(0)
            losses.append(abs(diff))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # ------------------------------------------------------
    # RSI 계산
    # ------------------------------------------------------
    if avg_loss == 0:

        return 100

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return round(rsi, 2)

# ==========================================================
# WDM Trading Signal
# ETH generate_signal()과 동일한 구조
# calculate_wdm_rsi() 아래 붙여넣기
# ==========================================================

def generate_wdm_signal():

    # ------------------------------------------------------
    # 지표 계산
    # ------------------------------------------------------
    rsi = calculate_wdm_rsi()

    ma20 = calculate_wdm_ma(20)

    ma60 = calculate_wdm_ma(60)

    prev20 = calculate_previous_wdm_ma(20)

    prev60 = calculate_previous_wdm_ma(60)

    signal = "HOLD"

    # ------------------------------------------------------
    # 데이터 부족
    # ------------------------------------------------------
    if None in (rsi, ma20, ma60, prev20, prev60):

        signal = "HOLD"

    else:

        # --------------------------------------------------
        # GOLDEN CROSS
        # --------------------------------------------------
        if prev20 <= prev60 and ma20 > ma60:

            if rsi < 30:

                signal = "BUY"

            else:

                signal = "BUY"

        # --------------------------------------------------
        # DEAD CROSS
        # --------------------------------------------------
        elif prev20 >= prev60 and ma20 < ma60:

            if rsi > 70:

                signal = "SELL"

            else:

                signal = "SELL"

        # --------------------------------------------------
        # HOLD
        # --------------------------------------------------
        else:

            signal = "HOLD"

    # ------------------------------------------------------
    # 결과 반환
    # ------------------------------------------------------
    return {

        "signal": signal,

        "rsi": rsi,

        "ma20": ma20,

        "ma60": ma60

    }
# ------------------------------------------------------------
# RSI 계산
# ------------------------------------------------------------
def calculate_rsi(period=14):

    prices = fetch_all(
        """
        SELECT price
        FROM eth_price
        ORDER BY id ASC
        """
    )


    if len(prices) < period + 1:

        return None


    close_prices = [
        float(row["price"])
        for row in prices
    ]


    import pandas as pd


    series = pd.Series(close_prices)


    delta = series.diff()


    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)


    avg_gain = gain.rolling(
        window=period
    ).mean()


    avg_loss = loss.rolling(
        window=period
    ).mean()


    rs = avg_gain / avg_loss


    rsi = 100 - (
        100 / (1 + rs)
    )


    return round(
        float(rsi.iloc[-1]),
        2
    )   
# ------------------------------------------------------------
# Moving Average
# ------------------------------------------------------------

def calculate_ma(period):

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT price
        FROM eth_price
        ORDER BY id DESC
        LIMIT %s
    """, (period,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    if len(rows) < period:
        return None

    prices = [float(r["price"]) for r in rows]

    prices.reverse()

    return round(sum(prices) / period, 2)


# ------------------------------------------------------------
# Previous Moving Average
# ------------------------------------------------------------

def calculate_previous_ma(period):

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT price
        FROM eth_price
        ORDER BY id DESC
        LIMIT %s
    """, (period + 1,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    if len(rows) < period + 1:
        return None

    prices = [float(r["price"]) for r in rows]

    prices.reverse()

    previous_prices = prices[:-1]

    return round(sum(previous_prices) / period, 2)

# ------------------------------------------------------------
# Cross Signal
# MA20 / MA60 실제 교차 계산
# ------------------------------------------------------------
def get_cross_signals():

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""

        SELECT
            id,
            ma20,
            ma60,
            price
        FROM eth_price
        ORDER BY id ASC

    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    if len(rows) < 2:
        return "HOLD"

    prev = rows[-2]
    curr = rows[-1]

    if (
        prev["ma20"] is None or
        prev["ma60"] is None or
        curr["ma20"] is None or
        curr["ma60"] is None
    ):
        return "HOLD"

    prev20 = float(prev["ma20"])
    prev60 = float(prev["ma60"])

    curr20 = float(curr["ma20"])
    curr60 = float(curr["ma60"])

    # ------------------------------
    # Golden Cross
    # ------------------------------
    if prev20 <= prev60 and curr20 > curr60:
        return "BUY"

    # ------------------------------
    # Dead Cross
    # ------------------------------
    if prev20 >= prev60 and curr20 < curr60:
        return "SELL"

    return "HOLD"
# ------------------------------------------------------------
# Trading Signal
# ------------------------------------------------------------
def generate_signal():

    # --------------------------------------------------------
    # RSI 계산
    # --------------------------------------------------------

    rsi = calculate_rsi()

    # --------------------------------------------------------
    # 이동평균 계산
    # --------------------------------------------------------

    ma20 = calculate_ma(20)

    ma60 = calculate_ma(60)

    # --------------------------------------------------------
    # 데이터가 부족하면 HOLD
    # --------------------------------------------------------

    if ma20 is None or ma60 is None:

        return {

            "signal": "HOLD",

            "rsi": rsi,

            "ma20": ma20,

            "ma60": ma60

        }

    # --------------------------------------------------------
    # MA20 / MA60 교차 신호 계산
    # --------------------------------------------------------

    signal = get_cross_signals()

    # --------------------------------------------------------
    # RSI 보강 판단
    # --------------------------------------------------------

    if signal == "BUY":

        if rsi is not None:

            if rsi < 30:

                signal = "STRONG BUY"

    elif signal == "SELL":

        if rsi is not None:

            if rsi > 70:

                signal = "STRONG SELL"

    # --------------------------------------------------------
    # 결과 반환
    # --------------------------------------------------------

    return {

     "signal": signal,

     "price": get_latest_price(),

     "rsi": rsi,

     "ma20": ma20,

     "ma60": ma60

   }
# ------------------------------------------------------------
# WDM Price
# ETH 가격을 기준으로 계산
# ------------------------------------------------------------

def calculate_wdm_price():

    eth = get_latest_price()

    if eth is None:

        return 0.001

    # ETH 가격의 1/2,000,000
    price = eth / 2000000

    return round(price, 8)   
# ============================================================
# PART 5 : Auto Save
# ============================================================

def auto_save_eth():

    while True:

        try:

            # ------------------------------------------------
            # 현재 ETH 가격
            # ------------------------------------------------

            price = get_eth_price()

            if price is None:

                time.sleep(30)
                continue

            # ------------------------------------------------
            # DB 저장 (가격만 먼저 저장)
            # ------------------------------------------------

            conn = get_db()

            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""

                INSERT INTO eth_price(price)

                VALUES(%s)

                RETURNING id

            """,(price,))

            new_id = cur.fetchone()["id"]

            conn.commit()
            # ------------------------------------------------
            # WDM 가격 저장
            # ------------------------------------------------

            wdm_price = calculate_wdm_price()

            cur.execute("""

                INSERT INTO wdm_price
                (
                    price
                )

                VALUES
                (
                    %s
                )

            """,(wdm_price,))

            # ------------------------------------------------
            # 이동평균 계산
            # ------------------------------------------------

            ma20 = calculate_ma(20)

            ma60 = calculate_ma(60)

            # ------------------------------------------------
            # 신호 계산
            # ------------------------------------------------

            signal_data = generate_signal()

            signal = signal_data["signal"]

            # 자동매매 실행
            auto_trade(signal_data)
            # ------------------------------------------------
            # 같은 행 UPDATE
            # ------------------------------------------------

            cur.execute("""

                UPDATE eth_price

                SET

                    ma20=%s,

                    ma60=%s,

                    signal=%s

                WHERE id=%s

            """,

            (

                ma20,

                ma60,

                signal,

                new_id

            ))

            conn.commit()

            cur.close()

            conn.close()

            print(

                f"[AUTO] "

                f"Price={price:.2f} "

                f"MA20={ma20} "

                f"MA60={ma60} "

                f"Signal={signal}"

            )
           # ------------------------------------------------
           # 오래된 데이터 삭제
           # ------------------------------------------------
            keep_latest_rows("eth_price", 10000)
            keep_latest_rows("trading_records", 10000)


        except Exception as e:

            print("AUTO SAVE ERROR :", e)

        # ------------------------------------------------
        # 10분마다 저장
        # ------------------------------------------------

        time.sleep(600)

# ==========================================================
# PART 6 : Portfolio
# ==========================================================

# --------------------------------------
# Portfolio 조회
# --------------------------------------
def calculate_portfolio():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Portfolio가 없으면 생성
    cur.execute("""
        SELECT *
        FROM portfolio
        LIMIT 1
    """)

    portfolio = cur.fetchone()

    if portfolio is None:

        cur.execute("""
            INSERT INTO portfolio
            (
                cash,
                eth,
                avg_price
            )
            VALUES
            (
                100000,
                0,
                0
            )
        """)

        conn.commit()

        cur.execute("""
            SELECT *
            FROM portfolio
            LIMIT 1
        """)

        portfolio = cur.fetchone()

    # 현재 ETH 가격
    cur.execute("""
        SELECT price
        FROM eth_price
        ORDER BY id DESC
        LIMIT 1
    """)

    row = cur.fetchone()

    current_price = 0

    if row:
        current_price = float(row["price"])

    # --------------------------------------------------------
    # Portfolio 금액 계산
    # --------------------------------------------------------

    cash = float(portfolio["cash"])
    eth = float(portfolio["eth"])
    wdm = float(portfolio["wdm"])
    avg_price = float(portfolio["avg_price"])

    # --------------------------------------------------------
    # ETH 자산 평가금액
    # --------------------------------------------------------

    asset_value = eth * current_price

    # --------------------------------------------------------
    # WDM 현재가격 조회
    # 반드시 먼저 계산해야 함
    # --------------------------------------------------------

    wdm_price = get_latest_wdm_price()

    # --------------------------------------------------------
    # WDM 평가금액
    # --------------------------------------------------------

    wdm_value = wdm * wdm_price

    # --------------------------------------------------------
    # 총 자산
    # --------------------------------------------------------

    total_assets = cash + asset_value + wdm_value
    # --------------------------------------------------------
    # WDM 현재가격
    # --------------------------------------------------------

    
    if eth > 0:
        profit = asset_value - (eth * avg_price)
    else:
        profit = 0

    if eth > 0 and avg_price > 0:
        roi = ((current_price - avg_price) / avg_price) * 100
    else:
        roi = 0

    cur.close()
    conn.close()

    return {

        "cash": round(cash, 2),

        "wdm": round(wdm,2),

        "eth": round(eth, 8),

        "wdm_price": round(wdm_price,8),

        "wdm_value": round(wdm_value,2),

        "avg_price": round(avg_price, 2),

        "current_price": round(current_price, 2),

        "asset_value": round(asset_value, 2),

        "total_assets": round(total_assets, 2),

        "profit": round(profit, 2),

        "roi": round(roi, 2)

    }
# ------------------------------------------------------------
# BUY ETH
# Portfolio에서 현금을 이용하여 ETH 매수
# ------------------------------------------------------------
def buy_eth(buy_percent=20):

    # --------------------------------------------------------
    # DB 연결
    # --------------------------------------------------------

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:

        # ----------------------------------------------------
        # Portfolio 조회
        # ----------------------------------------------------

        cur.execute("""

            SELECT
                cash,
                eth,
                avg_price

            FROM portfolio

            LIMIT 1

        """)

        portfolio = cur.fetchone()

        if portfolio is None:

            print("Portfolio Not Found")

            return None

        cash = float(portfolio["cash"])

        eth = float(portfolio["eth"])

        avg_price = float(portfolio["avg_price"])

        # ----------------------------------------------------
        # 이미 ETH 보유중이면 매수 안함
        # ----------------------------------------------------

        if eth > 0:

            print("BUY SKIP : Already Holding")

            return None

        # ----------------------------------------------------
        # 현재 ETH 가격 조회
        # ----------------------------------------------------

        cur.execute("""

            SELECT price

            FROM eth_price

            ORDER BY id DESC

            LIMIT 1

        """)

        row = cur.fetchone()

        if row is None:

            print("ETH Price Not Found")

            return None

        current_price = float(row["price"])

        # ----------------------------------------------------
        # 매수금액 계산
        # ----------------------------------------------------

        trade_amount = round(

            cash * buy_percent / 100,

            2

        )

        if trade_amount <= 0:

            return None

        # ----------------------------------------------------
        # 매수수량 계산
        # ----------------------------------------------------

        quantity = trade_amount / current_price

        # ----------------------------------------------------
        # Portfolio 계산
        # ----------------------------------------------------

        new_cash = cash - trade_amount

        new_eth = eth + quantity

        # ----------------------------------------------------
        # 평균단가 계산
        # ----------------------------------------------------

        if eth == 0:

            new_avg_price = current_price

        else:

            new_avg_price = (

                (eth * avg_price)

                +

                (quantity * current_price)

            ) / new_eth

        # ----------------------------------------------------
        # Portfolio UPDATE
        # ----------------------------------------------------

        cur.execute("""

            UPDATE portfolio

            SET

                cash=%s,

                eth=%s,

                avg_price=%s
           
        """,

        (

            new_cash,

            new_eth,

            new_avg_price

        ))

        conn.commit()

        # ----------------------------------------------------
        # Console 출력
        # ----------------------------------------------------

        print("=================================")

        print("AUTO BUY COMPLETE")

        print(f"PRICE      : {current_price:.2f}")

        print(f"QUANTITY   : {quantity:.8f}")

        print(f"AMOUNT     : {trade_amount:.2f}")

        print(f"CASH LEFT  : {new_cash:.2f}")

        print("=================================")

        # ----------------------------------------------------
        # 거래정보 반환
        # auto_trade()에서 사용
        # ----------------------------------------------------

        return {

            "signal": "BUY",

            "price": current_price,

            "quantity": quantity,

            "trade_amount": trade_amount,

            "profit": 0,

            "roi": 0,

            "trade_type": "AUTO"

        }

    except Exception as e:

        conn.rollback()

        print("BUY ERROR :", e)

        return None

    finally:

        cur.close()

        conn.close()
# ------------------------------------------------------------
# SELL ETH
# Portfolio에서 보유 ETH 전량 매도
# Portfolio 업데이트
# 실현손익 계산
# ROI 계산
# 거래정보 반환
# ------------------------------------------------------------
def sell_eth():

    # --------------------------------------------------------
    # DB 연결
    # --------------------------------------------------------

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:

        # ----------------------------------------------------
        # Portfolio 조회
        # ----------------------------------------------------

        cur.execute("""

            SELECT
                cash,
                eth,
                avg_price

            FROM portfolio

            LIMIT 1

        """)

        portfolio = cur.fetchone()

        if portfolio is None:

            print("Portfolio Not Found")

            return None

        cash = float(portfolio["cash"])

        eth = float(portfolio["eth"])

        avg_price = float(portfolio["avg_price"])

        # ----------------------------------------------------
        # ETH가 없으면 매도 안함
        # ----------------------------------------------------

        if eth <= 0:

            print("SELL SKIP : No ETH")

            return None

        # ----------------------------------------------------
        # 현재 ETH 가격 조회
        # ----------------------------------------------------

        cur.execute("""

            SELECT price

            FROM eth_price

            ORDER BY id DESC

            LIMIT 1

        """)

        row = cur.fetchone()

        if row is None:

            print("ETH Price Not Found")

            return None

        current_price = float(row["price"])

        # ----------------------------------------------------
        # 매도금액 계산
        # ----------------------------------------------------

        trade_amount = eth * current_price

        # ----------------------------------------------------
        # 실현손익 계산
        # ----------------------------------------------------

        profit = (

            current_price - avg_price

        ) * eth

        # ----------------------------------------------------
        # ROI 계산
        # ----------------------------------------------------

        if avg_price > 0:

            roi = (

                (current_price - avg_price)

                / avg_price

            ) * 100

        else:

            roi = 0

        # ----------------------------------------------------
        # Portfolio 계산
        # ----------------------------------------------------

        new_cash = cash + trade_amount

        new_eth = 0

        new_avg_price = 0

        # ----------------------------------------------------
        # Portfolio UPDATE
        # ----------------------------------------------------

        cur.execute("""

            UPDATE portfolio

            SET

                cash=%s,

                eth=%s,

                avg_price=%s
           
        """,

        (

            new_cash,

            new_eth,

            new_avg_price

        ))

        conn.commit()

        # ----------------------------------------------------
        # Console 출력
        # ----------------------------------------------------

        print("=================================")

        print("AUTO SELL COMPLETE")

        print(f"SELL PRICE   : {current_price:.2f}")

        print(f"QUANTITY     : {eth:.8f}")

        print(f"AMOUNT       : {trade_amount:.2f}")

        print(f"PROFIT       : {profit:.2f}")

        print(f"ROI          : {roi:.2f}%")

        print("=================================")

        # ----------------------------------------------------
        # 거래정보 반환
        # auto_trade()에서 사용
        # ----------------------------------------------------

        return {

            "signal": "SELL",

            "price": current_price,

            "quantity": eth,

            "trade_amount": trade_amount,

            "profit": profit,

            "roi": roi,

            "trade_type": "AUTO"

        }

    except Exception as e:

        conn.rollback()

        print("SELL ERROR :", e)

        return None

    finally:

        cur.close()

        conn.close()
# ============================================================
# PART 6-1 : ETH ↔ WDM Swap Engine
# ============================================================
# ====================================================
# PART 6-1
# ETH ↔ WDM Virtual DEX
# ====================================================

    calculate_swap()

    swap_eth_to_wdm()

    swap_wdm_to_eth()

    liquidity_pool()
# ------------------------------------------------------------
# ETH → WDM Swap
# ------------------------------------------------------------

# 구현 예정
# ETH를 현재 WDM 가격으로 교환
# Portfolio 업데이트
# Trading Record 저장
# 실제 DEX 연동 예정

# ------------------------------------------------------------
# WDM → ETH Swap
# ------------------------------------------------------------

# 구현 예정
# WDM를 현재 ETH 가격으로 교환
# Portfolio 업데이트
# Trading Record 저장
# 실제 DEX 연동 예정

# ------------------------------------------------------------
# ETH ↔ WDM Swap Price
# ------------------------------------------------------------

# 구현 예정
# 현재 ETH 가격
# 현재 WDM 가격
# Swap 비율 계산
# 예상 수령수량 계산

# ------------------------------------------------------------
# Swap Fee
# ------------------------------------------------------------

# 구현 예정
# 0.3% Swap Fee
# 추후 변경 가능

# ------------------------------------------------------------
# Liquidity Pool
# ------------------------------------------------------------

# 구현 예정
# ETH Reserve
# WDM Reserve
# Constant Product (x*y=k)
# 실제 Uniswap 방식 적용 예정       
# ------------------------------------------------------------
# AUTO TRADE
# 자동매매 엔진
#
# BUY  -> buy_eth()
# SELL -> sell_eth()
# HOLD -> 아무것도 안함
#
# 거래기록 저장은 이 함수에서만 수행한다.
# ------------------------------------------------------------
def auto_trade(signal_data=None):

    # --------------------------------------------------------
    # signal_data가 없으면 새로 생성
    # --------------------------------------------------------

    if signal_data is None:

        signal_data = generate_signal()

    # --------------------------------------------------------
    # 신호 데이터
    # --------------------------------------------------------

    signal = signal_data["signal"]

    price = signal_data["price"]

    rsi = signal_data["rsi"]

    ma20 = signal_data["ma20"]

    ma60 = signal_data["ma60"]

    print("--------------------------------")

    print("AUTO TRADE START")

    print(f"SIGNAL : {signal}")

    print("--------------------------------")

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    if signal in ("BUY", "STRONG BUY"):

        # ----------------------------------------------------
        # Portfolio 매수
        # ----------------------------------------------------

        result = buy_eth()

        # ----------------------------------------------------
        # 매수 실패
        # ----------------------------------------------------

        if result is None:

            print("BUY FAILED")

            return False

        # ----------------------------------------------------
        # DB 연결
        # ----------------------------------------------------

        conn = get_db()

        cur = conn.cursor()

        # ----------------------------------------------------
        # 거래기록 저장
        # ----------------------------------------------------

        cur.execute("""

            INSERT INTO trading_records
            (

                signal,

                price,

                quantity,

                trade_amount,

                profit,

                roi,

                trade_type,

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

                %s,

                %s,

                %s,

                %s,

                %s,

                %s

            )

        """,

        (

            result["signal"],

            result["price"],

            result["quantity"],

            result["trade_amount"],

            result["profit"],

            result["roi"],

            result["trade_type"],

            rsi,

            ma20,

            ma60

        ))

        conn.commit()

        cur.close()

        conn.close()

        print("AUTO BUY SUCCESS")

        return True
    elif signal in ("SELL", "STRONG SELL"):

        # ----------------------------------------------------
        # Portfolio 매도
        # ----------------------------------------------------

        result = sell_eth()

        # ----------------------------------------------------
        # 매도 실패
        # ----------------------------------------------------

        if result is None:

            print("SELL FAILED")

            return False

        # ----------------------------------------------------
        # DB 연결
        # ----------------------------------------------------

        conn = get_db()

        cur = conn.cursor()

        # ----------------------------------------------------
        # 거래기록 저장
        # ----------------------------------------------------

        cur.execute("""

            INSERT INTO trading_records
            (

                signal,

                price,

                quantity,

                trade_amount,

                profit,

                roi,

                trade_type,

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

                %s,

                %s,

                %s,

                %s,

                %s,

                %s

            )

        """,

        (

            result["signal"],

            result["price"],

            result["quantity"],

            result["trade_amount"],

            result["profit"],

            result["roi"],

            result["trade_type"],

            rsi,

            ma20,

            ma60

        ))

        conn.commit()

        cur.close()

        conn.close()

        print("AUTO SELL SUCCESS")

        return True

    # --------------------------------------------------------
    # HOLD
    # --------------------------------------------------------

    elif signal == "HOLD":

        print("AUTO TRADE : HOLD")

        return False

    # --------------------------------------------------------
    # 기타 신호
    # --------------------------------------------------------

    else:

        print("UNKNOWN SIGNAL :", signal)

        return False

# ------------------------------------------------------------
# Admin Check
# ------------------------------------------------------------

def admin_required():

    if not session.get("admin"):

        return False

    return True
# ==========================================================
# PART 7  Routes
# ==========================================================

# -----------------------------
# Home
# -----------------------------
@app.route("/")
def home():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM donation_records
        ORDER BY id DESC
    """)

    donations = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "donation.html",
        donations=donations
    )



# -----------------------------
# Trading Menu
# -----------------------------
@app.route("/trading")
def trading():
    return render_template("trading.html")


# -----------------------------
# Whitepaper
# -----------------------------
@app.route("/whitepaper")
def whitepaper():
    return render_template("whitepaper.html")


# -----------------------------
# Poem
# -----------------------------
@app.route("/poem")
def poem():
    return render_template("poem.html")

# ------------------------------------------------------------
# ETH Price Popup Page
# price.html 출력용
# ------------------------------------------------------------
@app.route("/price")
def price():

    # --------------------------------------------------------
    # DB 최신 가격
    # --------------------------------------------------------

    live_price = get_latest_price()

    # 최근 가격 기록 가져오기
    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)


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

        "price.html",

        live_price=live_price,

        prices=prices

    )



# ------------------------------------------------------------
# ETH Price API
# JavaScript / 자동 갱신용
# ------------------------------------------------------------
@app.route("/price-api")
def price_api():

    # --------------------------------------------------------
    # DB 최신 가격
    # --------------------------------------------------------

    live_price = get_latest_price()


    if live_price is None:

        return jsonify({

            "success": False,

            "price": None

        })


    return jsonify({

        "success": True,

        "price": live_price

    })

# -----------------------------
# Save Price
# -----------------------------
@app.route("/save-price", methods=["GET", "POST"])
def save_price():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # --------------------------------------------------------
    # Message
    # --------------------------------------------------------

    message = ""
    # --------------------------------------------------------
    # Save Button
    # --------------------------------------------------------

    if request.method == "POST":

        live_price = get_latest_price()

        cur.execute("""

            INSERT INTO eth_price(price)

            VALUES(%s)

        """, (live_price,))

        conn.commit()

        message = "ETH price saved successfully."

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

    live_price=get_latest_price(),

    message=message

)


# -----------------------------
# Price History
# -----------------------------
@app.route("/history")
def history():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM eth_price
        ORDER BY id DESC
        LIMIT 500
    """)

    prices = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "history.html",
        prices=prices
    )


@app.route("/trade-check")
def trade_check():

    try:

        signal = generate_signal()

        print("TRADE CHECK RESULT")
        print(signal)

        return render_template(

            "trade_check.html",

            signal=signal.get("signal"),

            rsi=signal.get("rsi"),

            ma20=signal.get("ma20"),

            ma60=signal.get("ma60")

        )


    except Exception as e:

        traceback.print_exc()

        return f"""
        <h3>Trade Check Error</h3>
        <pre>{e}</pre>
        """

# -----------------------------
# Trading Records
# -----------------------------
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


# -----------------------------
# Portfolio
# -----------------------------
@app.route("/portfolio")
def portfolio():

    portfolio = calculate_portfolio()

    return render_template(
        "portfolio.html",
        portfolio=portfolio
    )

# ------------------------------------------------------------
# Swap
# ------------------------------------------------------------
@app.route("/swap")
def swap():
    return render_template("swap.html")
# ------------------------------------------------------------
# Admin Login
# ------------------------------------------------------------

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]


        # 관리자 계정
        if (
            username == "admin"
            and password == "1234"
        ):

            session["admin"] = True

            return redirect(
                "/admin/donation"
            )


        else:

            return """
            <h3>
            Login Failed
            </h3>
            """


    return render_template(
        "admin_login.html"
    )
# ------------------------------------------------------------
# Donation Management
# 기부 보고서 관리자 페이지
# ------------------------------------------------------------

@app.route("/admin/donation")
def admin_donation():


    if not admin_required():

        return redirect(
            "/admin/login"
        )


    donations = fetch_all(
        """
        SELECT *
        FROM donation_records
        ORDER BY id DESC
        """
    )


    return render_template(
        "admin_donation.html",
        donations=donations
    )

# ------------------------------------------------------------
# Donation 추가
# 관리자 로그인 필요
# ------------------------------------------------------------

@app.route("/admin/donation/add", methods=["POST"])
def add_donation():


    # 관리자 확인
    if not admin_required():

        return redirect(
            "/admin/login"
        )


    quarter = request.form["quarter"]

    net_profit = request.form["net_profit"]

    donation = request.form["donation"]

    proof = request.form["proof"]



    execute(

        """
        INSERT INTO donation_records
        (
            quarter,
            net_profit,
            donation,
            proof
        )

        VALUES
        (%s,%s,%s,%s)

        """,

        (
            quarter,
            net_profit,
            donation,
            proof
        )

    )


    return redirect(
        "/admin/donation"
    )



# ------------------------------------------------------------
# Donation 수정
# 관리자 로그인 필요
# ------------------------------------------------------------

@app.route("/admin/donation/edit/<int:id>", methods=["POST"])
def edit_donation(id):


    # 관리자 확인
    if not admin_required():

        return redirect(
            "/admin/login"
        )



    quarter = request.form["quarter"]

    net_profit = request.form["net_profit"]

    donation = request.form["donation"]

    proof = request.form["proof"]



    execute(

        """
        UPDATE donation_records

        SET

            quarter=%s,

            net_profit=%s,

            donation=%s,

            proof=%s


        WHERE id=%s

        """,

        (

            quarter,

            net_profit,

            donation,

            proof,

            id

        )

    )


    return redirect(
        "/admin/donation"
    )



# ------------------------------------------------------------
# Donation 삭제
# 관리자 로그인 필요
# ------------------------------------------------------------

@app.route("/admin/donation/delete/<int:id>")
def delete_donation(id):


    # 관리자 확인
    if not admin_required():

        return redirect(
            "/admin/login"
        )



    execute(

        """
        DELETE FROM donation_records

        WHERE id=%s

        """,

        (id,)

    )


    return redirect(
        "/admin/donation"
    )
# -----------------------------
# Chart
# -----------------------------
@app.route("/chart")
def chart():

    return render_template("chart.html")
# ------------------------------------------------------------
# Swap API
# ------------------------------------------------------------
@app.route("/swap-api")
def swap_api():

    return jsonify({

        "eth_price": get_latest_price(),

        "wdm_price": get_latest_wdm_price()
     
       
    })
# ------------------------------------------------------------
# Execute Swap
# ------------------------------------------------------------

@app.route("/execute-swap", methods=["POST"])
def execute_swap():

    return jsonify({

        "success":False,

        "message":"Swap engine not implemented"

    })
    
# ==========================================================
# PART 8 : Chart API
# ==========================================================

@app.route("/chart-data")
def chart_data():

    # --------------------------------------------------------
    # DB 연결
    # --------------------------------------------------------

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""

        SELECT

            created_at,
            price,
            ma20,
            ma60

        FROM eth_price

        ORDER BY id ASC

        LIMIT 300

    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    # --------------------------------------------------------
    # Chart Data
    # --------------------------------------------------------

    labels = []

    prices = []

    ma20 = []

    ma60 = []

    buy = []

    sell = []

    golden = []

    dead = []

    # --------------------------------------------------------
    # 데이터 생성
    # --------------------------------------------------------

    for i, row in enumerate(rows):

        # 시간
        labels.append(
            row["created_at"].strftime("%H:%M:%S")
        )

        # 가격
        price = float(row["price"])

        prices.append(price)

        # 이동평균
        m20 = None
        m60 = None

        if row["ma20"] is not None:
            m20 = float(row["ma20"])

        if row["ma60"] is not None:
            m60 = float(row["ma60"])

        ma20.append(m20)
        ma60.append(m60)

        # 기본값
        buy.append(None)
        sell.append(None)
        golden.append(None)
        dead.append(None)

        # ----------------------------------------------------
        # 첫 번째 데이터는 비교 불가
        # ----------------------------------------------------

        if i == 0:
            continue

        prev20 = ma20[i - 1]
        prev60 = ma60[i - 1]

        # ----------------------------------------------------
        # 이동평균이 없으면 건너뜀
        # ----------------------------------------------------

        if (
            prev20 is None or
            prev60 is None or
            m20 is None or
            m60 is None
        ):
            continue

        # ----------------------------------------------------
        # Golden Cross
        # ----------------------------------------------------

        if prev20 <= prev60 and m20 > m60:

            buy[i] = price

            golden[i] = price

        # ----------------------------------------------------
        # Dead Cross
        # ----------------------------------------------------

        elif prev20 >= prev60 and m20 < m60:

            sell[i] = price

            dead[i] = price

    # --------------------------------------------------------
    # JSON 반환
    # --------------------------------------------------------

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

# ============================================================
# PART 8-1 : WDM Chart
# ============================================================

# ------------------------------------------------------------
# WDM Chart Page
# ------------------------------------------------------------

@app.route("/wdm-chart")
def wdm_chart():

    return render_template("wdm_chart.html")


# ==========================================================
# WDM Chart Data
# 기존 wdm_chart_data() 함수 전체 삭제 후 붙여넣기
# ==========================================================

@app.route("/wdm-chart-data")
def wdm_chart_data():

    try:

        # --------------------------------------------------
        # PostgreSQL 연결
        # --------------------------------------------------
        conn = get_db()

        cur = conn.cursor(cursor_factory=RealDictCursor)

        # --------------------------------------------------
        # 최근 200개 가격 조회
        # --------------------------------------------------
        cur.execute("""

            SELECT

                id,

                price,

                ma20,

                ma60,

                signal,

                created_at

            FROM wdm_price

            ORDER BY id ASC

            LIMIT 200

        """)

        rows = cur.fetchall()

        cur.close()

        conn.close()

        # --------------------------------------------------
        # Chart 데이터 생성
        # --------------------------------------------------
        labels = []

        prices = []

        ma20 = []

        ma60 = []

        buy = []

        sell = []

        golden = []

        dead = []

        # --------------------------------------------------
        # 데이터 변환
        # --------------------------------------------------
        for row in rows:

            # 시간
            labels.append(str(row["created_at"]))

            # 가격
            prices.append(
                float(row["price"])
                if row["price"] is not None
                else None
            )

            # MA20
            ma20.append(
                float(row["ma20"])
                if row["ma20"] is not None
                else None
            )

            # MA60
            ma60.append(
                float(row["ma60"])
                if row["ma60"] is not None
                else None
            )

            signal = row["signal"]

            # BUY
            if signal == "BUY":

                buy.append(float(row["price"]))

            else:

                buy.append(None)

            # SELL
            if signal == "SELL":

                sell.append(float(row["price"]))

            else:

                sell.append(None)

            # GOLDEN
            if signal == "BUY":

                golden.append(float(row["price"]))

            else:

                golden.append(None)

            # DEAD
            if signal == "SELL":

                dead.append(float(row["price"]))

            else:

                dead.append(None)

        # --------------------------------------------------
        # JSON 반환
        # --------------------------------------------------
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

    # ------------------------------------------------------
    # 오류 확인용
    # ------------------------------------------------------
    except Exception as e:

        traceback.print_exc()

        return jsonify({

            "error": str(e)

        }),500
# ============================================================
# Database Initialize
# ============================================================

init_db()



insert_default_portfolio()

insert_default_meme()
    
insert_test_data()
# ==========================================================
# PART 9 : Thread
# ==========================================================

# ============================================================
# Start Auto Save Thread
# ============================================================

if __name__ != "__main__":
    threading.Thread(
        target=auto_save_eth,
        daemon=True
    ).start()
# ==========================================================
# PART 10 : app.run()
# ==========================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )
