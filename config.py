import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "default-dev-secret-key-change-in-production")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
    DB_NAME = os.getenv("DB_NAME", "TeamFinder")
    FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

_client = None
_db = None

def get_mongo_client():
    global _client
    if _client is None:
        try:
            _client = MongoClient(
                Config.MONGO_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
            )
            # Verify connection
            _client.admin.command('ping')
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"[ERROR] Failed to connect to MongoDB at {Config.MONGO_URI}: {e}")
            raise e
    return _client

def get_db():
    global _db
    if _db is None:
        client = get_mongo_client()
        _db = client[Config.DB_NAME]
    return _db

# Convenience accessors for collections
def get_collections():
    db = get_db()
    return {
        "users": db["users"],
        "student_profiles": db["student_profiles"],
        "projects": db["projects"],
        "join_requests": db["join_requests"],
        "team_members": db["team_members"]
    }
