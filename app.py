from flask import Flask, jsonify
import requests

app = Flask(__name__)


@app.route("/")
def home():
    return "Oracle Server Running"


@app.route("/price")
def price():

    try:
        url = "https://api.binance.com/api/v3/ticker/price"

        params = {
            "symbol": "ETHUSDT"
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        data = response.json()

        return jsonify(data)

    except Exception as e:

        return jsonify({
            "error": str(e)
        })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
