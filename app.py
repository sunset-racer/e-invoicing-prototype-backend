import os
import time
import json
import uuid
import random
from datetime import datetime
from decimal import Decimal

from flask import Flask, request, jsonify
from flask_cors import CORS
from bson import ObjectId
from pydantic import ValidationError
from dotenv import load_dotenv

from db.mongo import MongoDB
from schemas import InvoiceSchema, InvoiceStatus

# Load environment variables from .env file (for local development)
load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION ---

# 1. Allow CORS for all domains (Essential for Vercel frontend to talk to Render backend)
CORS(app, resources={r"/api/*": {"origins": "*"}}) 

# 2. Database Connection Logic
# PRIORITY: Look for MONGO_URI in environment (Render / .env)
mongo_uri = os.environ.get("MONGO_URI")

if not mongo_uri:
    raise ValueError("CRITICAL: MONGO_URI is not set. Application cannot start.")

try:
    MongoDB.connect(mongo_uri) # type: ignore
    print(f"Connected to MongoDB")
except Exception as e:
    print(f"Critical Error: Could not connect to MongoDB. {e}")

# --- HELPER FUNCTIONS ---

def get_collection():
    """Helper function to get the invoices collection reliably."""
    return MongoDB.get_db()['invoices'] # type: ignore

def serialize_doc(doc):
    """
    Converts complex MongoDB types (ObjectId, Decimal, Date) into JSON-friendly formats.
    """
    if not doc:
        return None
    
    # Convert ObjectId to string
    doc["_id"] = str(doc["_id"])
    
    # Convert Decimals to string (for JSON precision)
    for key, value in doc.items():
        if isinstance(value, Decimal):
            doc[key] = str(value)
    
    # Handle Items List
    if "items" in doc:
        for item in doc["items"]:
            for k, v in item.items():
                if isinstance(v, Decimal):
                    item[k] = str(v)
                
    return doc

def parse_date(date_str):
    """Safely parses ISO date strings to datetime objects."""
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None

# --- MOCK GATEWAY LOGIC ---

def mock_external_gateway(invoice_doc):
    """
    Simulates the ZATCA/PEPPOL Government API.
    Returns: { "status": "SUCCESS"|"FAILED", "clearance_id": str|None }
    """
    time.sleep(random.uniform(0.8, 1.5)) # Realistic Jitter
    
    # 1. Check for explicit Failure Trigger
    receiver_id = invoice_doc.get("receiver_id", "").upper()
    if "FAIL" in receiver_id:
        print(f"🚫 [Gateway] Rejected: Receiver ID '{receiver_id}' flagged.")
        return {"status": InvoiceStatus.FAILED.value, "clearance_id": None}
    
    # 2. Data Integrity & Schema Validation
    try:
        payload = invoice_doc.copy()
        if '_id' in payload:
            payload['_id'] = str(payload['_id'])

        validated_invoice = InvoiceSchema(**payload)
        
        # 3. Business Rule Checks
        if validated_invoice.total_amount < 0:
            print("🚫 [Gateway] Rejected: Negative Total Amount.")
            return {"status": InvoiceStatus.FAILED.value, "clearance_id": None}

    except ValidationError as e:
        error_msg = e.errors()[0]['msg'] if e.errors() else "Invalid Data"
        print(f"🚫 [Gateway] Validation Failed: {error_msg}")
        return {"status": InvoiceStatus.FAILED.value, "clearance_id": None}
    except Exception as e:
        print(f"🔥 [Gateway] Critical Error: {str(e)}")
        return {"status": InvoiceStatus.FAILED.value, "clearance_id": None}
    
    # 4. Success Path
    mock_clearance_id = str(uuid.uuid4())
    print(f"✅ [Gateway] Cleared. ID: {mock_clearance_id}")
    
    return {
        "status": InvoiceStatus.SUCCESS.value, 
        "clearance_id": mock_clearance_id
    }

# --- ROUTES ---

@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        MongoDB.get_db().command('ping') # type: ignore
        return jsonify({"status": "Online", "database": "Connected"}), 200
    except Exception as e:
        return jsonify({"status": "Offline", "error": str(e)}), 500

@app.route('/api/invoices', methods=['GET'])
def get_invoices():
    """Fetch all invoices, sorted by newest first (created_at desc)."""
    collection = get_collection()
    cursor = collection.find().sort("created_at", -1)
    invoices = [serialize_doc(doc) for doc in cursor]
    return jsonify(invoices)

@app.route('/api/invoices/<id>', methods=['GET'])
def get_invoice_detail(id):
    collection = get_collection()
    try:
        invoice = collection.find_one({"_id": ObjectId(id)})
    except Exception:
        return jsonify({"error": "Invalid Invoice ID"}), 400
        
    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
    
    return jsonify(serialize_doc(invoice))

@app.route('/api/invoices', methods=['POST'])
def create_invoice():
    try:
        data = request.json
        
        # 1. Validation & Math
        invoice_obj = InvoiceSchema(**data)
        
        # 2. Serialization
        doc = json.loads(invoice_obj.model_dump_json())
        
        # 3. Date Handling (Crucial for Sorting)
        if 'created_at' in doc and doc['created_at']:
            parsed_date = parse_date(doc['created_at'])
            if parsed_date:
                doc['created_at'] = parsed_date
        
        doc['status'] = InvoiceStatus.RECEIVED.value
        
        # 4. Insert
        result = get_collection().insert_one(doc)
        
        return jsonify({
            "message": "Invoice created successfully", 
            "id": str(result.inserted_id),
            "status": doc['status'],
            "total_amount": doc['total_amount']
        }), 201

    except ValidationError as e:
        return jsonify({"error": "Validation Failed", "details": e.errors()}), 400
    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

@app.route('/api/invoices/<id>/validate', methods=['POST'])
def validate_invoice(id):
    collection = get_collection()
    
    try:
        invoice = collection.find_one({"_id": ObjectId(id)})
    except Exception:
        return jsonify({"error": "Invalid Invoice ID"}), 400

    if not invoice:
        return jsonify({"error": "Invoice not found"}), 404
        
    result = mock_external_gateway(invoice)
    
    update_fields = {"status": result["status"]}
    if result["clearance_id"]:
        update_fields["clearance_id"] = result["clearance_id"]
        
    collection.update_one({"_id": ObjectId(id)}, {"$set": update_fields})
    
    message = "Invoice Cleared & Signed" if result["status"] == "SUCCESS" else "Invoice Rejected"
    return jsonify({
        "status": result["status"], 
        "clearance_id": result.get("clearance_id"),
        "message": message
    })

@app.route('/api/invoices/<id>', methods=['PUT'])
def update_invoice(id):
    collection = get_collection()
    
    try:
        existing = collection.find_one({"_id": ObjectId(id)})
    except Exception:
        return jsonify({"error": "Invalid Invoice ID"}), 400

    if not existing:
        return jsonify({"error": "Invoice not found"}), 404
        
    if existing.get("status") == InvoiceStatus.SUCCESS.value:
        return jsonify({"error": "Forbidden: Cannot edit a cleared invoice."}), 403
        
    try:
        update_data = request.json
        
        # Validate logic
        validated_update = InvoiceSchema(**update_data)
        doc = json.loads(validated_update.model_dump_json())
        
        # Date Handling
        if 'created_at' in doc:
            parsed_date = parse_date(doc['created_at'])
            if parsed_date:
                doc['created_at'] = parsed_date

        # Protect System Fields
        if 'id' in doc: del doc['id']
        if 'status' in doc: del doc['status'] 
        
        collection.update_one({"_id": ObjectId(id)}, {"$set": doc})
        return jsonify({"message": "Invoice updated successfully"})
        
    except ValidationError as e:
        return jsonify({"error": "Validation Failed", "details": e.errors()}), 400

@app.route('/api/invoices/<id>', methods=['DELETE'])
def delete_invoice(id):
    collection = get_collection()
    
    try:
        existing = collection.find_one({"_id": ObjectId(id)})
    except Exception:
        return jsonify({"error": "Invalid Invoice ID"}), 400

    if not existing:
        return jsonify({"error": "Invoice not found"}), 404
    
    if existing.get("status") == InvoiceStatus.SUCCESS.value:
        return jsonify({"error": "Forbidden: Cannot delete a cleared invoice."}), 403
        
    collection.delete_one({"_id": ObjectId(id)})
    return jsonify({"message": "Invoice deleted successfully"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)