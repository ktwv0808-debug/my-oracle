from flask import Flask, jsonify
import requests

app = Flask(__name__)


@app.route("/")
def home():
    return "Oracle Server Running"


@app.route("/price")
def price():

    url = "https://api.binance.com/api/v3/ticker/price"

    params = {
        "symbol": "ETHUSDT"
    }

    response = requests.get(
        url,
        params=params
    )

    data = response.json()

    return jsonify(
        {
            "ETH_USDT": data["price"]
        }
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
