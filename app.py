from flask import Flask, jsonify
import requests

app = Flask(__name__)


@app.route("/")
def home():
    return "Oracle Server Running"


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


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
