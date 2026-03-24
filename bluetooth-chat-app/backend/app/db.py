import os
from pymongo import MongoClient


class Mongo:
    client: MongoClient | None = None
    db = None


mongo = Mongo()


def connect_db() -> None:
    uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB", "bluetooth_chat")
    if not uri:
        raise RuntimeError("MONGODB_URI is missing in backend/.env")

    mongo.client = MongoClient(uri)
    mongo.db = mongo.client[db_name]


def close_db() -> None:
    if mongo.client is not None:
        mongo.client.close()
        mongo.client = None
        mongo.db = None
