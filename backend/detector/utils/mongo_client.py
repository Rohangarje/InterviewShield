try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, PyMongoError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    print("⚠️  pymongo not installed. Install with: pip install pymongo")

from django.conf import settings
import os

# MongoDB connection config (add to settings.py or env)
MONGO_URI = getattr(settings, 'MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME = 'interviewshield'
COLLECTION_NAME = 'detection_logs'

client = None
db = None
collection = None

def get_mongo_client():
    """Get or create MongoDB client"""
    if not PYMONGO_AVAILABLE:
        print("⚠️  MongoDB disabled - pymongo not installed")
        return None
    
    global client
    if client is None:
        try:
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            # Test connection
            client.admin.command('ismaster')
            print("✅ MongoDB connected")
        except ConnectionFailure:
            print("❌ MongoDB connection failed - is mongod running?")
            return None
    return client

def get_database():
    """Get interviewshield database"""
    global db
    if db is None:
        mongo_client = get_mongo_client()
        if mongo_client is not None:
            db = mongo_client[DB_NAME]
    return db

def get_collection():
    """Get detection_logs collection (auto-creates)"""
    global collection
    if collection is None:
        mongo_db = get_database()
        if mongo_db is not None:
            collection = mongo_db[COLLECTION_NAME]
    return collection

def insert_detection_log(data):
    """Insert single log document"""
    if not PYMONGO_AVAILABLE:
        print("⚠️  MongoDB insert skipped - pymongo not installed")
        return None
    
    coll = get_collection()
    if coll is not None:
        try:
            result = coll.insert_one(data)
            print(f"✅ Inserted log ID: {result.inserted_id}")
            return result.inserted_id
        except Exception as e:
            print(f"❌ Mongo insert error: {e}")
            return None
    return None

def fetch_recent_logs(limit=10):
    """Fetch recent logs for testing"""
    coll = get_collection()
    if coll is not None:
        return list(coll.find().sort("timestamp", -1).limit(limit))
    return []

def test_connection():
    """Test full stack"""
    print("Testing MongoDB...")
    coll = get_collection()
    if coll is not None:
        # Insert test doc
        test_doc = {"username": "test_user", "status": "normal", "timestamp": "2024-10-21T12:00:00Z"}
        result = insert_detection_log(test_doc)
        if result is not None:
            # Fetch back
            logs = fetch_recent_logs(5)
            print(f"✅ Test success! Found {len(logs)} logs")
            return True
        else:
            print("❌ Test insert failed")
    return False
