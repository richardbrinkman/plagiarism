import hashlib
import io
import json
import plagiarism
import os
from flask import Flask, Response, render_template, request, redirect
from multiprocessing import Pipe, Process

UPLOAD_DIR = os.path.join(".", "static")
app = Flask(__name__)
parent_connection = {}


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
    names, _ = plagiarism.read_csv(input_file)
    parent_connection[md5], child_connection = Pipe()
    process = Process(target=plagiarism.detect_plagiarism, args=(input_file, output_file, child_connection))
    process.start()
    return render_template("processing.html", count=len(names), md5=md5, names=names)


@app.route("/progress/<md5>")
def progress(md5):
    def event_log():
        try:
            while True:
                status, name = parent_connection[md5].recv()
                data = json.dumps({"status": status, "name": name})
                yield f"data: {data}\n\n"
        except EOFError:
            pass
        data = json.dumps({"status": "completed"})
        yield f"data: {data}\n\n"
        # del parent_connection[md5]

    if md5 in parent_connection:
        response = Response(event_log())
        response.headers["content-type"] = "text/event-stream"
        response.headers["cache-control"] = "no-cache"
        response.headers["connection"] = "keep-alive"
        return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=os.getenv("PORT", 8080), debug=True)
