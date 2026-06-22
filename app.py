from flask import Flask, jsonify
import requests

app = Flask(__name__)


@app.route("/")
def home():
    return "Oracle Server Running"


@app.route("/price")
def price():

    url = "https://api.coingecko.com/api/v3/simple/price"

    params = {
        "ids": "ethereum",
        "vs_currencies": "usd"
    }

    result = requests.get(
        url,
        params=params
    ).json()


    eth = result["ethereum"]["usd"]


    return jsonify(
        {
            "ETH_USD": eth
        }
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )