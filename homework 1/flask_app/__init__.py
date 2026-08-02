import os
from flask import Flask
from flask_socketio import SocketIO
from dotenv import load_dotenv

socketio = SocketIO()
load_dotenv()
def create_app():
    # المسار الرئيسي للمشروع
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # homework 1
    root_dir = os.path.dirname(base_dir) # ai-agents
    
    # مسارات homework 0
    hw0_dir = os.path.join(root_dir, 'homework 0', 'flask_app')
    hw0_templates = os.path.join(hw0_dir, 'templates')
    hw0_static = os.path.join(hw0_dir, 'static')

    app = Flask(__name__, template_folder=hw0_templates, static_folder=hw0_static)
    app.config['SECRET_KEY'] = 'secret!'

    from .database.database import Database

    # جعل قاعدة البيانات تقرأ مباشرة من hw0_dir
    db_path = os.path.join(app.root_path, 'database', 'resume.db')
    db = Database(db_path, hw0_dir=hw0_dir)
    db.createTables(purge=True)

    app.db = db

    with app.app_context():
        from . import routes
        from .utils import socket_events

    socketio.init_app(app)
    return app