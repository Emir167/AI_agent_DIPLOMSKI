# db.py
from pymongo import MongoClient
from config import Config

_client = MongoClient(Config.MONGODB_URI)
db = _client[Config.MONGO_DB_NAME]

def ping():
    # vrati "ok":1 ako je konekcija u redu
    return _client.admin.command("ping")
