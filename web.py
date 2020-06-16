import hashlib
import json
import os
from multiprocessing import Pipe, Process
from threading import Thread
from time import sleep

from flask import Flask, Response, render_template, request, send_from_directory

import plagiarism

UPLOAD_DIR = os.path.join(".", "static")
app = Flask(__name__)
parent_connections = {}
child_connections = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/detect", methods=["POST"])
def detect():
    with request.files["input_file"].stream as input_file:
        csv_data = input_file.read()
    md5 = hashlib.md5(csv_data).hexdigest()
    directory = os.path.join(UPLOAD_DIR, md5)
    os.makedirs(directory, exist_ok=True)
    input_file = os.path.join(directory, "ItemsDeliveredRawReport.csv")
    output_file = os.path.join(directory, "plagiarism.xlsx")
    with open(input_file, "wb") as csv_file:
        csv_file.write(csv_data)
    names = plagiarism.get_names(plagiarism.read_csv(input_file))
    parent_connections[md5], child_connections[md5] = Pipe()
    process = Process(target=plagiarism.detect_plagiarism, args=(input_file, output_file, child_connections[md5]))
    process.start()
    return render_template("processing.html", count=len(names), md5=md5, names=names)


@app.route('/static/<path:filename>')
def download_file(filename):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)


@app.route("/progress/<md5>")
def progress(md5):
    def event_log():
        try:
            while True:
                status, name = parent_connections[md5].recv()
                if status is None:
                    yield ": keep-alive\n"
                elif status == "completed":
                    data = json.dumps({"status": "completed"})
                    yield f"data: {data}\n\n"
                    break
                else:
                    data = json.dumps({"status": status, "name": name})
                    yield f"data: {data}\n\n"
        except EOFError:
            pass

        del child_connections[md5]
        del parent_connections[md5]

    if md5 in parent_connections:
        response = Response(event_log())
        response.headers["content-type"] = "text/event-stream"
        response.headers["cache-control"] = "no-cache"
        response.headers["connection"] = "keep-alive"
        return response


def keepalive():
    while True:
        for md5 in child_connections:
            child_connections[md5].send((None, None))
        sleep(20)


if __name__ == "__main__":
    Thread(target=keepalive).start()
    app.run(host="0.0.0.0", port=os.getenv("PORT", 8080), debug=True)
