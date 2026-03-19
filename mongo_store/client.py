"""
MongoDB client singleton for LegalDocTracker.

Uses PyMongo and reads connection settings from Django settings.
The client is initialised once at module import time.
"""
import logging
from functools import lru_cache

import pymongo
from django.conf import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_mongo_client() -> pymongo.MongoClient:
    """
    Return a cached PyMongo MongoClient.

    The client is thread-safe and reused across requests.

    Returns:
        A connected MongoClient instance.
    """
    uri = getattr(settings, "MONGO_URI", "mongodb://localhost:27017")
    client: pymongo.MongoClient = pymongo.MongoClient(
        uri,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )
    logger.info("MongoDB client initialised: %s", uri)
    return client


def get_db() -> pymongo.database.Database:
    """
    Return the application MongoDB database.

    Returns:
        A PyMongo Database object.
    """
    db_name = getattr(settings, "MONGO_DB_NAME", "legaldoctracker")
    return get_mongo_client()[db_name]
