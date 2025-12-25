from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.database import Database
from dotenv import load_dotenv
import os
import certifi

load_dotenv()

class MongoDB:
    _client: MongoClient | None = None
    _db: Database | None = None

    @classmethod
    def connect(cls) -> None:
        if cls._client is not None:
            return
        
        mongo_uri = os.environ.get("MONGO_URI")
        db_name = os.environ.get("MONGO_DB_NAME", "einvoicing_db")

        if not mongo_uri:
            raise RuntimeError("MONGO_URI is not set")
        
        # Initialize Client with SSL Fix
        cls._client = MongoClient(
            mongo_uri,
            server_api=ServerApi('1'),
            tlsCAFile=certifi.where()
        )

        try:
            # Verify connection
            cls._client.admin.command("ping")
            print("MongoDB Connected Successfully via Singleton!")
        except Exception as e:
            print(f"Connection Failed: {e}")
            raise e

        cls._db = cls._client[db_name]
    
    @classmethod
    def get_db(cls):
        if cls._db is None:
            # Auto-connect if accessed before explicit connect (Lazy Loading)
            try:
                cls.connect()
            except Exception:
                raise RuntimeError("MongoDB not initialized. Call connect() first.")
        
        return cls._db  # <--- FIXED: Added return statement
    
    @classmethod
    def close(cls) -> None:
        if cls._client:
            cls._client.close()
            cls._client = None
            cls._db = None

# --- TEST BLOCK ---
if __name__ == "__main__":
    try:
        MongoDB.connect()
        db = MongoDB.get_db()
        print(f"Accessing Database: {db.name}") # type: ignore
    except Exception as e:
        print(e)