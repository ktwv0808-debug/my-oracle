# ============================================================
# PART 1 : Import
# ============================================================

from flask import (
    Flask,
    render_template, 
    request,
    redirect,
    session, 
    jsonify
)
import uuid
import os 
import threading 
import time
from datetime import datetime
import traceback
import requests
import pandas as pd
import base64
from werkzeug.utils import secure_filename
import psycopg2
# ==========================================================
# PostgreSQL Connection Pool
# ==========================================================
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from flask import send_file
from flask_compress import Compress

CACHE = {

    "eth_price": None,
    "eth_time": 0,

    "chart_data": None,
    "chart_time": 0,

    "portfolio": None,
    "portfolio_time": 0,

    "statistics": None,
    "statistics_time": 0,
    # --------------------------------
    # Trading Indicator Cache
    # RSI / MA 계산 캐시
    # --------------------------------

    "rsi": None,
    "rsi_time": 0,

    "ma20": None,
    "ma20_time": 0,

    "ma60": None,
    "ma60_time": 0,
    
    "prev_ma20": None,
    "prev_ma20_time": 0,
    
    "prev_ma60": None,
    "prev_ma60_time": 0,
    "cross_signal": None,
    "cross_signal_time": 0,
    "signal": None,
    "signal_time": 0,
    "wdm_price": None,
    "wdm_price_time": 0,
    # ==========================================================
    # FAQ Cache
    # ==========================================================

    "faq": None,
    "faq_time": 0,

    # ==========================================================
    # Announcement Cache
    # ==========================================================

    "announcement": None,
    "announcement_time": 0,

    # ==========================================================
    # Content Cache
    # ==========================================================

    "content": None,
    "content_time": 0
}


# 캐시 유지 시간(초)
CACHE_TIME = {

    "eth_price": 30,
    "chart_data": 30,
    "portfolio": 30,
    "statistics": 60,
    "rsi": 30,
    "ma20": 30,
    "ma60": 30,
    "prev_ma20": 30,
    "prev_ma60": 30,
    "cross_signal": 30,
    "signal": 30,
    "wdm_price": 30,
    # ==========================================================
    # FAQ Cache Time
    # ==========================================================

    "faq": 300,

    # ==========================================================
    # Announcement Cache Time
    # ==========================================================

    "announcement": 300,

    # ==========================================================
    # Content Cache Time
    # ==========================================================

    "content": 300
}
# ==========================================================
# Access Log Cache
# 동일 방문자 중복 저장 방지
# ==========================================================

ACCESS_LOG_CACHE = {}

ACCESS_LOG_CACHE_SECONDS = 30

# ------------------------------------------------------------
# Flask
# ------------------------------------------------------------

app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static"
)

# ==========================================================
# Static File Cache
# ==========================================================

app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400
# ==========================================================
# Gzip Compression
# ==========================================================

Compress(app)

# ==========================================================
# Compress MIME Types
# ==========================================================

app.config["COMPRESS_MIMETYPES"] = [
    "text/html",
    "text/css",
    "text/xml",
    "application/json",
    "application/javascript",
]

# ==========================================================
# Compression Level
# ==========================================================

app.config["COMPRESS_LEVEL"] = 6

# ==========================================================
# Minimum Size (Bytes)
# ==========================================================

app.config["COMPRESS_MIN_SIZE"] = 500
# ==========================================================
# Home Cache
# 메인 페이지 캐시
# ==========================================================

import time

HOME_CACHE = {

    "data": None,

    "time": 0

}

HOME_CACHE_SECONDS = 30
# ============================================================
# File Upload Setting
# ============================================================

UPLOAD_FOLDER = "static/uploads/content"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# ============================================================
# Allowed Upload Extensions
# ============================================================

ALLOWED_EXTENSIONS = {

    "pdf",

    "doc",

    "docx",

    "xls",

    "xlsx",

    "ppt",

    "pptx",

    "txt",

    "zip",

    "rar",

    "jpg",

    "jpeg",

    "png",

    "gif",

    "hwp",

    "webp"

}

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)
# ------------------------------------------------------------
# Session 암호키
# ------------------------------------------------------------
app.secret_key = "WDM_ADMIN_SECRET_KEY_2026"
# ==========================================================
# Admin Login
# ==========================================================

ADMIN_ID = "admin"
ADMIN_PASSWORD = "1234"
# ==========================================================
# Announcement Admin Account
# 공지사항 관리자 계정
# 붙여넣기 위치 :
# app.secret_key 바로 아래
# ==========================================================

ADMIN2_ID = "admin"

ADMIN2_PASSWORD = "1234"
# ============================================================
# Content Admin Account
# ============================================================

ADMIN3_ID = "admin"

ADMIN3_PASSWORD = "1234"
# ============================================================
# PART 2 : PostgreSQL
# ============================================================
# ============================================================
# Check Allowed File Extension
# ============================================================

def allowed_file(filename):

    return (

        "." in filename

        and

        filename.rsplit(".", 1)[1].lower()

        in ALLOWED_EXTENSIONS

    )
# ------------------------------------------------------------
# PostgreSQL Connection
# ------------------------------------------------------------

# ==========================================================
# PostgreSQL Connection Pool
# ==========================================================

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL is not set.")

db_pool = SimpleConnectionPool(

    minconn=1,

    maxconn=10,

    dsn=DATABASE_URL

)


# ==========================================================
# Get Database Connection
# Connection Pool 사용
# ==========================================================

def get_db():

    return db_pool.getconn()
# ==========================================================
# Return Database Connection
# Connection Pool 반환
# ==========================================================

def close_db(conn):

    if conn:

        db_pool.putconn(conn)
# ==========================================================
# Execute SQL
# INSERT / UPDATE / DELETE
# ==========================================================

def execute(sql, params=None):

    conn = get_db()

    try:

        cur = conn.cursor()

        cur.execute(sql, params)

        conn.commit()

        cur.close()

    finally:

        close_db(conn)


# ==========================================================
# Fetch One Row
# SELECT 1건 조회
# ==========================================================

def fetch_one(sql, params=None):

    conn = get_db()

    try:

        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(sql, params)

        row = cur.fetchone()

        cur.close()

        return row

    finally:

        close_db(conn)


# ==========================================================
# Fetch All Rows
# SELECT 여러건 조회
# ==========================================================

def fetch_all(sql, params=None):

    conn = get_db()

    try:

        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(sql, params)

        rows = cur.fetchall()

        cur.close()

        return rows

    finally:

        close_db(conn)

# ==========================================================
# Portfolio 조회 캐시
# DB 반복 조회 최소화
# ==========================================================

PORTFOLIO_CACHE = {

    "data": None,
    "time": 0

}


PORTFOLIO_CACHE_TIME = 30



def get_cached_portfolio():

    import time


    now = time.time()



    # -------------------------------
    # 캐시 사용
    # -------------------------------

    if PORTFOLIO_CACHE["data"]:

        if now - PORTFOLIO_CACHE["time"] < PORTFOLIO_CACHE_TIME:

            return PORTFOLIO_CACHE["data"]



    # -------------------------------
    # DB 조회
    # -------------------------------

    row = fetch_one("""
        SELECT *
        FROM portfolio
        LIMIT 1
    """)



    PORTFOLIO_CACHE["data"] = row

    PORTFOLIO_CACHE["time"] = now



    return row
# ==========================================================
# GitHub File Upload
# ==========================================================

def upload_file_to_github(file, filename):

    token = os.getenv("GITHUB_TOKEN")

    repo = os.getenv("GITHUB_REPO")

    branch = os.getenv("GITHUB_BRANCH")

    folder = os.getenv("GITHUB_FOLDER")


    # ------------------------------------------------------
    # File Read
    # ------------------------------------------------------

    content = base64.b64encode(
        file.read()
    ).decode("utf-8")


    # ------------------------------------------------------
    # GitHub API URL
    # ------------------------------------------------------

    url = (
        f"https://api.github.com/repos/"
        f"{repo}/contents/"
        f"{folder}/{filename}"
    )


    headers = {

        "Authorization":
        f"Bearer {token}",

        "Accept":
        "application/vnd.github+json"

    }


    data = {

        "message":
        f"Upload {filename}",

        "content":
        content,

        "branch":
        branch

    }


    response = requests.put(

        url,

        headers=headers,

        json=data

    )


    if response.status_code in [200, 201]:


        return (

            f"https://raw.githubusercontent.com/"
            f"{repo}/"
            f"{branch}/"
            f"{folder}/"
            f"{filename}"

        )


    else:

        print(response.text)

        return None

# ==========================================================
# GitHub File Delete
# ==========================================================

def delete_file_from_github(file_url):


    token = os.getenv("GITHUB_TOKEN")

    repo = os.getenv("GITHUB_REPO")

    branch = os.getenv("GITHUB_BRANCH")


    if not file_url:

        return


    filename = file_url.split("/")[-1]


    url = (

        f"https://api.github.com/repos/"
        f"{repo}/contents/"
        f"uploads/{filename}"

    )


    headers = {

        "Authorization":
        f"Bearer {token}",

        "Accept":
        "application/vnd.github+json"

    }


    # ------------------------------------------------------
    # 파일 정보 조회
    # ------------------------------------------------------

    response = requests.get(

        url,

        headers=headers

    )


    if response.status_code != 200:

        return


    sha = response.json()["sha"]


    # ------------------------------------------------------
    # 삭제
    # ------------------------------------------------------

    requests.delete(

        url,

        headers=headers,

        json={

            "message":
            f"Delete {filename}",

            "sha":
            sha,

            "branch":
            branch

        }

    )
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


# ==========================================================
# Announcement Helper Functions
# ==========================================================

# ==========================================================
# Announcement Helper Functions
# ==========================================================

import time


# ----------------------------------------------------------
# 공지 전체 조회 (Cache)
# ----------------------------------------------------------
def fetch_announcements():

    if (

        CACHE["announcement"] is None

        or

        time.time() - CACHE["announcement_time"] > CACHE_TIME["announcement"]

    ):

        CACHE["announcement"] = fetch_all("""

            SELECT *

            FROM announcements

            ORDER BY created_at DESC

        """)

        CACHE["announcement_time"] = time.time()

    return CACHE["announcement"]


# ----------------------------------------------------------
# 공지 1개 조회
# ----------------------------------------------------------
def get_announcement(id):

    return fetch_one("""

        SELECT *

        FROM announcements

        WHERE id=%s

    """,
    (
        id,
    ))


# ----------------------------------------------------------
# 공지 등록
# ----------------------------------------------------------
def add_announcement(title, content):

    execute("""

        INSERT INTO announcements
        (

            title,

            content

        )

        VALUES
        (

            %s,

            %s

        )

    """,
    (
        title,
        content
    ))

    # ------------------------------------------------------
    # Announcement Cache Clear
    # ------------------------------------------------------

    CACHE["announcement"] = None

    CACHE["announcement_time"] = 0


# ----------------------------------------------------------
# 공지 수정
# ----------------------------------------------------------
def update_announcement(id, title, content):

    execute("""

        UPDATE announcements

        SET

            title=%s,

            content=%s,

            updated_at=CURRENT_TIMESTAMP

        WHERE id=%s

    """,
    (
        title,
        content,
        id
    ))

    # ------------------------------------------------------
    # Announcement Cache Clear
    # ------------------------------------------------------

    CACHE["announcement"] = None

    CACHE["announcement_time"] = 0


# ----------------------------------------------------------
# 공지 삭제
# ----------------------------------------------------------
def delete_announcement(id):

    execute("""

        DELETE

        FROM announcements

        WHERE id=%s

    """,
    (
        id,
    ))

    # ------------------------------------------------------
    # Announcement Cache Clear
    # ------------------------------------------------------

    CACHE["announcement"] = None

    CACHE["announcement_time"] = 0
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
    close_db(conn)
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
    
    # ==========================================================
    # Announcement Table
    # 공지사항 테이블 생성
    # init_db() 함수 내부
    # ==========================================================

    cur.execute("""

    CREATE TABLE IF NOT EXISTS announcements(

        id SERIAL PRIMARY KEY,

        title VARCHAR(200) NOT NULL,

        content TEXT NOT NULL,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )

    """)

    # ============================================================
    # Content Table
    # ============================================================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS contents (

        id SERIAL PRIMARY KEY,

        title VARCHAR(255) NOT NULL,

        content TEXT NOT NULL,

        image TEXT,

        file_name TEXT,

        file_path TEXT,

        views INTEGER DEFAULT 0,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)

    # ==========================================================
    # FAQ Table
    # ==========================================================

    cur.execute("""
    CREATE TABLE IF NOT EXISTS faq (

        id SERIAL PRIMARY KEY,

        question TEXT NOT NULL,

        answer TEXT NOT NULL,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)

    # ==========================================================
    # FAQ Table Upgrade
    # ==========================================================

    cur.execute("""
    ALTER TABLE faq
    ADD COLUMN IF NOT EXISTS name TEXT;
    """)

    cur.execute("""
    ALTER TABLE faq
    ADD COLUMN IF NOT EXISTS email TEXT;
    """)

    cur.execute("""
    ALTER TABLE faq
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'WAIT';
    """)

# ==========================================================
# FAQ answer NULL 허용
# ==========================================================

    cur.execute("""

    ALTER TABLE faq
    ALTER COLUMN answer DROP NOT NULL;

    """)

# ==========================================================
# FAQ updated_at 기본값
# ==========================================================

    cur.execute("""

    ALTER TABLE faq
    ALTER COLUMN updated_at
    SET DEFAULT CURRENT_TIMESTAMP;

    """)

  
# ==========================================================
# Access Statistics Table
# 방문자 접속 기록 저장 테이블
# ==========================================================

    execute("""
    CREATE TABLE IF NOT EXISTS access_logs (

        id SERIAL PRIMARY KEY,

        ip TEXT,

        path TEXT,

        user_agent TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )
    """)
# ==========================================================
# Add Country Column
# 방문자 국가 정보 저장 컬럼 추가
# ==========================================================

    execute("""
    ALTER TABLE access_logs
    ADD COLUMN IF NOT EXISTS country TEXT
    """)
    # --------------------------------------------------------
    # WDM PRICE TABLE
    # --------------------------------------------------------

    cur.execute("""

    CREATE TABLE IF NOT EXISTS wdm_price(

        id SERIAL PRIMARY KEY,

        price NUMERIC(18,8),

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )

    """)

     
    
    # ==========================================================
    # WDM PRICE TABLE
    # MA20 컬럼 추가
    # ==========================================================

    cur.execute("""

    ALTER TABLE wdm_price
    ADD COLUMN IF NOT EXISTS ma20 DOUBLE PRECISION;

    """)

    # ==========================================================
    # WDM PRICE TABLE
    # MA60 컬럼 추가
    # ==========================================================

    cur.execute("""

    ALTER TABLE wdm_price
    ADD COLUMN IF NOT EXISTS ma60 DOUBLE PRECISION;

    """)

    # ==========================================================
    # WDM PRICE TABLE
    # SIGNAL 컬럼 추가
    # ==========================================================

    cur.execute("""

    ALTER TABLE wdm_price
    ADD COLUMN IF NOT EXISTS signal VARCHAR(20);

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
    cur.execute("""

    CREATE TABLE IF NOT EXISTS community_links(

        id SERIAL PRIMARY KEY,

        telegram TEXT,

        discord TEXT,

        twitter TEXT,

        youtube TEXT,

        website TEXT

    )

    """)
    conn.commit()

    cur.close()
    
        
    close_db(conn)

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
    close_db(conn)
    
    print("Database Updated")

# ==========================================================
# Save Access Log
# 방문 기록 저장
# ==========================================================

# ==========================================================
# Save Access Log
# 방문 기록 저장
# ==========================================================
def save_access_log():

    try:

        import time

        # ==========================================================
        # Get Real Visitor IP
        # 실제 방문자 IP 추출
        # ==========================================================

        forwarded = request.headers.get(
            "X-Forwarded-For"
        )

        if forwarded:

            ip = forwarded.split(",")[0].strip()

        else:

            ip = request.remote_addr


        # ==========================================================
        # Ignore Localhost
        # 로컬 및 내부 IP 제외
        # ==========================================================

        if ip in (
            "127.0.0.1",
            "::1"
        ):

            return


        # ==========================================================
        # Get Access Information
        # 접속 페이지 및 브라우저 정보
        # ==========================================================

        path = request.path

        agent = request.headers.get(
            "User-Agent",
            ""
        )


        # ==========================================================
        # Ignore Bot / Crawler
        # 봇 및 크롤러 제외
        # ==========================================================

        bot_keywords = [

            "bot",
            "crawl",
            "spider",
            "Go-http-client",
            "python",
            "curl",
            "Render",
            "Uptime",
            "monitor"

        ]


        if any(
            x.lower() in agent.lower()
            for x in bot_keywords
        ):

            return


        # ==========================================================
        # Ignore favicon
        # 파비콘 요청 제외
        # ==========================================================

        if path == "/favicon.ico":

            return


        # ==========================================================
        # Access Log Cache
        # 동일 IP + 동일 URL 30초 중복 저장 방지
        # ==========================================================

        now = time.time()

        cache_key = f"{ip}:{path}"

        if cache_key in ACCESS_LOG_CACHE:

            last_time = ACCESS_LOG_CACHE[cache_key]

            if now - last_time < ACCESS_LOG_CACHE_SECONDS:

                return

        ACCESS_LOG_CACHE[cache_key] = now


        # ==========================================================
        # 오래된 Cache 삭제
        # ==========================================================

        expired_keys = []

        for key, value in ACCESS_LOG_CACHE.items():

            if now - value > ACCESS_LOG_CACHE_SECONDS:

                expired_keys.append(key)

        for key in expired_keys:

            del ACCESS_LOG_CACHE[key]


         # ==========================================================
        # Get Visitor Country
        # 방문자 국가 정보 조회
        #
        # 속도 개선을 위해 임시 비활성화
        # 필요 시 아래 주석(#) 제거 후 사용
        # ==========================================================

        country = "Unknown"

        # try:
        #
        #     response = requests.get(
        #         f"http://ip-api.com/json/{ip}",
        #         timeout=0.5
        #     )
        #
        #     data = response.json()
        #
        #     if data.get("success"):
        #
        #         country = data.get(
        #             "country",
        #             "Unknown"
        #         )
        #
        # except Exception as e:
        #
        #     print(
        #         "COUNTRY LOOKUP ERROR :",
        #         e
        #     )
        #
        #     country = "Unknown"


        # ==========================================================
        # Insert Access Log
        # 방문 기록 저장
        # ==========================================================

        execute(

            """
            INSERT INTO access_logs
            (
                ip,
                country,
                path,
                user_agent
            )
            VALUES
            (%s,%s,%s,%s)
            """,

            (
                ip,
                country,
                path,
                agent
            )

        )


        # ==========================================================
        # Keep Latest 1000 Logs
        # 최근 방문 기록 1000개 유지
        # ==========================================================

        execute(

            """
            DELETE FROM access_logs

            WHERE id NOT IN
            (
                SELECT id
                FROM access_logs
                ORDER BY id DESC
                LIMIT 1000
            )
            """

        )


        print(

            f"ACCESS LOG : {ip} | {country} | {path}"

        )


    except Exception as e:

        import traceback

        traceback.print_exc()

        print(

            "ACCESS LOG ERROR :",

            e

        )
# ==========================================================
# Unique Visitor Count
# 중복 제거 방문자 수 계산
# ==========================================================

def get_unique_visitors():

    result = fetch_one(
        """
        SELECT COUNT(DISTINCT ip) AS cnt
        FROM access_logs
        WHERE created_at::date = CURRENT_DATE
        """
    )

    return result["cnt"]
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
    close_db(conn)
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

    close_db(conn)

# ------------------------------------------------------------
# Insert Default Community
# ------------------------------------------------------------

def insert_default_community():

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""

        INSERT INTO community_links
        (

            telegram,

            discord,

            twitter,

            youtube,

            website

        )

        SELECT

            '',

            '',

            '',

            '',

            ''

        WHERE NOT EXISTS
        (

            SELECT 1

            FROM community_links

        )

    """)

    conn.commit()

    cur.close()

    close_db(conn)
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
    close_db(conn)
    
# ============================================================
# PART 4 : Indicator
# ============================================================
# ==========================================================
# Get ETH Price From CoinGecko
# 이더리움 현재 가격 조회
# ==========================================================
# ==========================================================
# ETH Price Cache
# CoinGecko 호출 최소화
# ==========================================================

ETH_PRICE_CACHE = {

    "price": None,

    "time": 0

}

ETH_CACHE_SECONDS = 30

# ==========================================================
# ETH 가격 조회
# CoinGecko API + 메모리 캐시
# ==========================================================

def get_eth_price():

    import time


    now = time.time()


    # -------------------------------
    # 캐시 데이터 사용
    # -------------------------------

    if CACHE["eth_price"]:

        if now - CACHE["eth_time"] < CACHE_TIME["eth_price"]:

            return CACHE["eth_price"]



    # -------------------------------
    # 실제 API 호출
    # -------------------------------

    try:

        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids":"ethereum",
                "vs_currencies":"usd"
            },
            timeout=5
        )


        data = response.json()

        price = data["ethereum"]["usd"]



        # 캐시 저장

        CACHE["eth_price"] = price
        CACHE["eth_time"] = now


        return price



    except Exception as e:

        print("ETH PRICE ERROR:", e)

        return CACHE["eth_price"]
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

# DB 조회 최소화 (30초 Cache)
# ------------------------------------------------------------
def get_latest_wdm_price():

    import time

    now = time.time()

    # --------------------------------------------------------
    # Cache 확인
    # --------------------------------------------------------

    if CACHE["wdm_price"] is not None:

        if now - CACHE["wdm_price_time"] < CACHE_TIME["wdm_price"]:

            return CACHE["wdm_price"]

    # --------------------------------------------------------
    # DB 연결
    # --------------------------------------------------------

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:

        # ----------------------------------------------------
        # 최신 WDM 가격 조회
        # ----------------------------------------------------

        cur.execute("""

            SELECT
                price

            FROM wdm_price

            ORDER BY id DESC

            LIMIT 1

        """)

        row = cur.fetchone()

        if row is None:

            price = 0.0

        else:

            price = float(row["price"])

        # ----------------------------------------------------
        # Cache 저장
        # ----------------------------------------------------

        CACHE["wdm_price"] = price

        CACHE["wdm_price_time"] = now

        return price

    finally:

        cur.close()

        close_db(conn)
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
    close_db(conn)
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
    close_db(conn)
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
    close_db(conn)

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
    close_db(conn)
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
# ------------------------------------------------------------
# RSI 계산
# DB 조회 최소화 캐시 적용
# ------------------------------------------------------------

def calculate_rsi(period=14):


    import time


    now = time.time()



    # --------------------------------------------------------
    # RSI Cache
    # --------------------------------------------------------

    if CACHE["rsi"] is not None:


        if now - CACHE["rsi_time"] < CACHE_TIME["rsi"]:


            return CACHE["rsi"]



    # --------------------------------------------------------
    # 가격 데이터 조회
    # --------------------------------------------------------

    rows = fetch_all("""

        SELECT price

        FROM eth_price

        ORDER BY id DESC

        LIMIT 100

    """)



    if len(rows) <= period:

        return None



    prices = [

        float(row["price"])

        for row in reversed(rows)

    ]



    gains = []

    losses = []



    for i in range(1, len(prices)):


        diff = prices[i] - prices[i-1]


        if diff >= 0:

            gains.append(diff)

            losses.append(0)

        else:

            gains.append(0)

            losses.append(abs(diff))



    avg_gain = sum(gains[-period:]) / period

    avg_loss = sum(losses[-period:]) / period



    if avg_loss == 0:

        rsi = 100

    else:

        rs = avg_gain / avg_loss

        rsi = 100 - (
            100 / (1 + rs)
        )



    rsi = round(rsi, 2)



    # --------------------------------------------------------
    # 캐시 저장
    # --------------------------------------------------------

    CACHE["rsi"] = rsi

    CACHE["rsi_time"] = now



    return rsi
# ------------------------------------------------------------
# Moving Average
# MA20 / MA60 계산 캐시 적용
# ------------------------------------------------------------

def calculate_ma(period):


    import time


    now = time.time()


    cache_key = f"ma{period}"



    # --------------------------------------------------------
    # 캐시 확인
    # --------------------------------------------------------

    if CACHE.get(cache_key) is not None:


        if now - CACHE.get(
            f"{cache_key}_time",
            0
        ) < CACHE_TIME.get(
            cache_key,
            30
        ):


            return CACHE[cache_key]



    # --------------------------------------------------------
    # DB 조회
    # --------------------------------------------------------

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)



    try:

        cur.execute("""
            SELECT price
            FROM eth_price
            ORDER BY id DESC
            LIMIT %s
        """,
        (
            period,
        ))


        rows = cur.fetchall()



    finally:


        cur.close()

        close_db(conn)



    if len(rows) < period:

        return None



    prices = [

        float(r["price"])

        for r in rows

    ]



    prices.reverse()



    ma = round(
        sum(prices) / period,
        2
    )



    # --------------------------------------------------------
    # 캐시 저장
    # --------------------------------------------------------

    CACHE[cache_key] = ma

    CACHE[f"{cache_key}_time"] = now



    return ma





# ------------------------------------------------------------
# Previous Moving Average
# 이전 MA 계산 캐시 적용
# ------------------------------------------------------------

def calculate_previous_ma(period):


    import time


    now = time.time()


    cache_key = f"prev_ma{period}"



    # --------------------------------------------------------
    # 캐시 확인
    # --------------------------------------------------------

    if CACHE.get(cache_key) is not None:


        if now - CACHE.get(
            f"{cache_key}_time",
            0
        ) < CACHE_TIME.get(
            cache_key,
            30
        ):


            return CACHE[cache_key]



    # --------------------------------------------------------
    # DB 조회
    # --------------------------------------------------------

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)



    try:

        cur.execute("""
            SELECT price
            FROM eth_price
            ORDER BY id DESC
            LIMIT %s
        """,
        (
            period + 1,
        ))


        rows = cur.fetchall()



    finally:


        cur.close()

        close_db(conn)



    if len(rows) < period + 1:

        return None



    prices = [

        float(r["price"])

        for r in rows

    ]



    prices.reverse()



    previous_prices = prices[:-1]



    previous_ma = round(

        sum(previous_prices) / period,

        2

    )



    # --------------------------------------------------------
    # 캐시 저장
    # --------------------------------------------------------

    CACHE[cache_key] = previous_ma

    CACHE[f"{cache_key}_time"] = now



    return previous_ma
# ------------------------------------------------------------
# Cross Signal
# MA20 / MA60 실제 교차 계산
# ------------------------------------------------------------
# ------------------------------------------------------------
# Cross Signal
# MA20 / MA60 실제 교차 계산
# DB 조회 최소화 캐시 적용
# ------------------------------------------------------------

def get_cross_signals():


    import time


    now = time.time()



    # --------------------------------------------------------
    # Cross Signal Cache 확인
    # --------------------------------------------------------

    if CACHE["cross_signal"] is not None:


        if now - CACHE["cross_signal_time"] < CACHE_TIME["cross_signal"]:


            return CACHE["cross_signal"]



    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)



    try:


        # ----------------------------------------------------
        # 최근 두 개 데이터만 조회
        # ----------------------------------------------------

        cur.execute("""
            SELECT
                id,
                ma20,
                ma60,
                price

            FROM eth_price

            ORDER BY id DESC

            LIMIT 2

        """)


        rows = cur.fetchall()



    finally:


        cur.close()

        close_db(conn)



    if len(rows) < 2:


        return "HOLD"



    # 최신순으로 가져오기 때문에 역순 변경

    rows.reverse()



    prev = rows[0]

    curr = rows[1]



    if (

        prev["ma20"] is None or

        prev["ma60"] is None or

        curr["ma20"] is None or

        curr["ma60"] is None

    ):

        signal = "HOLD"



    else:


        prev20 = float(prev["ma20"])

        prev60 = float(prev["ma60"])


        curr20 = float(curr["ma20"])

        curr60 = float(curr["ma60"])



        # ------------------------------------------------
        # Golden Cross
        # ------------------------------------------------

        if prev20 <= prev60 and curr20 > curr60:


            signal = "BUY"



        # ------------------------------------------------
        # Dead Cross
        # ------------------------------------------------

        elif prev20 >= prev60 and curr20 < curr60:


            signal = "SELL"



        else:


            signal = "HOLD"



    # --------------------------------------------------------
    # Cache 저장
    # --------------------------------------------------------

    CACHE["cross_signal"] = signal

    CACHE["cross_signal_time"] = now



    return signal

# ------------------------------------------------------------
# Trading Signal
# ------------------------------------------------------------
# ------------------------------------------------------------
# Trading Signal
# RSI / MA / Cross Signal 캐시 적용
# ------------------------------------------------------------
def generate_signal():

    import time

    now = time.time()

    # --------------------------------------------------------
    # Signal Cache
    # --------------------------------------------------------

    if CACHE["signal"] is not None:

        if now - CACHE["signal_time"] < CACHE_TIME["signal"]:

            return CACHE["signal"]

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
    # 데이터 부족
    # --------------------------------------------------------

    if ma20 is None or ma60 is None:

        result = {

            "signal": "HOLD",

            "price": get_latest_price(),

            "rsi": rsi,

            "ma20": ma20,

            "ma60": ma60

        }

        CACHE["signal"] = result
        CACHE["signal_time"] = now

        return result

    # --------------------------------------------------------
    # Cross Signal
    # --------------------------------------------------------

    signal = get_cross_signals()

    # --------------------------------------------------------
    # RSI 보강
    # --------------------------------------------------------

    if signal == "BUY":

        if rsi is not None and rsi < 30:

            signal = "STRONG BUY"

    elif signal == "SELL":

        if rsi is not None and rsi > 70:

            signal = "STRONG SELL"

    # --------------------------------------------------------
    # 결과
    # --------------------------------------------------------

    result = {

        "signal": signal,

        "price": get_latest_price(),

        "rsi": rsi,

        "ma20": ma20,

        "ma60": ma60

    }

    # --------------------------------------------------------
    # Cache 저장
    # --------------------------------------------------------

    CACHE["signal"] = result
    CACHE["signal_time"] = now

    return result
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
            # --------------------------------------------------------
            # Chart Cache 초기화
            # 새로운 ETH 데이터 반영
            # --------------------------------------------------------

            CACHE["chart_data"] = None

            CACHE["chart_time"] = 0
            # --------------------------------------------------------
            # Indicator Cache 초기화
            # 새로운 ETH 가격 반영
            # RSI / MA / Cross Signal 초기화
            # --------------------------------------------------------

            # RSI Cache 초기화

            CACHE["rsi"] = None
            CACHE["rsi_time"] = 0



            # 현재 MA Cache 초기화

            CACHE["ma20"] = None
            CACHE["ma20_time"] = 0


            CACHE["ma60"] = None
            CACHE["ma60_time"] = 0



            # 이전 MA Cache 초기화
            # Golden Cross / Dead Cross 계산용

            CACHE["prev_ma20"] = None
            CACHE["prev_ma20_time"] = 0


            CACHE["prev_ma60"] = None
            CACHE["prev_ma60_time"] = 0



            # Cross Signal Cache 초기화
            # BUY / SELL / HOLD 재계산

            CACHE["cross_signal"] = None
            CACHE["cross_signal_time"] = 0

            # Signal Cache 초기화

            CACHE["signal"] = None
            CACHE["signal_time"] = 0

            # --------------------------------------------------------
            # WDM Price Cache 초기화
            # --------------------------------------------------------

            CACHE["wdm_price"] = None
            CACHE["wdm_price_time"] = 0

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

            close_db(conn)
            
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
# DB 조회 최소화 캐시 적용
# --------------------------------------

def calculate_portfolio():

    import time


    now = time.time()


    # --------------------------------------------------------
    # Portfolio 계산 결과 캐시 사용
    # 30초 동안 DB 조회 생략
    # --------------------------------------------------------

    if CACHE["portfolio"]:

        if now - CACHE["portfolio_time"] < CACHE_TIME["portfolio"]:

            return CACHE["portfolio"]



    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)



    try:


        # --------------------------------------------------------
        # Portfolio 데이터 조회
        # --------------------------------------------------------

        cur.execute("""
            SELECT *
            FROM portfolio
            LIMIT 1
        """)


        portfolio = cur.fetchone()



        # --------------------------------------------------------
        # Portfolio가 없으면 기본 생성
        # --------------------------------------------------------

        if portfolio is None:


            cur.execute("""
                INSERT INTO portfolio
                (
                    cash,
                    eth,
                    wdm,
                    avg_price
                )
                VALUES
                (
                    100000,
                    0,
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



        # --------------------------------------------------------
        # 최신 ETH 가격 조회
        # --------------------------------------------------------

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
        # Portfolio 기본 값
        # --------------------------------------------------------

        cash = float(portfolio["cash"])

        eth = float(portfolio["eth"])

        wdm = float(portfolio["wdm"])

        avg_price = float(portfolio["avg_price"])



        # --------------------------------------------------------
        # ETH 평가금액
        # --------------------------------------------------------

        asset_value = eth * current_price



        # --------------------------------------------------------
        # WDM 가격 조회
        # --------------------------------------------------------

        wdm_price = get_latest_wdm_price()



        # --------------------------------------------------------
        # WDM 평가금액
        # --------------------------------------------------------

        wdm_value = wdm * wdm_price



        # --------------------------------------------------------
        # 총 자산
        # --------------------------------------------------------

        total_assets = (
            cash
            + asset_value
            + wdm_value
        )



        # --------------------------------------------------------
        # 수익 계산
        # --------------------------------------------------------

        if eth > 0:

            profit = (
                asset_value
                - (eth * avg_price)
            )

        else:

            profit = 0



        # --------------------------------------------------------
        # ROI 계산
        # --------------------------------------------------------

        if eth > 0 and avg_price > 0:

            roi = (
                (current_price - avg_price)
                /
                avg_price
            ) * 100

        else:

            roi = 0



        # --------------------------------------------------------
        # 결과 저장
        # --------------------------------------------------------

        result = {


            "cash": round(cash, 2),


            "wdm": round(wdm, 2),


            "eth": round(eth, 8),


            "wdm_price": round(wdm_price, 8),


            "wdm_value": round(wdm_value, 2),


            "avg_price": round(avg_price, 2),


            "current_price": round(current_price, 2),


            "asset_value": round(asset_value, 2),


            "total_assets": round(total_assets, 2),


            "profit": round(profit, 2),


            "roi": round(roi, 2)

        }



        # --------------------------------------------------------
        # Portfolio 캐시 저장
        # --------------------------------------------------------

        CACHE["portfolio"] = result

        CACHE["portfolio_time"] = now



        return result



    finally:


        cur.close()

        close_db(conn)
# ------------------------------------------------------------
# BUY ETH
# Portfolio 현금을 이용하여 ETH 매수
# DB 조회 최소화 + Portfolio 캐시 초기화
# ------------------------------------------------------------

def buy_eth(buy_percent=20):


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
        # ETH 보유중이면 매수 금지
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
        # 매수 금액 계산
        # ----------------------------------------------------

        trade_amount = round(
            cash * buy_percent / 100,
            2
        )


        if trade_amount <= 0:

            return None



        # ----------------------------------------------------
        # ETH 수량 계산
        # ----------------------------------------------------

        quantity = trade_amount / current_price



        # ----------------------------------------------------
        # Portfolio 계산
        # ----------------------------------------------------

        new_cash = cash - trade_amount

        new_eth = eth + quantity



        # ----------------------------------------------------
        # 평균 매수가
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
        # Portfolio 업데이트
        # ----------------------------------------------------

        cur.execute("""
            UPDATE portfolio

            SET
                cash=%s,
                eth=%s,
                avg_price=%s

            WHERE id = (
                SELECT id
                FROM portfolio
                LIMIT 1
            )

        """,
        (
            new_cash,
            new_eth,
            new_avg_price
        ))



        conn.commit()



        # ----------------------------------------------------
        # Portfolio 캐시 초기화
        # ----------------------------------------------------

        CACHE["portfolio"] = None

        CACHE["portfolio_time"] = 0



        print("=================================")

        print("AUTO BUY COMPLETE")

        print(f"PRICE      : {current_price:.2f}")

        print(f"QUANTITY   : {quantity:.8f}")

        print(f"AMOUNT     : {trade_amount:.2f}")

        print(f"CASH LEFT  : {new_cash:.2f}")

        print("=================================")



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

        close_db(conn)





# ------------------------------------------------------------
# SELL ETH
# Portfolio 보유 ETH 전량 매도
# 실현손익 계산
# DB 조회 최소화 + Portfolio 캐시 초기화
# ------------------------------------------------------------

def sell_eth():


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
        # ETH 없으면 매도 불가
        # ----------------------------------------------------

        if eth <= 0:

            print("SELL SKIP : No ETH")

            return None



        # ----------------------------------------------------
        # 현재 ETH 가격
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
        # 매도 금액
        # ----------------------------------------------------

        trade_amount = eth * current_price



        # ----------------------------------------------------
        # 손익 계산
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

                /

                avg_price

            ) * 100

        else:

            roi = 0



        # ----------------------------------------------------
        # Portfolio 변경
        # ----------------------------------------------------

        new_cash = cash + trade_amount

        new_eth = 0

        new_avg_price = 0



        # ----------------------------------------------------
        # Portfolio 업데이트
        # ----------------------------------------------------

        cur.execute("""
            UPDATE portfolio

            SET

                cash=%s,

                eth=%s,

                avg_price=%s

            WHERE id = (
                SELECT id
                FROM portfolio
                LIMIT 1
            )

        """,
        (
            new_cash,
            new_eth,
            new_avg_price
        ))



        conn.commit()



        # ----------------------------------------------------
        # Portfolio 캐시 초기화
        # ----------------------------------------------------

        CACHE["portfolio"] = None

        CACHE["portfolio_time"] = 0



        print("=================================")

        print("AUTO SELL COMPLETE")

        print(f"SELL PRICE : {current_price:.2f}")

        print(f"QUANTITY   : {eth:.8f}")

        print(f"AMOUNT     : {trade_amount:.2f}")

        print(f"PROFIT     : {profit:.2f}")

        print(f"ROI        : {roi:.2f}%")

        print("=================================")



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

        close_db(conn)
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

        close_db(conn)
        
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

        close_db(conn)
        
        print("AUTO SELL SUCCESS")

        return True

   # --------------------------------------------------------
    # HOLD
    # --------------------------------------------------------

    elif signal == "HOLD":

        print("AUTO TRADE : HOLD")

        # ----------------------------------------------------
        # DB 연결
        # ----------------------------------------------------

        conn = get_db()

        cur = conn.cursor()

        # ----------------------------------------------------
        # HOLD 기록 저장
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

            "HOLD",

            price,

            0,

            0,

            0,

            0,

            "AUTO",

            rsi,

            ma20,

            ma60

        ))

        conn.commit()

        cur.close()

        close_db(conn)
        
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

# ==========================================================
# Home
# Main Page (120 Seconds Cache)
# ==========================================================

@app.route("/")
def home():

    global HOME_CACHE

    current_time = time.time()

    # ==========================================================
    # Home Cache
    # 120초 동안 캐시 사용
    # ==========================================================

    if (

        HOME_CACHE["data"] is not None

        and

        current_time - HOME_CACHE["time"] < 120

    ):

        donations = HOME_CACHE["data"]

    else:

        # ==========================================================
        # Donation Records
        # 기부 내역 조회
        # ==========================================================

        conn = get_db()

        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""

            SELECT
                quarter,
                net_profit,
                donation,
                proof

            FROM donation_records

            ORDER BY id DESC

        """)

        donations = cur.fetchall()

        cur.close()

        close_db(conn)

        # ==========================================================
        # Cache Save
        # 캐시에 저장
        # ==========================================================

        HOME_CACHE["data"] = donations

        HOME_CACHE["time"] = current_time

    # ==========================================================
    # Main Page
    # 메인 페이지 출력
    # ==========================================================

    return render_template(

        "donation.html",

        donations=donations

    )
# ------------------------------------------------------------
# Donation
# ------------------------------------------------------------
@app.route("/donation")
def donation():

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM donation_records
        ORDER BY id DESC
    """)

    donations = cur.fetchall()

    cur.close()
    close_db(conn)
    
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


# ------------------------------------------------------------
# Whitepaper
# ------------------------------------------------------------
@app.route("/whitepaper")
def whitepaper():

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM donation_records
        ORDER BY id DESC
    """)

    donations = cur.fetchall()

    cur.close()
    close_db(conn)

    return render_template(
        "whitepaper.html",
        donations=donations
    )

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

    close_db(conn)


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
    close_db(conn)
    
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
    close_db(conn)
    
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
    close_db(conn)
    
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

# ==========================================================
# Admin Login
# ==========================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_ID and password == ADMIN_PASSWORD:

            session["admin"] = True

            return redirect("/admin/dashboard")
        
        return render_template(
            "admin_login.html",
            error="Invalid Username or Password"
        )

    return render_template("admin_login.html")


# ==========================================================
# Admin Dashboard
# ==========================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    if not session.get("admin"):
        return redirect("/admin/login")

    return render_template("admin_dashboard.html")

# ==========================================================
# Admin Logout
# ==========================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop("admin", None)

    return redirect("/admin/login")


# ==========================================================
# Announcement Page
# ==========================================================

# ==========================================================
# Announcement
# 일반 사용자 공지 목록
# 붙여넣기 위치 :
# 기존 @app.route("/announcement") 삭제 후
# ==========================================================

@app.route("/announcement")
def announcement():

    rows = fetch_all("""

        SELECT *

        FROM announcements

        ORDER BY created_at DESC

    """)

    return render_template(

        "announcement.html",

        rows=rows

    )
# ==========================================================
# Admin Announcement CMS
# 관리자 전용 공지 관리
# 붙여넣기 위치 :
# @app.route("/announcement/<int:id>") 아래
# ==========================================================

@app.route("/admin2/announcement", methods=["GET", "POST"])
def admin2_announcement():

  
    

    # ==========================================================
    # Add / Update
    # ==========================================================
    if request.method == "POST":

        action = request.form.get("action")

        title = request.form["title"]

        content = request.form["content"]

        # 등록
        if action == "add":

            add_announcement(title, content)

        # 수정
        elif action == "edit":

            announcement_id = request.form["id"]

            update_announcement(
                announcement_id,
                title,
                content
            )

        return redirect("/admin2/announcement")

    # ==========================================================
    # Edit Mode
    # ==========================================================
    edit_id = request.args.get("edit")

    edit_row = None

    if edit_id:
        edit_row = get_announcement(edit_id)

    # ----------------------------------------------------------
    # 공지 목록
    # ----------------------------------------------------------
    rows = fetch_all("""

        SELECT *

        FROM announcements

        ORDER BY id DESC

    """)

    return render_template(

        "admin2_announcement.html",

        rows=rows,

        edit_row=edit_row

    )
# ==========================================================
# Announcement Detail
# 일반 사용자 공지 상세보기
# 붙여넣기 위치 :
# @app.route("/announcement") 바로 아래
# ==========================================================

@app.route("/announcement/<int:id>")
def announcement_detail(id):

    row = get_announcement(id)

    if row is None:

        return "Announcement Not Found", 404

    return render_template(

        "announcement_detail.html",

        row=row

    )

# ==========================================================
# Announcement Add
# 관리자 공지 등록
# 붙여넣기 위치 :
# @app.route("/announcement") 바로 아래
# ==========================================================

@app.route("/announcement/add", methods=["GET", "POST"])
def announcement_add():

    # ----------------------------------------------------------
    # 관리자 로그인 확인
    # ----------------------------------------------------------
    if not session.get("admin"):

        return redirect("/admin/login")

    if request.method == "POST":

        title = request.form["title"]
        content = request.form["content"]

        add_announcement(title, content)

        return redirect("/announcement")

    return render_template("announcement_add.html")
# ==========================================================
# Announcement Edit
# 공지 수정
# ==========================================================

@app.route("/announcement/edit/<int:id>", methods=["GET", "POST"])
def edit_announcement_route(id):

    # ----------------------------------------------------------
    # 관리자 로그인 확인
    # ----------------------------------------------------------
    if not session.get("admin"):
        return redirect("/admin/login")

    if request.method == "POST":

        title = request.form["title"]
        content = request.form["content"]

        update_announcement(id, title, content)

        return redirect("/announcement")

    row = get_announcement(id)

    return render_template(
        "announcement_edit.html",
        row=row
    )
# ==========================================================
# Admin2 Announcement Delete
# ==========================================================

@app.route("/admin2/announcement/delete/<int:id>")
def admin2_delete_announcement(id):

    # 관리자 로그인 확인
    if not session.get("admin"):
        return redirect("/admin/login")

    delete_announcement(id)

    # 관리자 목록으로 이동
    return redirect("/admin2/announcement")
# ==========================================================
# Admin Announcement Detail
# ==========================================================

@app.route("/admin2/announcement/<int:id>")
def admin2_announcement_detail(id):

    if not session.get("admin"):
        return redirect("/admin/login")
    row = get_announcement(id)

    return render_template(
        "admin2_announcement_detail.html",
        row=row
    )
# ============================================================
# Admin2 Content Management
# Content 등록 / 수정 / 삭제
# ============================================================

@app.route("/admin3/content", methods=["GET", "POST"])
def admin_content():

    # --------------------------------------------------------
    # Admin3 Login Check
    # --------------------------------------------------------

    if not session.get("admin"):

        return redirect("/admin/login")

    # --------------------------------------------------------
    # Content Delete
    # DB + Uploaded File 삭제
    # --------------------------------------------------------

    delete_id = request.args.get("delete")


    if delete_id:


        # ----------------------------------------------------
        # 1. 삭제할 파일 정보 조회
        # ----------------------------------------------------

        file_info = fetch_one("""
            SELECT file_path
            FROM contents
            WHERE id=%s

        """,
        (
            delete_id,
        ))



        # ----------------------------------------------------
        # 2. 실제 업로드 파일 삭제
        # ----------------------------------------------------

        if file_info and file_info["file_path"]:


            delete_file_from_github(

                file_info["file_path"]

            )


        # ----------------------------------------------------
        # 3. PostgreSQL 데이터 삭제
        # ----------------------------------------------------

        execute("""
            DELETE FROM contents
            WHERE id=%s

        """,
        (
            delete_id,
        ))

        # ----------------------------------------------------
        # Content Cache Clear
        # ----------------------------------------------------

        CACHE["content"] = None

        CACHE["content_time"] = 0

        return redirect(
            "/admin3/content"
        )



    # --------------------------------------------------------
    # Content Add / Edit
    # --------------------------------------------------------

    if request.method == "POST":

        action = request.form.get("action")


        # ----------------------------------------------------
        # Add Content
        # ----------------------------------------------------

        if action == "add":


            upload_file = request.files.get("file")


            file_name = None

            file_path = None



            # ------------------------------------------------
            # File Upload
            # 랜덤 파일명 생성
            # ------------------------------------------------

            if upload_file and upload_file.filename:


                # -----------------------------------------------
                # Extension Check
                # -----------------------------------------------

                if not allowed_file(upload_file.filename):

                    return """
                    <h3>
                    Upload Failed
                    <br><br>
                    File type is not allowed.
                    </h3>
                    """


                # ----------------------------------------------------
                # Original File Name
                # ----------------------------------------------------

                original_name = upload_file.filename


                # ----------------------------------------------------
                # Extension
                # ----------------------------------------------------

                ext = os.path.splitext(
                    upload_file.filename
                )[1]


                # ----------------------------------------------------
                # File Name Length Limit
                # ----------------------------------------------------

                if len(original_name) > 100:

                    original_name = original_name[:100]



                # ----------------------------------------------------
                # Random File Name
                # ----------------------------------------------------

                random_name = (
                    str(uuid.uuid4())
                    +
                    ext
                )



                # ----------------------------------------------------
                # Display File Name
                # ----------------------------------------------------

                file_name = original_name



                # ----------------------------------------------------
                # GitHub Upload
                # ----------------------------------------------------

                github_url = upload_file_to_github(
                    upload_file,
                    random_name
                )


                file_path = github_url



            # ----------------------------------------------------
            # Insert Content
            # ----------------------------------------------------

            execute("""
                INSERT INTO contents
                (
                    title,
                    content,
                    image,
                    file_name,
                    file_path
                )

                VALUES
                (%s,%s,%s,%s,%s)

            """,
            (

                request.form["title"],

                request.form["content"],

                request.form.get("image"),

                file_name,

                file_path

            ))



            # ----------------------------------------------------
            # Content Cache Clear
            # ----------------------------------------------------

            CACHE["content"] = None

            CACHE["content_time"] = 0



        # ----------------------------------------------------
        # Edit Content
        # ----------------------------------------------------

        elif action == "edit":


            execute("""
                UPDATE contents

                SET

                    title=%s,

                    content=%s,

                    image=%s,

                    updated_at=CURRENT_TIMESTAMP

                WHERE id=%s

            """,
            (

                request.form["title"],

                request.form["content"],

                request.form.get("image"),

                request.form["id"]

            ))



            # ----------------------------------------------------
            # Content Cache Clear
            # ----------------------------------------------------

            CACHE["content"] = None

            CACHE["content_time"] = 0



        return redirect(
            "/admin3/content"
        )
    # --------------------------------------------------------
    # Content List
    # --------------------------------------------------------

    rows = fetch_all("""
        SELECT *
        FROM contents
        ORDER BY id DESC

    """)



    edit_row = None


    edit_id = request.args.get("edit")



    if edit_id:


        edit_row = fetch_one("""
            SELECT *
            FROM contents
            WHERE id=%s

        """,
        (
            edit_id,
        ))



    return render_template(
        "admin3_content.html",

        rows=rows,

        edit_row=edit_row

    )
# ============================================================
# Admin3 Content Detail
# ============================================================

@app.route("/admin3/content/<int:content_id>")
def admin3_content_detail(content_id):

    if not session.get("admin"):

        return redirect("/admin/login")

    row = fetch_one("""
        SELECT *
        FROM contents
        WHERE id=%s
    """, (
        content_id,
    ))

    if not row:
        return "Content Not Found"

    return render_template(
        "admin3_content_detail.html",
        row=row
    )
@app.route("/content")
def content():

    # --------------------------------------------------------
    # Content Cache
    # --------------------------------------------------------

    if (

        CACHE["content"] is None

        or

        time.time() - CACHE["content_time"] > CACHE_TIME["content"]

    ):

        CACHE["content"] = fetch_all("""

            SELECT

                id,

                title,

                image,

                file_name,

                file_path,

                views,

                created_at

            FROM contents

            ORDER BY id DESC

        """)

        CACHE["content_time"] = time.time()


    rows = CACHE["content"]


    return render_template(

        "content.html",

        rows=rows

    )

# ============================================================
# Content Detail
# 콘텐츠 상세보기
# 조회수 증가 + 파일 다운로드
# ============================================================

@app.route("/content/<int:id>")
def content_detail(id):


    # --------------------------------------------------------
    # Content 조회
    # --------------------------------------------------------

    row = fetch_one("""
        SELECT *
        FROM contents
        WHERE id=%s

    """,
    (
        id,
    ))



    # --------------------------------------------------------
    # Content 존재 확인
    # --------------------------------------------------------

    if row is None:

        return "Content Not Found", 404



    # --------------------------------------------------------
    # 조회수 증가
    # --------------------------------------------------------

    execute("""
        UPDATE contents

        SET views = views + 1

        WHERE id=%s

    """,
    (
        id,
    ))

   # --------------------------------------------------------
   # Content Cache Clear
   # --------------------------------------------------------

   CACHE["content"] = None

   CACHE["content_time"] = 0

    # --------------------------------------------------------
    # 상세 페이지 출력
    # --------------------------------------------------------

    return render_template(
        "content_detail.html",

        row=row

    )


# ------------------------------------------------------------
# Content Download (GitHub)
# ------------------------------------------------------------
@app.route("/download/content/<int:content_id>")
def download_content(content_id):

    row = fetch_one("""
        SELECT *
        FROM contents
        WHERE id=%s
    """,
    (
        content_id,
    ))

    if not row:

        return "Not Found"


    # --------------------------------------------------------
    # GitHub File Download
    # --------------------------------------------------------

    response = requests.get(
        row["file_path"]
    )

    if response.status_code != 200:

        return "File Not Found"


    # --------------------------------------------------------
    # Original File Name Download
    # --------------------------------------------------------

    from io import BytesIO

    return send_file(

        BytesIO(response.content),

        as_attachment=True,

        download_name=row["file_name"]

    )

# ==========================================================
# FAQ
# Public FAQ Page
# ==========================================================

# ==========================================================
# FAQ
# Public FAQ Page
# ==========================================================

@app.route("/faq", methods=["GET", "POST"])
def faq():

    # ------------------------------------------------------
    # Question Registration
    # ------------------------------------------------------
    if request.method == "POST":

        execute("""
            INSERT INTO faq
            (
                name,
                email,
                question,
                status
            )
            VALUES
            (%s,%s,%s,'WAIT')
        """,
        (
            request.form["name"],
            request.form["email"],
            request.form["question"]
        ))

        # --------------------------------------------------
        # FAQ Cache Clear
        # --------------------------------------------------

        CACHE["faq"] = None

        CACHE["faq_time"] = 0

        return redirect("/faq")

    # ------------------------------------------------------
    # FAQ Cache
    # ------------------------------------------------------

    if (

        CACHE["faq"] is None

        or

        time.time() - CACHE["faq_time"] > CACHE_TIME["faq"]

    ):

        CACHE["faq"] = fetch_all("""

            SELECT *

            FROM faq

            ORDER BY id DESC

        """)

        CACHE["faq_time"] = time.time()

    faqs = CACHE["faq"]

    return render_template(

        "faq.html",

        faqs=faqs

    )
# ==========================================================
# FAQ CMS
# 관리자 FAQ 관리
# ==========================================================

@app.route("/admin/faq", methods=["GET", "POST"])
def admin_faq():

    if not session.get("admin"):
        return redirect("/admin/login")

    # ------------------------------------------------------
    # POST
    # ------------------------------------------------------
    if request.method == "POST":

        action = request.form.get("action")
        question = request.form.get("question")
        answer = request.form.get("answer")

        # -------------------------------
        # FAQ 등록
        # -------------------------------
        if action == "add":

            execute("""
                INSERT INTO faq
                (
                    question,
                    answer
                )
                VALUES
                (%s,%s)
            """,
            (
                question,
                answer
            ))

            # ------------------------------------------------------
            # FAQ Cache Clear
            # ------------------------------------------------------

            CACHE["faq"] = None

            CACHE["faq_time"] = 0
  
        # ------------------------------------------------------
        # FAQ Answer
        # Administrator writes an answer
        # ------------------------------------------------------

        elif action == "edit":

            execute("""

                UPDATE faq

                SET

                    answer=%s,

                    status='ANSWERED',

                    updated_at=CURRENT_TIMESTAMP

                WHERE id=%s

            """,
            (
                answer,
                request.form.get("id")
            ))
            # ------------------------------------------------------
            # FAQ Cache Clear
            # ------------------------------------------------------

            CACHE["faq"] = None

            CACHE["faq_time"] = 0
        return redirect("/admin/faq")

    # ------------------------------------------------------
    # 수정모드
    # ------------------------------------------------------
    edit_row = None

    edit_id = request.args.get("edit")

    if edit_id:

        edit_row = fetch_one("""
            SELECT *
            FROM faq
            WHERE id=%s
        """,
        (
            edit_id,
        ))

    rows = fetch_all("""
        SELECT *
        FROM faq
        ORDER BY id DESC
    """)

    return render_template(
        "admin_faq.html",
        rows=rows,
        edit_row=edit_row
    )
# ==========================================================
# FAQ Delete
# ==========================================================

@app.route("/admin/faq/delete/<int:id>")
def admin_delete_faq(id):

    if not session.get("admin"):
        return redirect("/admin/login")

    execute("""

        DELETE FROM faq

        WHERE id=%s

    """,
    (
        id,
    ))
    # ------------------------------------------------------
    # FAQ Cache Clear
    # ------------------------------------------------------

    CACHE["faq"] = None

    CACHE["faq_time"] = 0
    return redirect("/admin/faq")


# ==========================================================
# FAQ Detail
# ==========================================================

@app.route("/faq/<int:id>")
def faq_detail(id):

    row = fetch_one("""

        SELECT *

        FROM faq

        WHERE id=%s

    """,
    (
        id,
    ))

    if not row:

        return "FAQ Not Found"

    return render_template(

        "faq_detail.html",

        row=row

    )


# ==========================================================
# Admin FAQ Detail
# ==========================================================

@app.route("/admin/faq/<int:id>")
def admin_faq_detail(id):

    if not session.get("admin"):
        return redirect("/admin/login")

    row = fetch_one("""

        SELECT *

        FROM faq

        WHERE id=%s

    """,
    (
        id,
    ))

    if not row:

        return "FAQ Not Found"

    return render_template(

        "admin_faq_detail.html",

        row=row

    )
# ==========================================================
# Access Tracking
# ==========================================================

@app.before_request
def track_access():

    # 관리자 페이지 제외
    if not request.path.startswith("/admin"):

        save_access_log()

# ==========================================================
# Admin Access Statistics
# ==========================================================

@app.route("/admin/statistics")
def admin_statistics():

    if not session.get("admin"):

        return redirect("/admin/login")


    total = fetch_one(
        """
        SELECT COUNT(*) AS cnt
        FROM access_logs
        """
    )


    today = fetch_one(
        """
        SELECT COUNT(*) AS cnt
        FROM access_logs
        WHERE created_at::date =
        CURRENT_DATE
        """
    )


    pages = fetch_all(
        """
        SELECT
        path,
        COUNT(*) AS cnt

        FROM access_logs

        GROUP BY path

        ORDER BY cnt DESC

        LIMIT 10
        """
    )


# ==========================================================
# Daily Visitor Statistics
# 일별 방문 통계
# ==========================================================

    daily_stats = fetch_all(
        """
        SELECT

        created_at::date AS day,

        COUNT(DISTINCT ip) AS visitors


        FROM access_logs


        GROUP BY day


        ORDER BY day DESC


        LIMIT 7

        """
    )

# ==========================================================
# Monthly Visitor Statistics
# 월별 방문 통계
# ==========================================================

    monthly_stats = fetch_all(
        """
        SELECT

        TO_CHAR(created_at,'YYYY-MM') AS month,

        COUNT(DISTINCT ip) AS visitors


        FROM access_logs


        GROUP BY month


        ORDER BY month DESC


        LIMIT 12

        """
    )

# ==========================================================
# Country Visitor Statistics
# 국가별 방문 통계
# ==========================================================

    country_stats = fetch_all(
        """
        SELECT

        country,

        COUNT(DISTINCT ip) AS visitors


        FROM access_logs


        WHERE country IS NOT NULL


        GROUP BY country


        ORDER BY visitors DESC


        LIMIT 10

        """
    )
    logs = fetch_all(
        """
        SELECT *
        FROM access_logs

        ORDER BY id DESC

        LIMIT 20
        """
    )

# ==========================================================
# Render Access Statistics Page
# 접속통계 페이지 출력
# ==========================================================

    return render_template(
        "admin_statistics.html",
        total=total,
        today=today,
        pages=pages,
        daily_stats=daily_stats,
        monthly_stats=monthly_stats,
        country_stats=country_stats,
        logs=logs
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

    if not admin_required():

        return redirect("/admin/login")

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

    keep_latest_rows("donation_records")

    return redirect("/admin/dashboard")

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

# ------------------------------------------------------------
# Community Management
# 관리자 페이지
# ------------------------------------------------------------

@app.route("/admin/community")
def admin_community():

    # --------------------------------------------------------
    # 관리자 로그인 확인
    # --------------------------------------------------------

    if not admin_required():

        return redirect(
            "/admin/login"
        )


    community = fetch_one(
        """
        SELECT *

        FROM community_links

        LIMIT 1
        """
    )


    return render_template(

        "admin_community.html",

        community=community

    )


# ------------------------------------------------------------
# Community 저장
# 관리자 로그인 필요
# ------------------------------------------------------------

@app.route(
    "/admin/community/save",
    methods=["POST"]
)
def save_community():

    # --------------------------------------------------------
    # 관리자 로그인 확인
    # --------------------------------------------------------

    if not admin_required():

        return redirect(
            "/admin/login"
        )


    telegram = request.form["telegram"]

    discord = request.form["discord"]

    twitter = request.form["twitter"]

    youtube = request.form["youtube"]

    website = request.form["website"]


    row = fetch_one(
        """
        SELECT id

        FROM community_links

        LIMIT 1
        """
    )


    # --------------------------------------------------------
    # 데이터가 없으면 INSERT
    # --------------------------------------------------------

    if row is None:

        execute(
            """
            INSERT INTO community_links
            (

                telegram,

                discord,

                twitter,

                youtube,

                website

            )

            VALUES
            (%s,%s,%s,%s,%s)

            """,

            (

                telegram,

                discord,

                twitter,

                youtube,

                website

            )

        )


    # --------------------------------------------------------
    # 데이터가 있으면 UPDATE
    # --------------------------------------------------------

    else:

        execute(
            """
            UPDATE community_links

            SET

                telegram=%s,

                discord=%s,

                twitter=%s,

                youtube=%s,

                website=%s

            WHERE id=%s

            """,

            (

                telegram,

                discord,

                twitter,

                youtube,

                website,

                row["id"]

            )

        )


    return redirect(
        "/admin/community"
    )

# ------------------------------------------------------------
# Community
# ------------------------------------------------------------

@app.route("/community")
def community():

    community = fetch_one(
        """
        SELECT *

        FROM community_links

        LIMIT 1
        """
    )

    return render_template(

        "community.html",

        community=community

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

# ------------------------------------------------------------
# ETH Chart Data
# DB 조회 최소화 캐시 적용
# Golden Cross / Dead Cross 유지
# ------------------------------------------------------------

@app.route("/chart-data")
def chart_data():

    import time


    now = time.time()



    # --------------------------------------------------------
    # Chart Cache 확인
    # 30초 이내 DB 조회 생략
    # --------------------------------------------------------

    if CACHE["chart_data"]:


        if now - CACHE["chart_time"] < CACHE_TIME["chart_data"]:


            return jsonify(
                CACHE["chart_data"]
            )



    # --------------------------------------------------------
    # DB 연결
    # --------------------------------------------------------

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)



    try:


        cur.execute("""

            SELECT

                created_at,

                price,

                ma20,

                ma60


            FROM eth_price


            ORDER BY id DESC


            LIMIT 300


        """)


        rows = cur.fetchall()



    finally:


        cur.close()

        close_db(conn)



    # --------------------------------------------------------
    # 최신순 → 과거순 변경
    # --------------------------------------------------------

    rows = list(reversed(rows))



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



        # 첫 데이터 비교 불가

        if i == 0:

            continue



        prev20 = ma20[i - 1]

        prev60 = ma60[i - 1]



        # 이동평균 데이터 부족

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
    # JSON 데이터 생성
    # --------------------------------------------------------

    result = {


        "labels": labels,


        "prices": prices,


        "ma20": ma20,


        "ma60": ma60,


        "buy": buy,


        "sell": sell,


        "golden": golden,


        "dead": dead

    }



    # --------------------------------------------------------
    # Chart Cache 저장
    # --------------------------------------------------------

    CACHE["chart_data"] = result

    CACHE["chart_time"] = now



    return jsonify(result)
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

        close_db(conn)

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

@app.after_request
def add_cache_headers(response):

    if request.path.startswith("/static/"):

        response.cache_control.public = True

        response.cache_control.max_age = 86400

    return response

@app.after_request
def add_headers(response):

    if request.path.startswith("/static/"):

        response.cache_control.public = True

        response.cache_control.max_age = 86400

    else:

        response.cache_control.no_cache = True

    return response
# ============================================================
# Database Initialize
# ============================================================

init_db()

insert_default_community()

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
