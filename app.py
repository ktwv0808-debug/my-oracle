from flask import Flask, jsonify
import requests

app = Flask(__name__)


@app.route("/")
def home():
    return "Oracle Server Running"


# ETH 가격
@app.route("/price")
def price():

    try:

        url = "https://api.coinbase.com/v2/prices/ETH-USD/spot"

        response = requests.get(
            url,
            timeout=10
        )

        data = response.json()

        return jsonify(
            {
                "ETH_USD": data["data"]["amount"],
                "source": "Coinbase"
            }
        )

    except Exception as e:

        return jsonify({
            "error": str(e)
        })


# KTW 가격 (테스트용)
@app.route("/ktw-price")
def ktw_price():

    ktw_price_usd = 0.0001

    return jsonify(
        {
            "symbol": "KTW",
            "price_usd": ktw_price_usd,
            "source": "Oracle Test Price"
        }
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
2) GitHub 저장

Commit:

Update app.py
