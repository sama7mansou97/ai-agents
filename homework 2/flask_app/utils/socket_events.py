from flask import current_app, session
from flask_socketio import emit
from .llm import (
    assess_message_risk,
    request_human_validation,
    handle_validation_response,
    handle_ai_chat_request
)

def init_socket_events(socketio):
    @socketio.on('send_message')
    def handle_message(data):
        user_message = data.get('message', '').strip()

        if not user_message:
            return

        try:
            db = getattr(current_app, 'db', None)
            
            # فحص حالة الأمان أو معالجة الرسالة العادية
            if session.get('pending_validation'):
                ai_response = handle_validation_response(db, user_message)
            elif assess_message_risk(user_message):
                ai_response = request_human_validation(user_message)
            else:
                role = data.get('role', 'Orchestrator')
                ai_response = handle_ai_chat_request(db, role=role, message=user_message)
                
        except Exception as error:
            print(f"LLM error: {error}")
            ai_response = "Sorry, something went wrong answering that."

        emit('receive_message', {'response': ai_response})