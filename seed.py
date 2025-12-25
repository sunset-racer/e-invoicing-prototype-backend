import json
from datetime import datetime, timezone, timedelta
from db.mongo import MongoDB
from schemas import InvoiceSchema, InvoiceStatus, Currency

def seed_database():
    print("Starting database seeding...")

    # 1. Connect to DB
    try:
        MongoDB.connect()
        db = MongoDB.get_db()
        collection = db['invoices'] # type: ignore
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return

    # 2. Clear existing data
    collection.delete_many({})
    print("🧹 Cleared existing invoices.")

    # 3. Define Raw Data with STAGGERED TIMES
    # We use explicit times to ensure the Dashboard sorts them correctly (Newest First)
    now = datetime.now(timezone.utc)
    
    raw_invoices = [

        # Scenario 1: RECEIVED (Draft State) - Created Just Now
        {
            "sender_id": "US-TAX-101",
            "receiver_id": "EU-VAT-202",
            "currency": Currency.USD,
            "status": InvoiceStatus.RECEIVED,
            "created_at": now,  # Top of the list
            "items": [
                {"description": "Web Hosting - Q1", "quantity": 1, "unit_price": "150.00"},
                {"description": "Domain Renewal", "quantity": 2, "unit_price": "15.00"}
            ]
        },
        
        # Scenario 2: SUCCESS (Final State) - Created 2 Days Ago
        {
            "sender_id": "GB-VAT-303",
            "receiver_id": "EU-VAT-404",
            "currency": Currency.GBP,
            "status": InvoiceStatus.SUCCESS,
            "tax_rate": "0.20", 
            "created_at": now - timedelta(days=2), # Middle of list
            "items": [
                {"description": "Consulting Services", "quantity": 10, "unit_price": "200.00"},
                {"description": "Travel Expenses", "quantity": 1, "unit_price": "500.00"}
            ]
        },
        
        # Scenario 3: FAILED (Error State) - Created 5 Days Ago
        {
            "sender_id": "US-TAX-500",
            "receiver_id": "EU-VAT-FAIL", 
            "currency": Currency.EUR,
            "status": InvoiceStatus.FAILED,
            "created_at": now - timedelta(days=5), # Bottom of list
            "items": [
                {"description": "Software License (Invalid)", "quantity": 5, "unit_price": "99.99"}
            ]
        }
    ]

    # 4. Process & Insert
    count = 0
    for raw in raw_invoices:
        try:
            # A. Pass through Schema (Calculates Subtotal, Tax, Total)
            invoice_obj = InvoiceSchema(**raw)
            
            # B. Serialization Step (Crucial for Robustness)
            # 1. Dump to JSON string then load back (Converts Decimal -> String, Datetime -> String)
            doc = json.loads(invoice_obj.model_dump_json())
            
            # 2. FIX: Convert the date string BACK to a real Python datetime object
            # This ensures MongoDB stores it as a BSON Date (sortable), not a simple string.
            if 'created_at' in doc and doc['created_at']:
                doc['created_at'] = datetime.fromisoformat(doc['created_at'].replace('Z', '+00:00'))

            # C. Insert
            collection.insert_one(doc)
            count += 1
            
            print(f"Inserted: {doc['sender_id']} -> {doc['receiver_id']} | Total: {doc['currency']} {doc['total_amount']}")
            
        except Exception as e:
            print(f"Error seeding invoice: {e}")

    print(f"\nSuccessfully seeded {count} invoices into MongoDB Atlas!")
    MongoDB.close()

if __name__ == "__main__":
    seed_database()