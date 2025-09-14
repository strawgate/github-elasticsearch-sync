"""GitHub Elasticsearch Sync Package

A Python tool for syncing GitHub repository information to Elasticsearch.
"""

__version__ = "0.1.0"
__author__ = "GitHub Elasticsearch Sync Contributors"

from .client import GitHubClient
from .elasticsearch_client import ElasticsearchClient
from .sync_engine import SyncEngine
from .config import Config

__all__ = [
    "GitHubClient",
    "ElasticsearchClient", 
    "SyncEngine",
    "Config",
]