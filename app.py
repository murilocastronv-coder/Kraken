"""Entrypoint: serve the MT5 demo connector instead of the paper-trading simulator."""
import os
from mt5_connector import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
