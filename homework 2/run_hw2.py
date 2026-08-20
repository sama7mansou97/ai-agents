import os
import sys
import importlib

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
hw1_dir = os.path.join(base_dir, "homework 1")

if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
if hw1_dir not in sys.path:
    sys.path.insert(0, hw1_dir)

from flask_app import create_app, socketio

app = create_app()

# تفعيل أحداث HW2 على كائن socketio المباشر
hw2_events = importlib.import_module("homework 2.flask_app.utils.socket_events")
hw2_events.init_socket_events(socketio)

if __name__ == '__main__':
    print("🚀 Running Homework 2 Semantic Search Server...")
    socketio.run(app, debug=True, port=8080)