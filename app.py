# ============================================================
# DB CONNECTION POOL SAFETY PATCH
# 2026-09-18
# - get_db()���� �뿩�� connection ����
# - ���ܷ� close_db()�� ������� ���� ��� teardown���� ��ȯ
# - ���� �߻� �� rollback �� pool ��ȯ
# - close_db()�� ��ȯ ������ ��û ��ü�� �ٽ� ���н�Ű�� �ʵ��� ��ȣ
# - pool maxconn�� ������ Ű���� �ʰ� 10���� ����
# ============================================================

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
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from flask import send_file
from flask_compress import Compress
from psycopg2 import OperationalError

# ==========================================================
# Admin Account (Environment Variables)
# ������ ���� (ȯ�溯��)
# ==========================================================

ADMIN_ID = os.environ.get("ADMIN_ID")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

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
    # RSI / MA ��� ĳ��
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
    "content_time": 0,
    
    "whitepaper": None,
    "whitepaper_time": 0
}


# ĳ�� ���� �ð�(��)
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

    "content": 300,
    "whitepaper": 300
}
# ==========================================================
# Access Log Cache
# ���� �湮�� �ߺ� ���� ����
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
# ���� ������ ĳ��
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
# Session ��ȣŰ
# ------------------------------------------------------------
app.secret_key = "WDM_ADMIN_SECRET_KEY_2026"

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

# Small, lazy pool to reduce connections on a low-traffic Render/Neon setup.
db_pool = ThreadedConnectionPool(
    minconn=0,
    maxconn=3,
    dsn=DATABASE_URL,
    connect_timeout=5,
    sslmode="require",
    application_name="wdm-web"
)


# ==========================================================
# Get Database Connection
# Connection Pool ���
# ==========================================================

def get_db():
    """Borrow a database connection and register it for request cleanup."""
    conn = db_pool.getconn()
    try:
        from flask import g, has_request_context
        if has_request_context():
            if not hasattr(g, "_db_connection_objects"):
                g._db_connection_objects = {}
            g._db_connection_objects[id(conn)] = conn
    except Exception:
        pass
    return conn


def close_db(conn, discard=False):
    """Return a connection once; discard broken connections when requested."""
    if conn is None:
        return
    try:
        from flask import g, has_request_context
        if has_request_context() and hasattr(g, "_db_connection_objects"):
            g._db_connection_objects.pop(id(conn), None)
    except Exception:
        pass
    try:
        if not discard and not conn.closed:
            if conn.status != psycopg2.extensions.STATUS_READY:
                conn.rollback()
        db_pool.putconn(conn, close=discard or bool(conn.closed))
    except Exception:
        try:
            db_pool.putconn(conn, close=True)
        except Exception:
            pass


@app.teardown_appcontext
def cleanup_db_connections(exception=None):
    """Return any connections that a route forgot to close."""
    try:
        from flask import g
        connections = list(getattr(g, "_db_connection_objects", {}).values())
        for conn in connections:
            try:
                if exception is not None:
                    conn.rollback()
                close_db(conn, discard=bool(getattr(conn, "closed", False)))
            except Exception:
                try:
                    close_db(conn, discard=True)
                except Exception:
                    pass
    except Exception:
        pass


def execute(sql, params=None):
    for attempt in range(2):
        conn = None
        cur = None

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return

        except OperationalError:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass

            if attempt == 0:
                # ������ ������ �ݵ�� ����ϰ� �� ����� ��õ�
                if conn is not None:
                    close_db(conn, discard=True)
                    conn = None
                continue

            raise

        finally:
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass

            if conn is not None:
                close_db(conn)

# ==========================================================
# Fetch One Row
# SELECT 1�� ��ȸ
# ==========================================================

def fetch_one(sql, params=None):
    for attempt in range(2):
        conn = None
        cur = None

        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            return cur.fetchone()

        except psycopg2.OperationalError:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass

            if attempt == 0:
                if conn is not None:
                    close_db(conn, discard=True)
                    conn = None
                continue

            raise

        finally:
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass

            if conn is not None:
                close_db(conn)

# ==========================================================
# Fetch All Rows
# SELECT ������ ��ȸ
# ==========================================================

def fetch_all(sql, params=None):
    for attempt in range(2):
        conn = None
        cur = None

        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            return cur.fetchall()

        except psycopg2.OperationalError:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass

            if attempt == 0:
                if conn is not None:
                    close_db(conn, discard=True)
                    conn = None
                continue

            raise

        finally:
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass

            if conn is not None:
                close_db(conn)

# ==========================================================
# Portfolio ��ȸ ĳ��
# DB �ݺ� ��ȸ �ּ�ȭ
# ==========================================================

PORTFOLIO_CACHE = {

    "data": None,

    "time": 0

}


# ==========================================================
# Portfolio Cache ���� �ð�
# seconds
# ==========================================================

PORTFOLIO_CACHE_TIME = 30



# ==========================================================
# Portfolio ��ȸ
# Cache ����
# ==========================================================

def get_cached_portfolio():

    import time


    now = time.time()



    # ======================================================
    # Cache ���
    # ======================================================

    if PORTFOLIO_CACHE["data"] is not None:


        if (

            now - PORTFOLIO_CACHE["time"]

            <

            PORTFOLIO_CACHE_TIME

        ):


            return PORTFOLIO_CACHE["data"]



    # ======================================================
    # Cache ����
    # DB ��ȸ ����
    # ======================================================

    row = fetch_one("""
        SELECT *
        FROM portfolio
        ORDER BY id
        LIMIT 1
    """)



    # ======================================================
    # Cache ����
    # ======================================================

    PORTFOLIO_CACHE["data"] = row


    PORTFOLIO_CACHE["time"] = now



    return row




# ==========================================================
# Portfolio Cache Clear
# �ż�/�ŵ� �� ����
# ==========================================================

def clear_portfolio_cache():


    PORTFOLIO_CACHE["data"] = None


    PORTFOLIO_CACHE["time"] = 0
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
    # ���� ���� ��ȸ
    # ------------------------------------------------------

    response = requests.get(

        url,

        headers=headers

    )


    if response.status_code != 200:

        return


    sha = response.json()["sha"]


    # ------------------------------------------------------
    # ����
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

        FROM (

            SELECT

                id,

                created_at,

                price

            FROM

                wdm_price_history

            ORDER BY

                id DESC

            LIMIT 100

        ) AS latest

        ORDER BY

            id ASC

        """

    )
# ----------------------------------------------
# WDM ��Ʈ ���� �̷� ����
# ----------------------------------------------
def save_wdm_chart_price(conn, price):

    try:

        cur = conn.cursor()

        cur.execute("""

            INSERT INTO wdm_price_history(price)

            VALUES(%s)

        """, (price,))

        cur.close()

        return True

    except Exception as e:

        print("WDM CHART SAVE ERROR :", e)

        traceback.print_exc()

        return False



# ==========================================================
# Announcement Helper Functions
# ==========================================================

# ==========================================================
# Announcement Helper Functions
# ==========================================================

import time


# ----------------------------------------------------------
# ���� ��ü ��ȸ (Cache)
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
# ���� 1�� ��ȸ
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
# ���� ���
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
# ���� ����
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
# ���� ����
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
    conn = None
    cur = None

    try:
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

    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if conn is not None:
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
    # �������� ���̺� ����
    # init_db() �Լ� ����
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
# FAQ answer NULL ���
# ==========================================================

    cur.execute("""

    ALTER TABLE faq
    ALTER COLUMN answer DROP NOT NULL;

    """)

# ==========================================================
# FAQ updated_at �⺻��
# ==========================================================

    cur.execute("""

    ALTER TABLE faq
    ALTER COLUMN updated_at
    SET DEFAULT CURRENT_TIMESTAMP;

    """)

    # ==========================================================
    # site_statistics �÷� �߰�
    # ���� �湮�� ����
    # ==========================================================

    execute("""
        ALTER TABLE site_statistics
        ADD COLUMN IF NOT EXISTS today_visits INTEGER DEFAULT 0
    """)


    execute("""
        ALTER TABLE site_statistics
        ADD COLUMN IF NOT EXISTS visit_date DATE DEFAULT CURRENT_DATE
    """)
    # ==========================================================
    # Site Statistics Table
    # ���� �湮�� ���
    # ==========================================================

    execute(

        """

        CREATE TABLE IF NOT EXISTS site_statistics
        (

            id INTEGER PRIMARY KEY,

            total_visits BIGINT DEFAULT 0

        )

        """

    )

   

    # ==========================================================
    # Insert Default Site Statistics
    # �⺻ �湮�� ��� ������ ����
    # ==========================================================

    execute("""

        INSERT INTO site_statistics
        (
            id,
            total_visits,
            today_visits,
            visit_date
        )

        VALUES
        (
            1,
            0,
            0,
            CURRENT_DATE
        )

        ON CONFLICT (id)
        DO NOTHING

    """)
    # ==========================================================
    # Site Statistics Table
    # ���� �湮�� ���
    # ==========================================================

    cur.execute("""

        CREATE TABLE IF NOT EXISTS site_statistics
        (

            id INTEGER PRIMARY KEY,

            total_visits BIGINT DEFAULT 0

        )

    """)

    cur.execute("""

        INSERT INTO site_statistics
        (
            id,
            total_visits
        )

        VALUES
        (
            1,
            0
        )

        ON CONFLICT (id)

        DO NOTHING

    """)
  
# ==========================================================
# Access Statistics Table
# �湮�� ���� ��� ���� ���̺�
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
# �湮�� ���� ���� ���� �÷� �߰�
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

    # --------------------------------------------------------
    # WDM PRICE HISTORY TABLE
    # --------------------------------------------------------

    cur.execute("""

        CREATE TABLE IF NOT EXISTS wdm_price_history(

            id SERIAL PRIMARY KEY,

            price NUMERIC(18,8),

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )

    """)
    
    # ==========================================================
    # WDM PRICE TABLE
    # MA20 �÷� �߰�
    # ==========================================================

    cur.execute("""

    ALTER TABLE wdm_price
    ADD COLUMN IF NOT EXISTS ma20 DOUBLE PRECISION;

    """)

    # ==========================================================
    # WDM PRICE TABLE
    # MA60 �÷� �߰�
    # ==========================================================

    cur.execute("""

    ALTER TABLE wdm_price
    ADD COLUMN IF NOT EXISTS ma60 DOUBLE PRECISION;

    """)

    # ==========================================================
    # WDM PRICE TABLE
    # SIGNAL �÷� �߰�
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
# �湮 ��� ����
# ==========================================================

# ==========================================================
# Save Access Log
# �湮 ��� ����
# ==========================================================
def save_access_log():

    try:

        import time

        # ==========================================================
        # Get Real Visitor IP
        # ���� �湮�� IP ����
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
        # ���� �� ���� IP ����
        # ==========================================================

        if ip in (
            "127.0.0.1",
            "::1"
        ):

            return


        # ==========================================================
        # Get Access Information
        # ���� ������ �� ������ ����
        # ==========================================================

        path = request.path

        agent = request.headers.get(
            "User-Agent",
            ""
        )


        # ==========================================================
        # Ignore Bot / Crawler
        # �� �� ũ�ѷ� ����
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
        # �ĺ��� ��û ����
        # ==========================================================

        if path == "/favicon.ico":

            return


        # ==========================================================
        # Access Log Cache
        # ���� IP + ���� URL 30�� �ߺ� ���� ����
        # ==========================================================

        now = time.time()

        cache_key = f"{ip}:{path}"

        if cache_key in ACCESS_LOG_CACHE:

            last_time = ACCESS_LOG_CACHE[cache_key]

            if now - last_time < ACCESS_LOG_CACHE_SECONDS:

                return

        ACCESS_LOG_CACHE[cache_key] = now


        # ==========================================================
        # ������ Cache ����
        # ==========================================================

        expired_keys = []

        for key, value in ACCESS_LOG_CACHE.items():

            if now - value > ACCESS_LOG_CACHE_SECONDS:

                expired_keys.append(key)

        for key in expired_keys:

            del ACCESS_LOG_CACHE[key]


         # ==========================================================
        # Get Visitor Country
        # �湮�� ���� ���� ��ȸ
        #
        # �ӵ� ������ ���� �ӽ� ��Ȱ��ȭ
        # �ʿ� �� �Ʒ� �ּ�(#) ���� �� ���
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
        # Today Visitor Count ����
        # ���� �湮�� ����
        # ==========================================================

        execute("""
            UPDATE site_statistics

            SET today_visits = today_visits + 1

            WHERE id = 1
        """)

        # ==========================================================
        # ��¥ ���� Ȯ��
        # ���� ��¥ ���� �� �ʱ�ȭ
        # ==========================================================

        execute("""
            UPDATE site_statistics

            SET
                today_visits = 0,
                visit_date = CURRENT_DATE

            WHERE
                id = 1

            AND
                visit_date <> CURRENT_DATE
        """)
        # ==========================================================
        # Insert Access Log
        # �湮 ��� ����
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
        # Total Visitor Count
        # ���� �湮�� �� ����
        # ==========================================================

        execute(

            """

            UPDATE site_statistics

            SET

                total_visits = total_visits + 1

            WHERE id = 1

            """

        )
             
        # ==========================================================
        # Keep Latest 1000 Logs
        # �ֱ� �湮 ��� 1000�� ����
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
# �ߺ� ���� �湮�� �� ���
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
    # WDM ���� ����
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
# �̴����� ���� ���� ��ȸ
# ==========================================================
# ==========================================================
# ETH Price Cache
# CoinGecko ȣ�� �ּ�ȭ
# ==========================================================

ETH_PRICE_CACHE = {

    "price": None,

    "time": 0

}

ETH_CACHE_SECONDS = 30

# ==========================================================
# ETH ���� ��ȸ
# CoinGecko API + �޸� ĳ��
# ==========================================================

def get_eth_price():

    import time


    now = time.time()


    # -------------------------------
    # ĳ�� ������ ���
    # -------------------------------

    if CACHE["eth_price"]:

        if now - CACHE["eth_time"] < CACHE_TIME["eth_price"]:

            return CACHE["eth_price"]



    # -------------------------------
    # ���� API ȣ��
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



        # ĳ�� ����

        CACHE["eth_price"] = price
        CACHE["eth_time"] = now


        return price



    except Exception as e:

        print("ETH PRICE ERROR:", e)

        return CACHE["eth_price"]
# ------------------------------------------------------------
# Latest Price (DB)
# �˾�â ��� ǥ�ÿ�
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
# ============================================================
# WDM Latest Price
# Uniswap V4 / Base Mainnet
# ============================================================

def get_latest_wdm_price():

    import time
    import requests

    now = time.time()

    # --------------------------------------------------------
    # Cache
    # --------------------------------------------------------

    cached_price = CACHE.get("wdm_price")
    cached_time = CACHE.get("wdm_price_time", 0)

    cache_seconds = CACHE_TIME.get("wdm_price", 30)

    if cached_price is not None:
        if now - cached_time < cache_seconds:
            return float(cached_price)

    # --------------------------------------------------------
    # Error cooldown
    # --------------------------------------------------------

    error_time = CACHE.get("wdm_price_error_time", 0)

    if error_time:

        if now - error_time < 60:

            if cached_price is not None:
                return float(cached_price)

            return 0.0

    # --------------------------------------------------------
    # Base Mainnet RPC
    # --------------------------------------------------------

    RPC_URL = "https://base-rpc.publicnode.com"

    # --------------------------------------------------------
    # Uniswap V4 StateView - Base Mainnet
    # --------------------------------------------------------

    STATE_VIEW = (
        "0xa3c0c9b65bad0b08107aa264b0f3db444b867a71"
    )

    # --------------------------------------------------------
    # WDM / ETH Pool ID
    # --------------------------------------------------------

    POOL_ID = (
        "0x2cf89bddedee86c8d81609a5866d4086ce8464975142bf37d8b648c4cd2fd24b"
    )

    # --------------------------------------------------------
    # Uniswap V4
    #
    # getSlot0(bytes32)
    #
    # IMPORTANT:
    # This is NOT the Uniswap V3 slot0() selector.
    # --------------------------------------------------------

    selector = "0xc815641c"

    data = selector + POOL_ID[2:]

    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [
            {
                "to": STATE_VIEW,
                "data": data
            },
            "latest"
        ],
        "id": 1
    }

    try:

        # ----------------------------------------------------
        # requests Session
        # Render netrc timeout ����
        # ----------------------------------------------------

        session = requests.Session()

        session.trust_env = False

        response = session.post(
            RPC_URL,
            json=payload,
            timeout=(3, 8),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "W-donation-WDM/1.0"
            }
        )

        # ----------------------------------------------------
        # HTTP 429
        # ----------------------------------------------------

        if response.status_code == 429:

            CACHE["wdm_price_error_time"] = now

            print(
                "WDM StateView RPC: 429 Too Many Requests"
            )

            if cached_price is not None:
                return float(cached_price)

            return 0.0

        response.raise_for_status()

        result = response.json()

        # ----------------------------------------------------
        # JSON RPC Error
        # ----------------------------------------------------

        if "error" in result:

            CACHE["wdm_price_error_time"] = now

            print(
                "WDM StateView RPC Error:",
                result["error"]
            )

            if cached_price is not None:
                return float(cached_price)

            return 0.0

        raw = result.get("result")

        # ----------------------------------------------------
        # Empty result
        # ----------------------------------------------------

        if not raw or raw == "0x":

            CACHE["wdm_price_error_time"] = now

            print(
                "WDM StateView: Empty result"
            )

            if cached_price is not None:
                return float(cached_price)

            return 0.0

        # ----------------------------------------------------
        # ABI decode
        #
        # getSlot0 returns 4 values
        #
        # 1. sqrtPriceX96
        # 2. tick
        # 3. protocolFee
        # 4. lpFee
        # ----------------------------------------------------

        raw_data = raw[2:]

        if len(raw_data) < 128:

            CACHE["wdm_price_error_time"] = now

            print(
                "WDM StateView: Invalid result length:",
                len(raw_data)
            )

            if cached_price is not None:
                return float(cached_price)

            return 0.0

        # ----------------------------------------------------
        # sqrtPriceX96
        # ----------------------------------------------------

        sqrt_price_x96 = int(
            raw_data[0:64],
            16
        )

        # ----------------------------------------------------
        # tick
        # ----------------------------------------------------

        tick_raw = int(
            raw_data[64:128],
            16
        )

        # int24 signed conversion

        if tick_raw >= 2 ** 23:
            tick = tick_raw - 2 ** 24
        else:
            tick = tick_raw

        # ----------------------------------------------------
        # Pool initialization check
        # ----------------------------------------------------

        if sqrt_price_x96 <= 0:

            CACHE["wdm_price_error_time"] = now

            print(
                "WDM StateView: sqrtPriceX96 = 0"
            )

            if cached_price is not None:
                return float(cached_price)

            return 0.0

        # ----------------------------------------------------
        # sqrtPriceX96
        #
        # price = (sqrtPriceX96 / 2^96)^2
        # ----------------------------------------------------

        price_token1_per_token0 = (
            (sqrt_price_x96 / (2 ** 96)) ** 2
        )

        if price_token1_per_token0 <= 0:

            CACHE["wdm_price_error_time"] = now

            print(
                "WDM StateView: Invalid pool price"
            )

            if cached_price is not None:
                return float(cached_price)

            return 0.0

        # ----------------------------------------------------
        # Token order
        #
        # WETH:
        # 0x4200000000000000000000000000000000000006
        #
        # WDM:
        # 0x4C154CaF238efD0811e15D9b30d074358F6468D1
        #
        # WETH < WDM
        #
        # Therefore:
        #
        # currency0 = WETH
        # currency1 = WDM
        # ----------------------------------------------------

        wdm_per_eth = price_token1_per_token0

        # ----------------------------------------------------
        # ETH/USD
        # ----------------------------------------------------

        try:
            eth_price = get_latest_price()
        except Exception as e:
            print("WDM ETH DB price unavailable; using market API:", e)
            eth_price = None

        # Fall back to cached/live ETH market price if DB history is unavailable.
        if not eth_price or float(eth_price) <= 0:
            try:
                eth_price = get_eth_price()
            except Exception as e:
                print("WDM ETH market price error:", e)
                eth_price = 0.0

        if not eth_price or float(eth_price) <= 0:

            CACHE["wdm_price_error_time"] = now

            print(
                "WDM StateView: ETH price unavailable"
            )

            if cached_price is not None:
                return float(cached_price)

            return 0.0

        # ----------------------------------------------------
        # WDM/USD
        # ----------------------------------------------------

        wdm_price = (
            float(eth_price) / wdm_per_eth
        )

        # ----------------------------------------------------
        # Safety
        # ----------------------------------------------------

        if wdm_price <= 0:

            CACHE["wdm_price_error_time"] = now

            print(
                "WDM StateView: Invalid WDM price:",
                wdm_price
            )

            if cached_price is not None:
                return float(cached_price)

            return 0.0

        # ----------------------------------------------------
        # Cache save
        # ----------------------------------------------------

        CACHE["wdm_price"] = float(wdm_price)
        CACHE["wdm_price_time"] = now

        CACHE["wdm_price_error_time"] = 0

        # ----------------------------------------------------
        # Log
        # ----------------------------------------------------

        print(
            f"WDM Uniswap V4 Price: "
            f"${wdm_price:.12f}"
        )

        print(
            f"WDM per ETH: "
            f"{wdm_per_eth:,.6f}"
        )

        print(
            f"WDM Tick: {tick}"
        )

        print(
            f"ETH Price: "
            f"${float(eth_price):,.2f}"
        )

        return float(wdm_price)

    except Exception as e:

        CACHE["wdm_price_error_time"] = now

        print(
            "WDM Uniswap V4 Price Error:",
            e
        )

        if cached_price is not None:
            return float(cached_price)

        return 0.0


# ============================================================
# ETH �� WDM Conversion Calculator
# ȯ�� ��� ����
# ============================================================

def calculate_wdm_conversion(
    direction,
    amount,
    eth_price,
    wdm_price
):

    try:

        amount = float(amount)

        eth_price = float(eth_price)

        wdm_price = float(wdm_price)

    except (TypeError, ValueError):

        return {
            "success": False,
            "message": "Invalid conversion data"
        }


    # --------------------------------------------------------
    # �ݾ� Ȯ��
    # --------------------------------------------------------

    if amount <= 0:

        return {
            "success": False,
            "message": "Amount must be greater than zero"
        }


    # --------------------------------------------------------
    # ���� Ȯ��
    # --------------------------------------------------------

    if eth_price <= 0:

        return {
            "success": False,
            "message": "ETH price unavailable"
        }


    if wdm_price <= 0:

        return {
            "success": False,
            "message": "WDM price unavailable"
        }


    # --------------------------------------------------------
    # ETH �� WDM
    # --------------------------------------------------------

    if direction == "ETH_TO_WDM":

        receive_amount = (
            amount * eth_price
        ) / wdm_price


    # --------------------------------------------------------
    # WDM �� ETH
    # --------------------------------------------------------

    elif direction == "WDM_TO_ETH":

        receive_amount = (
            amount * wdm_price
        ) / eth_price


    # --------------------------------------------------------
    # �߸��� ����
    # --------------------------------------------------------

    else:

        return {
            "success": False,
            "message": "Invalid direction"
        }


    # --------------------------------------------------------
    # ���
    # --------------------------------------------------------

    return {

        "success": True,

        "direction": direction,

        "amount": amount,

        "eth_price": eth_price,

        "wdm_price": wdm_price,

        "receive_amount": receive_amount

    }


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
    # ���� ��ư Ŭ��
    # ------------------------------------------------------
    if request.method == "POST":

        price = float(request.form["price"])

        # ----------------------------------------------
        # ���� ����
        # ----------------------------------------------
        cur.execute("""
            INSERT INTO wdm_price(price)
            VALUES(%s)
            RETURNING id
        """, (price,))

        new_id = cur.fetchone()["id"]

        conn.commit()

        # ----------------------------------------------
        # MA20 ���
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
        # MA60 ���
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
        # ���� MA ��ȸ
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
        # MA / Signal ������Ʈ
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
        # ���� �Ϸ�
        # ----------------------------------------------
        conn.commit()

        message = f"WDM Saved ({signal})"
    # ==========================================================
    # ���� �Ϸ�
    # (signal�� ������ �̹� ���Ǿ� ����)
    # ==========================================================

    conn.commit()

    message = f"WDM Saved ({signal})"

    # ------------------------------------------------------
    # �ֱ� ������ ǥ��
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
# MA ���
# ���� calculate_wdm_ma() �Լ� ��ü ��ü
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
    # ������ ����
    # ------------------------------------------
    if len(rows) < period:

        return None

    prices = [float(r["price"]) for r in rows]

    return round(sum(prices) / period, 8)


# ==========================================================
# WDM Previous Moving Average
# ���� MA ���
# ���� calculate_previous_wdm_ma() �Լ� ��ü ��ü
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
    # ������ ����
    # ------------------------------------------
    if len(rows) < period + 1:

        return None

    # �ֱ� ���� ����
    prices = [float(r["price"]) for r in rows[1:]]

    return round(sum(prices) / period, 8)    
# ==========================================================
# WDM RSI
# RSI ���
# calculate_previous_wdm_ma() �ٷ� �Ʒ� �ٿ��ֱ�
# ==========================================================

def calculate_wdm_rsi(period=14):

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ------------------------------------------------------
    # �ֱ� period+1���� ���� ��ȸ
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
    # ������ ����
    # ------------------------------------------------------
    if len(rows) < period + 1:

        return None

    # ������ ���� �� �ֽ� ���� ������ ����
    prices = [float(r["price"]) for r in reversed(rows)]

    gains = []
    losses = []

    # ------------------------------------------------------
    # ��� / �϶� ���
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
    # RSI ���
    # ------------------------------------------------------
    if avg_loss == 0:

        return 100

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return round(rsi, 2)
# ==========================================================
# WDM Price History
# WDM ��Ʈ�� ���� �̷� ��ȸ
# ==========================================================

def get_wdm_price_history(limit=100):

    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            price,
            created_at
        FROM wdm_price_history
        ORDER BY id DESC
        LIMIT %s
    """, (limit,))

    rows = cur.fetchall()

    cur.close()
    close_db(conn)

    return rows
# ==========================================================
# WDM Trading Signal
# ETH generate_signal()�� ������ ����
# calculate_wdm_rsi() �Ʒ� �ٿ��ֱ�
# ==========================================================

def generate_wdm_signal():

    # ------------------------------------------------------
    # ��ǥ ���
    # ------------------------------------------------------
    rsi = calculate_wdm_rsi()

    ma20 = calculate_wdm_ma(20)

    ma60 = calculate_wdm_ma(60)

    prev20 = calculate_previous_wdm_ma(20)

    prev60 = calculate_previous_wdm_ma(60)

    signal = "HOLD"

    # ------------------------------------------------------
    # ������ ����
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
    # ��� ��ȯ
    # ------------------------------------------------------
    return {

        "signal": signal,

        "rsi": rsi,

        "ma20": ma20,

        "ma60": ma60

    }
# ------------------------------------------------------------
# RSI ���
# ------------------------------------------------------------
# ------------------------------------------------------------
# RSI ���
# DB ��ȸ �ּ�ȭ ĳ�� ����
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
    # ���� ������ ��ȸ
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
    # ĳ�� ����
    # --------------------------------------------------------

    CACHE["rsi"] = rsi

    CACHE["rsi_time"] = now



    return rsi
# ------------------------------------------------------------
# Moving Average
# MA20 / MA60 ��� ĳ�� ����
# ------------------------------------------------------------

def calculate_ma(period):


    import time


    now = time.time()


    cache_key = f"ma{period}"



    # --------------------------------------------------------
    # ĳ�� Ȯ��
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
    # DB ��ȸ
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
    # ĳ�� ����
    # --------------------------------------------------------

    CACHE[cache_key] = ma

    CACHE[f"{cache_key}_time"] = now



    return ma





# ------------------------------------------------------------
# Previous Moving Average
# ���� MA ��� ĳ�� ����
# ------------------------------------------------------------

def calculate_previous_ma(period):


    import time


    now = time.time()


    cache_key = f"prev_ma{period}"



    # --------------------------------------------------------
    # ĳ�� Ȯ��
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
    # DB ��ȸ
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
    # ĳ�� ����
    # --------------------------------------------------------

    CACHE[cache_key] = previous_ma

    CACHE[f"{cache_key}_time"] = now



    return previous_ma
# ------------------------------------------------------------
# Cross Signal
# MA20 / MA60 ���� ���� ���
# ------------------------------------------------------------
# ------------------------------------------------------------
# Cross Signal
# MA20 / MA60 ���� ���� ���
# DB ��ȸ �ּ�ȭ ĳ�� ����
# ------------------------------------------------------------

def get_cross_signals():


    import time


    now = time.time()



    # --------------------------------------------------------
    # Cross Signal Cache Ȯ��
    # --------------------------------------------------------

    if CACHE["cross_signal"] is not None:


        if now - CACHE["cross_signal_time"] < CACHE_TIME["cross_signal"]:


            return CACHE["cross_signal"]



    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)



    try:


        # ----------------------------------------------------
        # �ֱ� �� �� �����͸� ��ȸ
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



    # �ֽż����� �������� ������ ���� ����

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
    # Cache ����
    # --------------------------------------------------------

    CACHE["cross_signal"] = signal

    CACHE["cross_signal_time"] = now



    return signal

# ------------------------------------------------------------
# Trading Signal
# ------------------------------------------------------------
# ------------------------------------------------------------
# Trading Signal
# RSI / MA / Cross Signal ĳ�� ����
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
    # RSI ���
    # --------------------------------------------------------

    rsi = calculate_rsi()

    # --------------------------------------------------------
    # �̵���� ���
    # --------------------------------------------------------

    ma20 = calculate_ma(20)

    ma60 = calculate_ma(60)

    # --------------------------------------------------------
    # ������ ����
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
    # RSI ����
    # --------------------------------------------------------

    if signal == "BUY":

        if rsi is not None and rsi < 30:

            signal = "STRONG BUY"

    elif signal == "SELL":

        if rsi is not None and rsi > 70:

            signal = "STRONG SELL"

    # --------------------------------------------------------
    # ���
    # --------------------------------------------------------

    result = {

        "signal": signal,

        "price": get_latest_price(),

        "rsi": rsi,

        "ma20": ma20,

        "ma60": ma60

    }

    # --------------------------------------------------------
    # Cache ����
    # --------------------------------------------------------

    CACHE["signal"] = result
    CACHE["signal_time"] = now

    return result

# ==========================================================
# PART 5 : Auto Save
# ==========================================================

def auto_save_eth():

    while True:

        try:
            # ------------------------------------------------
            # ���� ETH ����
            # ------------------------------------------------
            price = get_eth_price()

            if price is None:
                time.sleep(30)
                continue

            # ------------------------------------------------
            # �߿�: DB ������ ���� �������� �ʵ���
            # ���� INSERT �� ��� connection ��ȯ
            # ------------------------------------------------
            conn = None
            cur = None
            new_id = None

            try:
                conn = get_db()
                cur = conn.cursor(cursor_factory=RealDictCursor)

                cur.execute(
                    """
                    INSERT INTO eth_price(price)
                    VALUES(%s)
                    RETURNING id
                    """,
                    (price,)
                )

                new_id = cur.fetchone()["id"]
                conn.commit()

            except Exception:
                if conn is not None:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                raise

            finally:
                if cur is not None:
                    try:
                        cur.close()
                    except Exception:
                        pass
                if conn is not None:
                    close_db(conn)

            # ------------------------------------------------
            # Cache �ʱ�ȭ
            # ------------------------------------------------
            CACHE["chart_data"] = None
            CACHE["chart_time"] = 0

            CACHE["rsi"] = None
            CACHE["rsi_time"] = 0
            CACHE["ma20"] = None
            CACHE["ma20_time"] = 0
            CACHE["ma60"] = None
            CACHE["ma60_time"] = 0
            CACHE["prev_ma20"] = None
            CACHE["prev_ma20_time"] = 0
            CACHE["prev_ma60"] = None
            CACHE["prev_ma60_time"] = 0
            CACHE["cross_signal"] = None
            CACHE["cross_signal_time"] = 0
            CACHE["signal"] = None
            CACHE["signal_time"] = 0

            CACHE["wdm_price"] = None
            CACHE["wdm_price_time"] = 0

            # ------------------------------------------------
            # DB connection�� ��ȯ�� �� ��ǥ ���
            # -> nested connection���� ���� pool ���� ����
            # ------------------------------------------------
            ma20 = calculate_ma(20)
            ma60 = calculate_ma(60)
            signal_data = generate_signal()
            signal = signal_data["signal"]

            # ------------------------------------------------
            # �ڵ��Ÿ� ���� ��Ȱ��ȭ
            # ------------------------------------------------
            # auto_trade(signal_data)

            # ------------------------------------------------
            # ��� ����� ������ ª�� DB ����� UPDATE
            # ------------------------------------------------
            conn = None
            cur = None

            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE eth_price
                    SET
                        ma20=%s,
                        ma60=%s,
                        signal=%s
                    WHERE id=%s
                    """,
                    (ma20, ma60, signal, new_id)
                )
                conn.commit()

            except Exception:
                if conn is not None:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                raise

            finally:
                if cur is not None:
                    try:
                        cur.close()
                    except Exception:
                        pass
                if conn is not None:
                    close_db(conn)

            print(
                f"[AUTO ETH] "
                f"Price={price:.2f} "
                f"MA20={ma20} "
                f"MA60={ma60} "
                f"Signal={signal}"
            )

        except Exception as e:
            print("AUTO ETH SAVE ERROR :", e)
            traceback.print_exc()

        try:
            keep_latest_rows("eth_price", 10000)
            keep_latest_rows("trading_records", 10000)
        except Exception as e:
            print("AUTO ETH CLEANUP ERROR :", e)
            traceback.print_exc()

        time.sleep(600)

def auto_save_wdm():

    while True:

        conn = None

        try:

            # ------------------------------------------------
            # ���� WDM ���� ��ȸ
            # Uniswap V4 / Base Mainnet
            # ------------------------------------------------

            print(
                "[AUTO WDM] "
                "WDM price check..."
            )

            wdm_price = get_latest_wdm_price()


            # ------------------------------------------------
            # ���� ���� Ȯ��
            # ------------------------------------------------

            if (
                wdm_price is None
                or float(wdm_price) <= 0
            ):

                print(
                    "[AUTO WDM] "
                    "WDM price unavailable - "
                    "retry after 60 seconds"
                )

                time.sleep(60)

                continue


            # ------------------------------------------------
            # ���� Ȯ�� �α�
            # ------------------------------------------------

            wdm_price = float(wdm_price)

            print(
                "[AUTO WDM] "
                f"Price=${wdm_price:.12f}"
            )


            # ------------------------------------------------
            # DB ����
            # ------------------------------------------------

            conn = get_db()


            # ------------------------------------------------
            # WDM ���� �̷� ����
            # ------------------------------------------------

            saved = save_wdm_chart_price(
                conn,
                wdm_price
            )


            # ------------------------------------------------
            # ���� ��� Ȯ��
            # ------------------------------------------------

            if not saved:

                conn.rollback()

                print(
                    "[AUTO WDM] "
                    "Price history save failed - "
                    "retry after 60 seconds"
                )

                close_db(conn)

                conn = None

                time.sleep(60)

                continue


            # ------------------------------------------------
            # DB Commit
            # ------------------------------------------------

            conn.commit()


            # ------------------------------------------------
            # DB ���� ����
            # ------------------------------------------------

            close_db(conn)

            conn = None


            # ------------------------------------------------
            # WDM Chart Cache �ʱ�ȭ
            # ���ο� ������ ����Ǿ����Ƿ�
            # ���� ��Ʈ ��ȸ���� �ֽ� DB �����͸� �е��� ��
            # ------------------------------------------------

            CACHE["chart_data"] = None
            CACHE["chart_time"] = 0


            # ------------------------------------------------
            # ���� �Ϸ� �α�
            # ------------------------------------------------

            print(
                "[AUTO WDM] "
                "Price history saved successfully"
            )


            # ------------------------------------------------
            # ���� ���� �� 10�� �� ���� ����
            # ------------------------------------------------

            time.sleep(600)


        except Exception as e:

            # ------------------------------------------------
            # DB Rollback
            # ------------------------------------------------

            if conn is not None:

                try:

                    conn.rollback()

                except Exception:

                    pass


                # ------------------------------------------------
                # DB ���� ����
                # ------------------------------------------------

                try:

                    close_db(conn)

                except Exception:

                    pass

                conn = None


            # ------------------------------------------------
            # ���� �α�
            # ------------------------------------------------

            print(
                "[AUTO WDM SAVE ERROR]:",
                e
            )

            traceback.print_exc()


            # ------------------------------------------------
            # ���� �߻� �� 60�� �� ��õ�
            # ------------------------------------------------

            print(
                "[AUTO WDM] "
                "Retry after 60 seconds"
            )

            time.sleep(60)


# ==========================================================
# PART 6 : Portfolio
# ==========================================================


# --------------------------------------
# Portfolio ��ȸ
# DB ��ȸ �ּ�ȭ ĳ�� ����
# --------------------------------------

def calculate_portfolio():

    import time


    now = time.time()


    # --------------------------------------------------------
    # Portfolio ��� ��� ĳ�� ���
    # 30�� ���� DB ��ȸ ����
    # --------------------------------------------------------

    if CACHE["portfolio"]:

        if now - CACHE["portfolio_time"] < CACHE_TIME["portfolio"]:

            return CACHE["portfolio"]



    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)



    try:


        # --------------------------------------------------------
        # Portfolio ������ ��ȸ
        # --------------------------------------------------------

        cur.execute("""
            SELECT *
            FROM portfolio
            LIMIT 1
        """)


        portfolio = cur.fetchone()



        # --------------------------------------------------------
        # Portfolio�� ������ �⺻ ����
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
        # �ֽ� ETH ���� ��ȸ
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
        # Portfolio �⺻ ��
        # --------------------------------------------------------

        cash = float(portfolio["cash"])

        eth = float(portfolio["eth"])

        wdm = float(portfolio["wdm"])

        avg_price = float(portfolio["avg_price"])



        # --------------------------------------------------------
        # ETH �򰡱ݾ�
        # --------------------------------------------------------

        asset_value = eth * current_price



        # --------------------------------------------------------
        # WDM ���� ��ȸ
        # --------------------------------------------------------

        wdm_price = get_latest_wdm_price()



        # --------------------------------------------------------
        # WDM �򰡱ݾ�
        # --------------------------------------------------------

        wdm_value = wdm * wdm_price



        # --------------------------------------------------------
        # �� �ڻ�
        # --------------------------------------------------------

        total_assets = (
            cash
            + asset_value
            + wdm_value
        )



        # --------------------------------------------------------
        # ���� ���
        # --------------------------------------------------------

        if eth > 0:

            profit = (
                asset_value
                - (eth * avg_price)
            )

        else:

            profit = 0



        # --------------------------------------------------------
        # ROI ���
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
        # ��� ����
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
        # Portfolio ĳ�� ����
        # --------------------------------------------------------

        CACHE["portfolio"] = result

        CACHE["portfolio_time"] = now



        return result



    finally:


        cur.close()

        close_db(conn)
# ------------------------------------------------------------
# BUY ETH
# Portfolio ������ �̿��Ͽ� ETH �ż�
# DB ��ȸ �ּ�ȭ + Portfolio ĳ�� �ʱ�ȭ
# ------------------------------------------------------------

def buy_eth(buy_percent=20):


    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)


    try:


        # ----------------------------------------------------
        # Portfolio ��ȸ
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
        # ETH �������̸� �ż� ����
        # ----------------------------------------------------

        if eth > 0:

            print("BUY SKIP : Already Holding")

            return None



        # ----------------------------------------------------
        # ���� ETH ���� ��ȸ
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
        # �ż� �ݾ� ���
        # ----------------------------------------------------

        trade_amount = round(
            cash * buy_percent / 100,
            2
        )


        if trade_amount <= 0:

            return None



        # ----------------------------------------------------
        # ETH ���� ���
        # ----------------------------------------------------

        quantity = trade_amount / current_price



        # ----------------------------------------------------
        # Portfolio ���
        # ----------------------------------------------------

        new_cash = cash - trade_amount

        new_eth = eth + quantity



        # ----------------------------------------------------
        # ��� �ż���
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
        # Portfolio ������Ʈ
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
        # Portfolio ĳ�� �ʱ�ȭ
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
# Portfolio ���� ETH ���� �ŵ�
# �������� ���
# DB ��ȸ �ּ�ȭ + Portfolio ĳ�� �ʱ�ȭ
# ------------------------------------------------------------

def sell_eth():


    conn = get_db()

    cur = conn.cursor(cursor_factory=RealDictCursor)



    try:


        # ----------------------------------------------------
        # Portfolio ��ȸ
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
        # ETH ������ �ŵ� �Ұ�
        # ----------------------------------------------------

        if eth <= 0:

            print("SELL SKIP : No ETH")

            return None



        # ----------------------------------------------------
        # ���� ETH ����
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
        # �ŵ� �ݾ�
        # ----------------------------------------------------

        trade_amount = eth * current_price



        # ----------------------------------------------------
        # ���� ���
        # ----------------------------------------------------

        profit = (

            current_price - avg_price

        ) * eth



        # ----------------------------------------------------
        # ROI ���
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
        # Portfolio ����
        # ----------------------------------------------------

        new_cash = cash + trade_amount

        new_eth = 0

        new_avg_price = 0



        # ----------------------------------------------------
        # Portfolio ������Ʈ
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
        # Portfolio ĳ�� �ʱ�ȭ
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
# PART 6-1 : ETH �� WDM Swap Engine
# ============================================================
# ====================================================
# PART 6-1
# ETH �� WDM Virtual DEX
# ====================================================

    calculate_swap()

    swap_eth_to_wdm()

    swap_wdm_to_eth()

    liquidity_pool()
# ------------------------------------------------------------
# ETH �� WDM Swap
# ------------------------------------------------------------

# ���� ����
# ETH�� ���� WDM �������� ��ȯ
# Portfolio ������Ʈ
# Trading Record ����
# ���� DEX ���� ����

# ------------------------------------------------------------
# WDM �� ETH Swap
# ------------------------------------------------------------

# ���� ����
# WDM�� ���� ETH �������� ��ȯ
# Portfolio ������Ʈ
# Trading Record ����
# ���� DEX ���� ����

# ------------------------------------------------------------
# ETH �� WDM Swap Price
# ------------------------------------------------------------

# ���� ����
# ���� ETH ����
# ���� WDM ����
# Swap ���� ���
# ���� ���ɼ��� ���

# ------------------------------------------------------------
# Swap Fee
# ------------------------------------------------------------

# ���� ����
# 0.3% Swap Fee
# ���� ���� ����

# ------------------------------------------------------------
# Liquidity Pool
# ------------------------------------------------------------

# ���� ����
# ETH Reserve
# WDM Reserve
# Constant Product (x*y=k)
# ���� Uniswap ��� ���� ����       
# ------------------------------------------------------------
# AUTO TRADE
# �ڵ��Ÿ� ����
#
# BUY  -> buy_eth()
# SELL -> sell_eth()
# HOLD -> �ƹ��͵� ����
#
# �ŷ���� ������ �� �Լ������� �����Ѵ�.
# ------------------------------------------------------------
def auto_trade(signal_data=None):

    # --------------------------------------------------------
    # signal_data�� ������ ���� ����
    # --------------------------------------------------------

    if signal_data is None:

        signal_data = generate_signal()

    # --------------------------------------------------------
    # ��ȣ ������
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
    # ETH Trading Analysis Record
    # �ڵ��ŸŴ� �������� �ʰ� �м� ����� ���
    # --------------------------------------------------------

    conn = get_db()
    cur = conn.cursor()

    # --------------------------------------------------------
    # �ŷ���� ����
    # --------------------------------------------------------

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
        signal,
        price,
        0,
        0,
        0,
        0,
        "ANALYSIS",
        rsi,
        ma20,
        ma60
    ))

    conn.commit()

    cur.close()
    close_db(conn)

    print(
        "ETH ANALYSIS SAVED :",
        signal,
        price,
        rsi,
        ma20,
        ma60
    )

    return True


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
    """Render the public homepage even when Neon is temporarily unavailable."""
    global HOME_CACHE

    current_time = time.time()
    donations = []

    # Prefer the short-lived cache so the homepage can still render during a DB outage.
    try:
        cached_data = HOME_CACHE.get("data")
        cached_time = HOME_CACHE.get("time", 0)
        if cached_data is not None and current_time - cached_time < 120:
            donations = cached_data
        else:
            conn = None
            cur = None
            try:
                conn = get_db()
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT quarter, net_profit, donation, proof
                    FROM donation_records
                    ORDER BY id DESC
                """)
                donations = cur.fetchall()
                HOME_CACHE["data"] = donations
                HOME_CACHE["time"] = current_time
            finally:
                if cur is not None:
                    try:
                        cur.close()
                    except Exception:
                        pass
                if conn is not None:
                    # Discard a connection if the query failed or the connection is broken.
                    try:
                        close_db(conn, discard=bool(getattr(conn, "closed", 0)))
                    except Exception:
                        pass
    except Exception as exc:
        # Do not let database quota/connection errors take down the public landing page.
        print(f"HOME DATABASE UNAVAILABLE; rendering homepage without donation records: {exc}")
        cached_data = HOME_CACHE.get("data")
        if cached_data is not None:
            donations = cached_data
        else:
            donations = []

    return render_template("donation.html", donations=donations)
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

    # --------------------------------------------------------
    # Whitepaper Cache
    # --------------------------------------------------------

    if (

        CACHE["whitepaper"] is None

        or

        time.time() - CACHE["whitepaper_time"] > CACHE_TIME["whitepaper"]

    ):

        conn = get_db()

        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT *
            FROM donation_records
            ORDER BY id DESC
        """)

        CACHE["whitepaper"] = cur.fetchall()

        CACHE["whitepaper_time"] = time.time()

        cur.close()

        close_db(conn)

    return render_template(

        "whitepaper.html",

        donations=CACHE["whitepaper"]

    )
# -----------------------------
# Poem
# -----------------------------
@app.route("/poem")
def poem():
    return render_template("poem.html")

# ------------------------------------------------------------
# ETH Price Popup Page
# price.html ��¿�
# ------------------------------------------------------------
@app.route("/price")
def price():

    # --------------------------------------------------------
    # DB �ֽ� ����
    # --------------------------------------------------------

    live_price = get_latest_price()

    # �ֱ� ���� ��� ��������
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
# JavaScript / �ڵ� ���ſ�
# ------------------------------------------------------------
@app.route("/price-api")
def price_api():

    # --------------------------------------------------------
    # DB �ֽ� ����
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
# ������ ���� ��ú���
# ==========================================================

@app.route("/admin/dashboard")
def admin_dashboard():

    # ------------------------------------------------------
    # Admin Login Check
    # ������ �α��� ���� Ȯ��
    # ------------------------------------------------------

    if not session.get("admin"):

        return redirect("/admin/login")

    # ------------------------------------------------------
    # Admin Dashboard
    # ������ ��ú��� ���
    # ------------------------------------------------------

    return render_template(
        "admin_dashboard.html"
    )

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
# �Ϲ� ����� ���� ���
# �ٿ��ֱ� ��ġ :
# ���� @app.route("/announcement") ���� ��
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
# ������ ���� ���� ����
# �ٿ��ֱ� ��ġ :
# @app.route("/announcement/<int:id>") �Ʒ�
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

        # ���
        if action == "add":

            add_announcement(title, content)

        # ����
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
    # ���� ���
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
# �Ϲ� ����� ���� �󼼺���
# �ٿ��ֱ� ��ġ :
# @app.route("/announcement") �ٷ� �Ʒ�
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
# ������ ���� ���
# �ٿ��ֱ� ��ġ :
# @app.route("/announcement") �ٷ� �Ʒ�
# ==========================================================

@app.route("/announcement/add", methods=["GET", "POST"])
def announcement_add():

    # ----------------------------------------------------------
    # ������ �α��� Ȯ��
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
# ���� ����
# ==========================================================

@app.route("/announcement/edit/<int:id>", methods=["GET", "POST"])
def edit_announcement_route(id):

    # ----------------------------------------------------------
    # ������ �α��� Ȯ��
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

    # ������ �α��� Ȯ��
    if not session.get("admin"):
        return redirect("/admin/login")

    delete_announcement(id)

    # ������ ������� �̵�
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
# Content ��� / ���� / ����
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
    # DB + Uploaded File ����
    # --------------------------------------------------------

    delete_id = request.args.get("delete")


    if delete_id:


        # ----------------------------------------------------
        # 1. ������ ���� ���� ��ȸ
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
        # 2. ���� ���ε� ���� ����
        # ----------------------------------------------------

        if file_info and file_info["file_path"]:


            delete_file_from_github(

                file_info["file_path"]

            )


        # ----------------------------------------------------
        # 3. PostgreSQL ������ ����
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
            # ���� ���ϸ� ����
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

    """,
    (
        content_id,
    ))


    if not row:

        return "Content Not Found"


    return render_template(
        "admin3_content_detail.html",
        row=row
    )



# ============================================================
# Public Content List
# ����� ������ ���
# Cache ����
# ============================================================

@app.route("/content")
def content():


    # --------------------------------------------------------
    # Content Cache Check
    # --------------------------------------------------------

    if (

        CACHE["content"] is None

        or

        time.time() - CACHE["content_time"]
        > CACHE_TIME["content"]

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
# ������ �󼼺���
# ��ȸ�� ���� + Cache �ʱ�ȭ
# ============================================================

@app.route("/content/<int:id>")
def content_detail(id):


    # --------------------------------------------------------
    # Content ��ȸ
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
    # Content ���� Ȯ��
    # --------------------------------------------------------

    if row is None:

        return "Content Not Found", 404



    # --------------------------------------------------------
    # ��ȸ�� ����
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
    # �� ������ ���
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
# ������ FAQ ����
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
        # FAQ ���
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
    # �������
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

    # ������ ������ ����
    if not request.path.startswith("/admin"):

        save_access_log()

# ==========================================================
# Admin Access Statistics
# ==========================================================

@app.route("/admin/statistics")
def admin_statistics():

    if not session.get("admin"):

        return redirect("/admin/login")


    # ==========================================================
    # Total Visitors
    # ���� �湮�� ��
    # ==========================================================

    total = fetch_one(

        """
        SELECT

            total_visits

        FROM

            site_statistics

        WHERE

            id = 1

        """

    )


    total = total["total_visits"]


    # ==========================================================
    # Today Visitors
    # ���� �湮�� ��
    # ==========================================================

    today = fetch_one(

        """

        SELECT

            today_visits

        FROM

            site_statistics

        WHERE

            id = 1

        """

    )


    today = today["today_visits"]

    # ==========================================================
    # Top Pages
    # ���� �湮�� ������
    # ==========================================================

    pages = fetch_all(

        """

        SELECT

            path,

            COUNT(*) AS cnt

        FROM

            access_logs

        GROUP BY

            path

        ORDER BY

            cnt DESC

        LIMIT 10

        """

    )


    # ==========================================================
    # Daily Visitor Statistics
    # �Ϻ� �湮 ���
    # ==========================================================

    daily_stats = fetch_all(

        """

        SELECT

            created_at::date AS day,

            COUNT(DISTINCT ip) AS visitors

        FROM

            access_logs

        GROUP BY

            day

        ORDER BY

            day DESC

        LIMIT 7

        """

    )


    # ==========================================================
    # Monthly Visitor Statistics
    # ���� �湮 ���
    # ==========================================================

    monthly_stats = fetch_all(

        """

        SELECT

            TO_CHAR(created_at,'YYYY-MM') AS month,

            COUNT(DISTINCT ip) AS visitors

        FROM

            access_logs

        GROUP BY

            month

        ORDER BY

            month DESC

        LIMIT 12

        """

    )


    # ==========================================================
    # Country Visitor Statistics
    # ������ �湮 ���
    # ==========================================================

    country_stats = fetch_all(

        """

        SELECT

            country,

            COUNT(DISTINCT ip) AS visitors

        FROM

            access_logs

        WHERE

            country IS NOT NULL

        GROUP BY

            country

        ORDER BY

            visitors DESC

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
    # ������� ������ ���
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
# ��� ������ ������ ������
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
# Donation �߰�
# ������ �α��� �ʿ�
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
# Donation ����
# ������ �α��� �ʿ�
# ------------------------------------------------------------

@app.route("/admin/donation/edit/<int:id>", methods=["POST"])
def edit_donation(id):


    # ������ Ȯ��
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

    # --------------------------------------------------------
    # Whitepaper Cache Clear
    # --------------------------------------------------------

    CACHE["whitepaper"] = None

    CACHE["whitepaper_time"] = 0
 
 
    return redirect(
        "/admin/donation"
    )



# ------------------------------------------------------------
# Donation ����
# ������ �α��� �ʿ�
# ------------------------------------------------------------

@app.route("/admin/donation/delete/<int:id>")
def delete_donation(id):


    # ������ Ȯ��
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
# ������ ������
# ------------------------------------------------------------

@app.route("/admin/community")
def admin_community():

    # --------------------------------------------------------
    # ������ �α��� Ȯ��
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
# Community ����
# ������ �α��� �ʿ�
# ------------------------------------------------------------

@app.route(
    "/admin/community/save",
    methods=["POST"]
)
def save_community():

    # --------------------------------------------------------
    # ������ �α��� Ȯ��
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
    # �����Ͱ� ������ INSERT
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
    # �����Ͱ� ������ UPDATE
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
# ȯ��⿡ ���� ETH / WDM ���� ����
# ------------------------------------------------------------

@app.route("/swap-api")
def swap_api():

    try:

        # ----------------------------------------------------
        # ETH ���� ����
        # ----------------------------------------------------

        eth_price = get_latest_price()

        if eth_price is None:
            eth_price = 0.0

        eth_price = float(eth_price)


        # ----------------------------------------------------
        # WDM ���� ����
        # ���� ���� ���� �Լ� ���
        # ----------------------------------------------------

        wdm_price = get_latest_wdm_price()

        if wdm_price is None:
            wdm_price = 0.0

        wdm_price = float(wdm_price)


        # ----------------------------------------------------
        # ��� ��ȯ
        # ----------------------------------------------------

        return jsonify({

            "success": True,

            "eth_price": eth_price,

            "wdm_price": wdm_price

        })


    except Exception as e:

        print("SWAP API ERROR:", e)

        return jsonify({

            "success": False,

            "eth_price": 0.0,

            "wdm_price": 0.0,

            "message": "Price data unavailable"

        })


# ============================================================
# WDM Converter Calculation API
# ȯ�� ��� ����
# ============================================================

@app.route("/calculate-conversion", methods=["POST"])
def calculate_conversion():

    try:

        data = request.get_json()

        if not data:

            return jsonify({

                "success": False,

                "message": "No data received"

            })


        # ----------------------------------------------------
        # ȯ�� ����
        # ----------------------------------------------------

        direction = data.get(
            "direction",
            "ETH_TO_WDM"
        )


        # ----------------------------------------------------
        # �Է� �ݾ�
        # ----------------------------------------------------

        amount = data.get(
            "amount",
            0
        )


        # ----------------------------------------------------
        # ���� ����
        # /swap-api�� ������ ���� ���� �Լ� ���
        # ----------------------------------------------------

        eth_price = get_latest_price()

        if eth_price is None:

            eth_price = 0.0

        eth_price = float(eth_price)


        wdm_price = get_latest_wdm_price()

        if wdm_price is None:

            wdm_price = 0.0

        wdm_price = float(wdm_price)


        # ----------------------------------------------------
        # ȯ�� ���
        # ��� �Լ����� ������ ����
        # ----------------------------------------------------

        result = calculate_wdm_conversion(

            direction,

            amount,

            eth_price,

            wdm_price

        )


        return jsonify(result)


    except Exception as e:

        print(
            "CONVERSION ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message": "Conversion calculation failed"

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
# DB ��ȸ �ּ�ȭ ĳ�� ����
# Golden Cross / Dead Cross ����
# ------------------------------------------------------------

@app.route("/chart-data")
def chart_data():

    import time


    now = time.time()



    # --------------------------------------------------------
    # Chart Cache Ȯ��
    # 30�� �̳� DB ��ȸ ����
    # --------------------------------------------------------

    if CACHE["chart_data"]:


        if now - CACHE["chart_time"] < CACHE_TIME["chart_data"]:


            return jsonify(
                CACHE["chart_data"]
            )



    # --------------------------------------------------------
    # DB ����
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
    # �ֽż� �� ���ż� ����
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
    # ������ ����
    # --------------------------------------------------------

    for i, row in enumerate(rows):


        # �ð�

        labels.append(

            row["created_at"].strftime("%H:%M:%S")

        )



        # ����

        price = float(row["price"])

        prices.append(price)



        # �̵����

        m20 = None

        m60 = None



        if row["ma20"] is not None:

            m20 = float(row["ma20"])



        if row["ma60"] is not None:

            m60 = float(row["ma60"])



        ma20.append(m20)

        ma60.append(m60)



        # �⺻��

        buy.append(None)

        sell.append(None)

        golden.append(None)

        dead.append(None)



        # ù ������ �� �Ұ�

        if i == 0:

            continue



        prev20 = ma20[i - 1]

        prev60 = ma60[i - 1]



        # �̵���� ������ ����

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
    # JSON ������ ����
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
    # Chart Cache ����
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
# ���� wdm_chart_data() �Լ� ��ü ���� �� �ٿ��ֱ�
# ==========================================================

# ============================================================
# WDM CHART DATA
# ��Ʈ ���� ������
# ============================================================

# ==========================================================
# WDM Chart Data
# WDM ���� �̷� �� ��Ʈ ������
# ==========================================================

@app.route("/wdm-chart-data")
def wdm_chart_data():

    try:

        # --------------------------------------------------
        # WDM Price History ��ȸ
        # --------------------------------------------------

        rows = get_wdm_price_history(100)

        # --------------------------------------------------
        # Chart Data
        # --------------------------------------------------

        labels = []
        prices = []

        # --------------------------------------------------
        # ������ ������ �� �ֽ� ������ ������ ����
        # --------------------------------------------------

        rows = list(reversed(rows))

        for row in rows:

            labels.append(
                str(row["created_at"])
            )

            prices.append(
                float(row["price"])
                if row["price"] is not None
                else None
            )

        # --------------------------------------------------
        # JSON ��ȯ
        # --------------------------------------------------

        return jsonify({

            "labels": labels,

            "prices": prices

        })

    except Exception as e:

        traceback.print_exc()

        return jsonify({

            "error": str(e)

        }), 500
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

# A temporary Neon quota/outage must not prevent Gunicorn from importing Flask.
# Existing tables/data are not deleted by this startup block.
DB_STARTUP_OK = False
try:
    init_db()
    insert_default_community()
    insert_default_portfolio()
    insert_default_meme()
    insert_test_data()
    DB_STARTUP_OK = True
    print("[DB STARTUP] Database initialization completed.")
except Exception as e:
    print("[DB STARTUP] Database unavailable; app starts in degraded mode:", e)
    traceback.print_exc()

# PART 9 : Thread
# ============================================================

# ============================================================
# Start Auto Save Threads
# ============================================================

# Enable explicitly with ENABLE_BACKGROUND_JOBS=true after checking Neon quota.
if (
    __name__ != "__main__"
    and os.environ.get("ENABLE_BACKGROUND_JOBS", "false").strip().lower()
    in ("1", "true", "yes", "on")
):
    threading.Thread(target=auto_save_eth, daemon=True, name="wdm-auto-eth").start()
    threading.Thread(target=auto_save_wdm, daemon=True, name="wdm-auto-wdm").start()
# PART 10 : app.run()
# ==========================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=False

    )
