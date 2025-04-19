from flask import Flask, jsonify, request, Response
from flask_sse import sse
import json
import threading
from query_processor import process_query
from lib.utils import generate_query_id

app = Flask(__name__)
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
        "query_id": query_id
    }
    
    with open(f"./jobs/{query_id}.json", "w") as f:
        json.dump(query_data, f)
    
    # Start processing in background
    threading.Thread(target=process_query, args=(query_id, app,)).start()
    
    return jsonify({
        "query_id": query_id,
        "status": "processing"
    })
