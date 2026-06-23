from flask import Flask, jsonify
import requests

app = Flask(__name__)


@app.route("/")
def home():
    return "Oracle Server Running"


@app.route("/price")
def price():

    url = "https://api.coincap.io/v2/assets/ethereum"

    response = requests.get(url)

    data = response.json()

    return jsonify(
        {
            "ETH_USD": data["data"]["priceUsd"],
            "source": "CoinCap"
        }
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
