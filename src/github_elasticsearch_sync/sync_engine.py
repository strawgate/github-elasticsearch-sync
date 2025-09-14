"""Sync engine for orchestrating GitHub to Elasticsearch synchronization."""

from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime, timezone
import structlog
from concurrent.futures import ThreadPoolExecutor

from .client import GitHubClient
from .elasticsearch_client import ElasticsearchClient
from .config import Config

logger = structlog.get_logger()


class SyncEngine:
    """Main synchronization engine for GitHub to Elasticsearch."""
    
    def __init__(self, config: Config):
        """Initialize sync engine with configuration."""
        self.config = config
        self.github_client = GitHubClient(config.github)
        self.elasticsearch_client = ElasticsearchClient(config.elasticsearch)
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.github_client.connect()
        await self.elasticsearch_client.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.github_client.close()
        await self.elasticsearch_client.close()
    
    async def sync_repository(self, repo: str, full_sync: bool = False) -> Dict[str, Any]:
        """Sync a single repository to Elasticsearch."""
        logger.info("Starting repository sync", repository=repo, full_sync=full_sync)
        
        start_time = datetime.now(timezone.utc)
        stats = {
            "repository": repo,
            "start_time": start_time.isoformat(),
            "full_sync": full_sync,
            "issues_synced": 0,
            "pull_requests_synced": 0,
            "comments_synced": 0,
            "errors": [],
        }
        
        try:
            # Set up indices for this repository
            await self.elasticsearch_client.setup_indices(
                repo, self.config.sync.index_prefix
            )
            
            # Sync repository metadata
            await self._sync_repository_metadata(repo)
            
            # Determine sync timestamps for partial sync
            since_timestamps = {}
            if not full_sync and self.config.sync.partial_sync:
                since_timestamps = await self._get_since_timestamps(repo)
            
            # Sync data in parallel
            tasks = []
            
            if self.config.sync.sync_issues:
                tasks.append(self._sync_issues(repo, since_timestamps.get("issues")))
            
            if self.config.sync.sync_pull_requests:
                tasks.append(self._sync_pull_requests(repo, since_timestamps.get("pull_requests")))
            
            # Run sync tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    error_msg = f"Task {i} failed: {str(result)}"
                    stats["errors"].append(error_msg)
                    logger.error("Sync task failed", task=i, error=str(result))
                else:
                    if i == 0 and self.config.sync.sync_issues:
                        stats["issues_synced"] = result.get("count", 0)
                    elif (i == 1 and self.config.sync.sync_pull_requests) or (i == 0 and not self.config.sync.sync_issues):
                        stats["pull_requests_synced"] = result.get("count", 0)
            
            # Sync comments if enabled
            if self.config.sync.sync_comments:
                comments_result = await self._sync_comments(repo, since_timestamps.get("comments"))
                if isinstance(comments_result, Exception):
                    stats["errors"].append(f"Comments sync failed: {str(comments_result)}")
                else:
                    stats["comments_synced"] = comments_result.get("count", 0)
            
            end_time = datetime.now(timezone.utc)
            stats["end_time"] = end_time.isoformat()
            stats["duration_seconds"] = (end_time - start_time).total_seconds()
            
            logger.info(
                "Repository sync completed",
                repository=repo,
                stats=stats
            )
            
            return stats
            
        except Exception as e:
            error_msg = f"Repository sync failed: {str(e)}"
            stats["errors"].append(error_msg)
            logger.error("Repository sync failed", repository=repo, error=str(e))
            return stats
    
    async def sync_all_repositories(self, full_sync: bool = False) -> List[Dict[str, Any]]:
        """Sync all configured repositories."""
        logger.info(
            "Starting sync of all repositories",
            repositories=self.config.sync.repositories,
            full_sync=full_sync
        )
        
        # Validate repositories
        if not self.config.sync.repositories:
            raise ValueError("No repositories configured for sync")
        
        # Create semaphore to limit concurrent repository syncs
        semaphore = asyncio.Semaphore(self.config.sync.max_concurrent_requests)
        
        async def sync_repo_with_semaphore(repo: str):
            async with semaphore:
                return await self.sync_repository(repo, full_sync)
        
        # Sync repositories concurrently
        tasks = [
            sync_repo_with_semaphore(repo)
            for repo in self.config.sync.repositories
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        sync_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                repo = self.config.sync.repositories[i]
                sync_results.append({
                    "repository": repo,
                    "error": str(result),
                    "success": False
                })
                logger.error("Repository sync failed", repository=repo, error=str(result))
            else:
                result["success"] = len(result.get("errors", [])) == 0
                sync_results.append(result)
        
        logger.info("All repositories sync completed", results=sync_results)
        return sync_results
    
    async def _sync_repository_metadata(self, repo: str) -> None:
        """Sync repository metadata."""
        try:
            repo_info = await self.github_client.get_repository_info(repo)
            
            index_name = self.elasticsearch_client._get_index_name(
                repo, "repository", self.config.sync.index_prefix
            )
            
            await self.elasticsearch_client.index_document(
                index_name,
                str(repo_info["id"]),
                repo_info
            )
            
            logger.debug("Synced repository metadata", repository=repo)
            
        except Exception as e:
            logger.error("Failed to sync repository metadata", repository=repo, error=str(e))
            raise
    
    async def _get_since_timestamps(self, repo: str) -> Dict[str, datetime]:
        """Get last sync timestamps for partial sync."""
        timestamps = {}
        data_types = ["issues", "pull_requests", "comments"]
        
        for data_type in data_types:
            try:
                timestamp = await self.elasticsearch_client.get_last_synced_timestamp(
                    repo, data_type, self.config.sync.index_prefix
                )
                if timestamp:
                    timestamps[data_type] = timestamp
                    logger.debug(
                        "Found last sync timestamp",
                        repository=repo,
                        data_type=data_type,
                        timestamp=timestamp.isoformat()
                    )
            except Exception as e:
                logger.warning(
                    "Failed to get last sync timestamp",
                    repository=repo,
                    data_type=data_type,
                    error=str(e)
                )
        
        return timestamps
    
    async def _sync_issues(self, repo: str, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Sync issues for a repository."""
        logger.info("Syncing issues", repository=repo, since=since.isoformat() if since else None)
        
        index_name = self.elasticsearch_client._get_index_name(
            repo, "issues", self.config.sync.index_prefix
        )
        
        operations = []
        count = 0
        
        try:
            async for issue in self.github_client.get_issues(
                repo, since=since, per_page=self.config.sync.batch_size
            ):
                # Create bulk operation
                operations.extend([
                    {"index": {"_index": index_name, "_id": str(issue["id"])}},
                    issue
                ])
                count += 1
                
                # Bulk index when we have enough operations
                if len(operations) >= self.config.sync.batch_size * 2:
                    await self.elasticsearch_client.bulk_index(operations)
                    operations = []
                    logger.debug("Bulk indexed issues batch", repository=repo, count=count)
            
            # Index remaining operations
            if operations:
                await self.elasticsearch_client.bulk_index(operations)
            
            logger.info("Issues sync completed", repository=repo, count=count)
            return {"count": count}
            
        except Exception as e:
            logger.error("Issues sync failed", repository=repo, error=str(e))
            raise
    
    async def _sync_pull_requests(self, repo: str, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Sync pull requests for a repository."""
        logger.info("Syncing pull requests", repository=repo, since=since.isoformat() if since else None)
        
        index_name = self.elasticsearch_client._get_index_name(
            repo, "pull_requests", self.config.sync.index_prefix
        )
        
        operations = []
        count = 0
        
        try:
            async for pr in self.github_client.get_pull_requests(
                repo, since=since, per_page=self.config.sync.batch_size
            ):
                # Create bulk operation
                operations.extend([
                    {"index": {"_index": index_name, "_id": str(pr["id"])}},
                    pr
                ])
                count += 1
                
                # Bulk index when we have enough operations
                if len(operations) >= self.config.sync.batch_size * 2:
                    await self.elasticsearch_client.bulk_index(operations)
                    operations = []
                    logger.debug("Bulk indexed pull requests batch", repository=repo, count=count)
            
            # Index remaining operations
            if operations:
                await self.elasticsearch_client.bulk_index(operations)
            
            logger.info("Pull requests sync completed", repository=repo, count=count)
            return {"count": count}
            
        except Exception as e:
            logger.error("Pull requests sync failed", repository=repo, error=str(e))
            raise
    
    async def _sync_comments(self, repo: str, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Sync comments for a repository."""
        logger.info("Syncing comments", repository=repo, since=since.isoformat() if since else None)
        
        index_name = self.elasticsearch_client._get_index_name(
            repo, "comments", self.config.sync.index_prefix
        )
        
        operations = []
        count = 0
        
        try:
            # Get issues and pull requests to sync their comments
            issue_numbers = []
            pr_numbers = []
            
            # Collect issue numbers
            if self.config.sync.sync_issues:
                async for issue in self.github_client.get_issues(repo, since=since):
                    issue_numbers.append(issue["number"])
            
            # Collect PR numbers
            if self.config.sync.sync_pull_requests:
                async for pr in self.github_client.get_pull_requests(repo, since=since):
                    pr_numbers.append(pr["number"])
            
            # Sync issue comments
            for issue_number in issue_numbers:
                async for comment in self.github_client.get_issue_comments(
                    repo, issue_number, since=since, per_page=self.config.sync.batch_size
                ):
                    operations.extend([
                        {"index": {"_index": index_name, "_id": str(comment["id"])}},
                        comment
                    ])
                    count += 1
                    
                    # Bulk index when we have enough operations
                    if len(operations) >= self.config.sync.batch_size * 2:
                        await self.elasticsearch_client.bulk_index(operations)
                        operations = []
                        logger.debug("Bulk indexed comments batch", repository=repo, count=count)
            
            # Sync PR comments
            for pr_number in pr_numbers:
                async for comment in self.github_client.get_pull_request_comments(
                    repo, pr_number, since=since, per_page=self.config.sync.batch_size
                ):
                    operations.extend([
                        {"index": {"_index": index_name, "_id": str(comment["id"])}},
                        comment
                    ])
                    count += 1
                    
                    # Bulk index when we have enough operations
                    if len(operations) >= self.config.sync.batch_size * 2:
                        await self.elasticsearch_client.bulk_index(operations)
                        operations = []
                        logger.debug("Bulk indexed comments batch", repository=repo, count=count)
            
            # Index remaining operations
            if operations:
                await self.elasticsearch_client.bulk_index(operations)
            
            logger.info("Comments sync completed", repository=repo, count=count)
            return {"count": count}
            
        except Exception as e:
            logger.error("Comments sync failed", repository=repo, error=str(e))
            raise