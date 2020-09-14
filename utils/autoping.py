from flask import Flask
from threading import Thread
import pickle
import json
import sys

app = Flask('')

@app.route('/')
def main():
    return 'trovebot online'

def run():
    app.run(host="0.0.0.0", port=8080)

def autoping():
    server = Thread(target=run)
    server.start()