"""
MongoDB client access for LegalDocTracker.

Uses PyMongo and reads connection settings from Django settings.
The MongoClient is created lazily on first use and cached with
``functools.lru_cache``; connection pooling is handled by PyMongo itself.
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

    MongoClient is thread-safe and maintains its own connection pool, so a
    single cached instance is shared across requests.

    Returns:
        A MongoClient instance (connects lazily).
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
