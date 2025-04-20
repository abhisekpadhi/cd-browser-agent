from flask import Flask, jsonify, request, Response
from flask_sse import sse
import json
import threading
from service.query_processor import query_processor_service
from lib.utils import generate_query_id
from datetime import datetime
from flask_cors import CORS


app = Flask(__name__)

# Enable CORS
CORS(app, resources={
    r"/stream": {"origins": "http://localhost:3000"},
    r"/interact": {"origins": "http://localhost:3000"},
    r"/": {"origins": "http://localhost:3000"}
})

app.config["REDIS_URL"] = "redis://localhost:6379"
app.register_blueprint(sse, url_prefix='/stream')

@app.route('/')
def health():
    return jsonify({"status": "ok"})

@app.route('/push')
def publish_hello():
    sse.publish({"message": "Hello!"})
    return "Message sent!"

@app.route('/interact', methods=['POST'])
def interact():
    data = request.get_json()
    query = data.get('query')
    query_id = data.get('query_id')
    
    if not query:
        return jsonify({"error": "Query is required"}), 400
        
    if not query_id:
        query_id = generate_query_id()
    
    # Save query to file
    query_data = {
        "query": query,
        "query_id": query_id,
        "status": "pending",
        "result": None,
        "created_at": datetime.now().isoformat()
    }
    
    with open(f"./jobs/{query_id}.json", "w") as f:
        json.dump(query_data, f)
    
    with app.app_context():
        sse.publish({"message": "Processing query...", "query_data": query_data})
    
    # Start processing in background
    threading.Thread(target=query_processor_service.process_query, args=(query_id, app,)).start()
    
    return jsonify({
        "query_id": query_id,
        "status": "processing"
    })
