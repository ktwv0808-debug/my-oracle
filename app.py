from flask import Flask, jsonify, render_template
import requests


app = Flask(__name__)


# ------------------------
# 메인 페이지
# ------------------------

@app.route("/")
def home():

    return """
    <h1>Oracle Server Running</h1>

    <p>
    <a href="/price">
    ETH Price API
    </a>
    </p>

    <p>
    <a href="/ktw-price">
    W-donation Token API
    </a>
    </p>

    <p>
    <a href="/donation">
    Social Contribution
    </a>
    </p>
    """



# ------------------------
# ETH 가격 Oracle
# ------------------------

@app.route("/price")
def price():

    try:

        url = (
            "https://api.coinbase.com/v2/"
            "prices/ETH-USD/spot"
        )


        response = requests.get(
            url,
            timeout=10
        )


        data = response.json()


        return jsonify({

            "ETH_USD":
            data["data"]["amount"],

            "source":
            "Coinbase"

        })


    except Exception as e:


        return jsonify({

            "error":
            str(e)

        })




# ------------------------
# W-donation Token 가격 API
# ------------------------

@app.route("/ktw-price")
def ktw_price():


    return jsonify({

        "symbol":
        "W-donation",


        "price_usd":
        "0.0001",


        "donation":
        "10% quarterly profit to World Vision",


        "source":
        "Oracle Test Price"

    })




# ------------------------
# 후원 페이지
# ------------------------

@app.route("/donation")
def donation():

    return render_template(
        "donation.html"
    )




# ------------------------
# 실행
# ------------------------

if __name__ == "__main__":


    app.run(

        host="0.0.0.0",

        port=5000

    )
