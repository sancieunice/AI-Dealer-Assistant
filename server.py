"""Flask API server for VIKMO Dealer Assistant."""

from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
import sys
import json

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assistant.agent import DealerAssistant
from assistant.orders import persist_order

app = Flask(__name__)
CORS(app)

# Initialize the assistant
bot = DealerAssistant()

# Store conversation state
conversation_state = {
    "messages": [],
    "order_draft": None
}


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle chat messages."""
    try:
        data = request.get_json()
        message = data.get("message", "").strip()
        
        if not message:
            return jsonify({"error": "Empty message"}), 400
        
        # Add user message to history
        conversation_state["messages"].append({
            "role": "user",
            "content": message
        })
        
        # Process with assistant
        state = bot.chat(message)
        
        # Prepare response
        assistant_message = {
            "role": "assistant",
            "content": state.get("final_answer", ""),
            "products": state.get("retrieved_docs", []),
            "order_summary": state.get("order_summary")
        }
        
        # Update order draft if order is ready
        if state.get("order_summary", {}).get("status") == "ready_for_confirmation":
            conversation_state["order_draft"] = state.get("order_summary")
        
        # Add to message history
        conversation_state["messages"].append(assistant_message)
        
        return jsonify({
            "message": assistant_message["content"],
            "products": assistant_message["products"],
            "order_summary": assistant_message["order_summary"],
            "messages": conversation_state["messages"]
        }), 200
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/reset", methods=["POST"])
def reset():
    """Reset conversation."""
    try:
        bot.reset()
        conversation_state["messages"] = []
        conversation_state["order_draft"] = None
        return jsonify({"status": "reset"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/messages", methods=["GET"])
def get_messages():
    """Get all messages in current conversation."""
    return jsonify({"messages": conversation_state["messages"]}), 200


@app.route("/api/order-draft", methods=["GET"])
def get_order_draft():
    """Get current order draft."""
    return jsonify({"order_draft": conversation_state["order_draft"]}), 200


@app.route("/api/confirm-order", methods=["POST"])
def confirm_order():
    """Confirm the current order draft."""
    try:
        if not conversation_state["order_draft"]:
            return jsonify({"error": "No order draft to confirm"}), 400
        
        # In a real scenario, this would save the order to a database
        order = conversation_state["order_draft"]
        saved = persist_order(order)
        conversation_state["order_draft"] = None
        
        return jsonify({
            "status": "confirmed",
            "order": saved,
            "message": f"Order {saved['order_id']} confirmed for {saved.get('dealer', 'Customer')}"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
