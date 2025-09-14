"""Elasticsearch client for indexing GitHub data."""

from typing import Dict, List, Optional, Any, AsyncGenerator
import asyncio
from datetime import datetime, timezone
import structlog
from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import ApiError, NotFoundError

from .config import ElasticsearchConfig

logger = structlog.get_logger()


class ElasticsearchClient:
    """Elasticsearch client for indexing GitHub data."""
    
    def __init__(self, config: ElasticsearchConfig):
        """Initialize Elasticsearch client with configuration."""
        self.config = config
        self._client: Optional[AsyncElasticsearch] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    async def connect(self) -> None:
        """Initialize Elasticsearch client connection."""
        try:
            client_config = {
                "hosts": self.config.hosts,
                "verify_certs": self.config.verify_certs,
            }
            
            # Add authentication
            if self.config.api_key:
                client_config["api_key"] = self.config.api_key
                logger.info("Using Elasticsearch API key authentication")
            elif self.config.username and self.config.password:
                client_config["basic_auth"] = (self.config.username, self.config.password)
                logger.info("Using Elasticsearch basic authentication")
            
            # Add cloud configuration
            if self.config.cloud_id:
                client_config["cloud_id"] = self.config.cloud_id
                logger.info("Using Elasticsearch Cloud")
            
            # Add CA certificates
            if self.config.ca_certs:
                client_config["ca_certs"] = self.config.ca_certs
            
            self._client = AsyncElasticsearch(**client_config)
            
            # Test the connection
            health = await self._client.cluster.health()
            logger.info("Elasticsearch client connected", status=health["status"])
            
        except ApiError as e:
            logger.error("Failed to connect to Elasticsearch", error=str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error connecting to Elasticsearch", error=str(e))
            raise
            
    async def close(self) -> None:
        """Close the Elasticsearch client connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Elasticsearch client connection closed")
    
    def _get_index_name(self, repo: str, data_type: str, prefix: str = "github") -> str:
        """Generate index name for a repository and data type."""
        # Replace slashes and special characters with underscores
        repo_safe = repo.replace("/", "_").replace("-", "_").lower()
        return f"{prefix}_{repo_safe}_{data_type}"
    
    async def create_index_if_not_exists(
        self, 
        index_name: str, 
        mapping: Dict[str, Any]
    ) -> None:
        """Create an index with mapping if it doesn't exist."""
        if not self._client:
            raise RuntimeError("Elasticsearch client not connected")
        
        try:
            exists = await self._client.indices.exists(index=index_name)
            if not exists:
                await self._client.indices.create(
                    index=index_name,
                    body={
                        "mappings": mapping,
                        "settings": {
                            "number_of_shards": 1,
                            "number_of_replicas": 0,
                        }
                    }
                )
                logger.info("Created index", index=index_name)
            else:
                logger.debug("Index already exists", index=index_name)
                
        except ApiError as e:
            logger.error("Failed to create index", index=index_name, error=str(e))
            raise
    
    async def setup_indices(self, repo: str, prefix: str = "github") -> None:
        """Set up all necessary indices for a repository."""
        indices = {
            "issues": self._get_issue_mapping(),
            "pull_requests": self._get_pull_request_mapping(),
            "comments": self._get_comment_mapping(),
            "repository": self._get_repository_mapping(),
        }
        
        for data_type, mapping in indices.items():
            index_name = self._get_index_name(repo, data_type, prefix)
            await self.create_index_if_not_exists(index_name, mapping)
    
    def _get_repository_mapping(self) -> Dict[str, Any]:
        """Get mapping for repository documents."""
        return {
            "properties": {
                "id": {"type": "long"},
                "name": {"type": "keyword"},
                "full_name": {"type": "keyword"},
                "description": {"type": "text"},
                "html_url": {"type": "keyword"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "language": {"type": "keyword"},
                "stargazers_count": {"type": "integer"},
                "forks_count": {"type": "integer"},
                "open_issues_count": {"type": "integer"},
                "topics": {"type": "keyword"},
                "visibility": {"type": "keyword"},
                "default_branch": {"type": "keyword"},
                "synced_at": {"type": "date"},
            }
        }
    
    def _get_issue_mapping(self) -> Dict[str, Any]:
        """Get mapping for issue documents."""
        return {
            "properties": {
                "id": {"type": "long"},
                "number": {"type": "integer"},
                "title": {"type": "text", "analyzer": "standard"},
                "body": {"type": "text", "analyzer": "standard"},
                "state": {"type": "keyword"},
                "user": {
                    "properties": {
                        "id": {"type": "long"},
                        "login": {"type": "keyword"},
                        "type": {"type": "keyword"},
                    }
                },
                "assignees": {
                    "properties": {
                        "id": {"type": "long"},
                        "login": {"type": "keyword"},
                    }
                },
                "labels": {
                    "properties": {
                        "id": {"type": "long"},
                        "name": {"type": "keyword"},
                        "color": {"type": "keyword"},
                    }
                },
                "milestone": {
                    "properties": {
                        "id": {"type": "long"},
                        "title": {"type": "text"},
                        "state": {"type": "keyword"},
                    }
                },
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "closed_at": {"type": "date"},
                "html_url": {"type": "keyword"},
                "comments": {"type": "integer"},
                "repository": {"type": "keyword"},
                "synced_at": {"type": "date"},
            }
        }
    
    def _get_pull_request_mapping(self) -> Dict[str, Any]:
        """Get mapping for pull request documents."""
        return {
            "properties": {
                "id": {"type": "long"},
                "number": {"type": "integer"},
                "title": {"type": "text", "analyzer": "standard"},
                "body": {"type": "text", "analyzer": "standard"},
                "state": {"type": "keyword"},
                "user": {
                    "properties": {
                        "id": {"type": "long"},
                        "login": {"type": "keyword"},
                        "type": {"type": "keyword"},
                    }
                },
                "assignees": {
                    "properties": {
                        "id": {"type": "long"},
                        "login": {"type": "keyword"},
                    }
                },
                "labels": {
                    "properties": {
                        "id": {"type": "long"},
                        "name": {"type": "keyword"},
                        "color": {"type": "keyword"},
                    }
                },
                "milestone": {
                    "properties": {
                        "id": {"type": "long"},
                        "title": {"type": "text"},
                        "state": {"type": "keyword"},
                    }
                },
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "closed_at": {"type": "date"},
                "merged_at": {"type": "date"},
                "html_url": {"type": "keyword"},
                "head": {
                    "properties": {
                        "ref": {"type": "keyword"},
                        "sha": {"type": "keyword"},
                    }
                },
                "base": {
                    "properties": {
                        "ref": {"type": "keyword"},
                        "sha": {"type": "keyword"},
                    }
                },
                "merged": {"type": "boolean"},
                "mergeable": {"type": "boolean"},
                "comments": {"type": "integer"},
                "review_comments": {"type": "integer"},
                "commits": {"type": "integer"},
                "additions": {"type": "integer"},
                "deletions": {"type": "integer"},
                "changed_files": {"type": "integer"},
                "repository": {"type": "keyword"},
                "synced_at": {"type": "date"},
            }
        }
    
    def _get_comment_mapping(self) -> Dict[str, Any]:
        """Get mapping for comment documents."""
        return {
            "properties": {
                "id": {"type": "long"},
                "body": {"type": "text", "analyzer": "standard"},
                "user": {
                    "properties": {
                        "id": {"type": "long"},
                        "login": {"type": "keyword"},
                        "type": {"type": "keyword"},
                    }
                },
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "html_url": {"type": "keyword"},
                "issue_number": {"type": "integer"},
                "pull_request_number": {"type": "integer"},
                "repository": {"type": "keyword"},
                "comment_type": {"type": "keyword"},
                # Review comment specific fields
                "path": {"type": "keyword"},
                "position": {"type": "integer"},
                "original_position": {"type": "integer"},
                "commit_id": {"type": "keyword"},
                "original_commit_id": {"type": "keyword"},
                "diff_hunk": {"type": "text"},
                "in_reply_to_id": {"type": "long"},
                "synced_at": {"type": "date"},
            }
        }
    
    async def index_document(
        self,
        index_name: str,
        doc_id: str,
        document: Dict[str, Any]
    ) -> None:
        """Index a single document."""
        if not self._client:
            raise RuntimeError("Elasticsearch client not connected")
        
        try:
            # Add sync timestamp
            document["synced_at"] = datetime.now(timezone.utc).isoformat()
            
            await self._client.index(
                index=index_name,
                id=doc_id,
                body=document
            )
            logger.debug("Indexed document", index=index_name, id=doc_id)
            
        except ApiError as e:
            logger.error(
                "Failed to index document",
                index=index_name,
                id=doc_id,
                error=str(e)
            )
            raise
    
    async def bulk_index(
        self,
        operations: List[Dict[str, Any]],
        chunk_size: int = 100
    ) -> None:
        """Bulk index documents."""
        if not self._client:
            raise RuntimeError("Elasticsearch client not connected")
        
        if not operations:
            return
        
        try:
            # Process in chunks
            for i in range(0, len(operations), chunk_size):
                chunk = operations[i:i + chunk_size]
                response = await self._client.bulk(body=chunk)
                
                # Check for errors
                if response.get("errors"):
                    errors = []
                    for item in response["items"]:
                        for action, result in item.items():
                            if "error" in result:
                                errors.append(f"{action}: {result['error']}")
                    
                    if errors:
                        logger.error("Bulk indexing errors", errors=errors)
                        raise ApiError(f"Bulk indexing failed: {errors}")
                
                logger.debug("Bulk indexed chunk", count=len(chunk))
            
            logger.info("Bulk indexing completed", total_operations=len(operations))
            
        except ApiError as e:
            logger.error("Bulk indexing failed", error=str(e))
            raise
    
    async def get_last_synced_timestamp(
        self,
        repo: str,
        data_type: str,
        prefix: str = "github"
    ) -> Optional[datetime]:
        """Get the timestamp of the last synced item for a repository and data type."""
        if not self._client:
            raise RuntimeError("Elasticsearch client not connected")
        
        index_name = self._get_index_name(repo, data_type, prefix)
        
        try:
            # Check if index exists
            exists = await self._client.indices.exists(index=index_name)
            if not exists:
                return None
            
            # Query for the most recent document
            query = {
                "query": {"match_all": {}},
                "sort": [{"updated_at": {"order": "desc"}}],
                "size": 1,
                "_source": ["updated_at"]
            }
            
            response = await self._client.search(index=index_name, body=query)
            hits = response["hits"]["hits"]
            
            if hits:
                updated_at = hits[0]["_source"]["updated_at"]
                return datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            
            return None
            
        except NotFoundError:
            return None
        except ApiError as e:
            logger.error(
                "Failed to get last synced timestamp",
                index=index_name,
                error=str(e)
            )
            return None
    
    async def search(
        self,
        index_name: str,
        query: Dict[str, Any],
        size: int = 10,
        from_: int = 0
    ) -> Dict[str, Any]:
        """Search documents in an index."""
        if not self._client:
            raise RuntimeError("Elasticsearch client not connected")
        
        try:
            response = await self._client.search(
                index=index_name,
                body=query,
                size=size,
                from_=from_
            )
            return response
            
        except ApiError as e:
            logger.error("Search failed", index=index_name, error=str(e))
            raise
    
    async def delete_index(self, index_name: str) -> None:
        """Delete an index."""
        if not self._client:
            raise RuntimeError("Elasticsearch client not connected")
        
        try:
            exists = await self._client.indices.exists(index=index_name)
            if exists:
                await self._client.indices.delete(index=index_name)
                logger.info("Deleted index", index=index_name)
            else:
                logger.debug("Index does not exist", index=index_name)
                
        except ApiError as e:
            logger.error("Failed to delete index", index=index_name, error=str(e))
            raise