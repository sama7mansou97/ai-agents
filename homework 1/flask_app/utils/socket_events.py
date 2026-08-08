from flask_socketio import emit
from flask_app import socketio
from flask_app.utils.llm import handle_ai_chat_request

db = None

# Step 5: Wire the Orchestrator into chat
@socketio.on('send_message')
def handle_message(data):
    global db
    if db is None:
        from flask import current_app
        db = current_app.db

    user_message = data.get('message', '').strip()
    if not user_message:
        return

    try:
        ai_response = handle_ai_chat_request(db, role="Orchestrator", message=user_message)
    except Exception as error:
        print(f"LLM error: {error}")
        ai_response = "Sorry, something went wrong answering that."

    emit('receive_message', {'response': ai_response})


