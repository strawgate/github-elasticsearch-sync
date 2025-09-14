"""GitHub client for fetching repository data."""

from typing import Dict, List, Optional, AsyncGenerator, Any
import asyncio
from datetime import datetime, timezone
import structlog
from githubkit import GitHub
from githubkit.auth import TokenAuthStrategy, AppAuthStrategy
from githubkit.exception import GitHubException, AuthCredentialError

from .config import GitHubConfig

logger = structlog.get_logger()


class GitHubClient:
    """GitHub API client for fetching repository data."""
    
    def __init__(self, config: GitHubConfig):
        """Initialize GitHub client with configuration."""
        self.config = config
        self._client: Optional[GitHub] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    async def connect(self) -> None:
        """Initialize GitHub client connection."""
        try:
            if self.config.token:
                auth = TokenAuthStrategy(self.config.token)
                logger.info("Using GitHub token authentication")
            elif (
                self.config.app_id and 
                self.config.private_key and 
                self.config.installation_id
            ):
                auth = AppAuthStrategy(
                    app_id=self.config.app_id,
                    private_key=self.config.private_key,
                    installation_id=int(self.config.installation_id),
                )
                logger.info("Using GitHub App authentication")
            else:
                raise ValueError("No valid GitHub authentication configured")
                
            self._client = GitHub(auth=auth, base_url=self.config.base_url)
            
            # Test the connection
            await self._client.rest.users.async_get_authenticated()
            logger.info("GitHub client connected successfully")
            
        except AuthCredentialError as e:
            logger.error("GitHub authentication failed", error=str(e))
            raise
        except GitHubException as e:
            logger.error("GitHub API error", error=str(e))
            raise
        except Exception as e:
            logger.error("Failed to connect to GitHub", error=str(e))
            raise
            
    async def close(self) -> None:
        """Close the GitHub client connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("GitHub client connection closed")
    
    def _parse_repo_name(self, repo: str) -> tuple[str, str]:
        """Parse repository name into owner and repo."""
        if "/" not in repo:
            raise ValueError(f"Repository must be in format 'owner/repo', got: {repo}")
        owner, name = repo.split("/", 1)
        return owner, name
    
    async def get_repository_info(self, repo: str) -> Dict[str, Any]:
        """Get repository information."""
        if not self._client:
            raise RuntimeError("GitHub client not connected")
            
        owner, name = self._parse_repo_name(repo)
        
        try:
            response = await self._client.rest.repos.async_get(owner=owner, repo=name)
            repo_data = response.parsed_data
            
            return {
                "id": repo_data.id,
                "name": repo_data.name,
                "full_name": repo_data.full_name,
                "description": repo_data.description,
                "html_url": repo_data.html_url,
                "created_at": repo_data.created_at.isoformat() if repo_data.created_at else None,
                "updated_at": repo_data.updated_at.isoformat() if repo_data.updated_at else None,
                "language": repo_data.language,
                "stargazers_count": repo_data.stargazers_count,
                "forks_count": repo_data.forks_count,
                "open_issues_count": repo_data.open_issues_count,
                "topics": repo_data.topics or [],
                "visibility": repo_data.visibility,
                "default_branch": repo_data.default_branch,
            }
        except GitHubException as e:
            logger.error("Failed to get repository info", repo=repo, error=str(e))
            raise
    
    async def get_issues(
        self,
        repo: str,
        since: Optional[datetime] = None,
        state: str = "all",
        per_page: int = 100,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get issues from a repository."""
        if not self._client:
            raise RuntimeError("GitHub client not connected")
            
        owner, name = self._parse_repo_name(repo)
        page = 1
        
        while True:
            try:
                params = {
                    "owner": owner,
                    "repo": name,
                    "state": state,
                    "per_page": per_page,
                    "page": page,
                    "sort": "updated",
                    "direction": "desc",
                }
                
                if since:
                    params["since"] = since.isoformat()
                
                response = await self._client.rest.issues.async_list_for_repo(**params)
                issues = response.parsed_data
                
                if not issues:
                    break
                
                for issue in issues:
                    # Skip pull requests (they appear in issues endpoint)
                    if issue.pull_request:
                        continue
                        
                    yield {
                        "id": issue.id,
                        "number": issue.number,
                        "title": issue.title,
                        "body": issue.body,
                        "state": issue.state,
                        "user": {
                            "id": issue.user.id if issue.user else None,
                            "login": issue.user.login if issue.user else None,
                            "type": issue.user.type if issue.user else None,
                        },
                        "assignees": [
                            {"id": assignee.id, "login": assignee.login}
                            for assignee in (issue.assignees or [])
                        ],
                        "labels": [
                            {"id": label.id, "name": label.name, "color": label.color}
                            for label in (issue.labels or [])
                        ],
                        "milestone": {
                            "id": issue.milestone.id,
                            "title": issue.milestone.title,
                            "state": issue.milestone.state,
                        } if issue.milestone else None,
                        "created_at": issue.created_at.isoformat() if issue.created_at else None,
                        "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
                        "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                        "html_url": issue.html_url,
                        "comments": issue.comments,
                        "repository": repo,
                    }
                
                page += 1
                
            except GitHubException as e:
                logger.error("Failed to get issues", repo=repo, page=page, error=str(e))
                raise
    
    async def get_pull_requests(
        self,
        repo: str,
        since: Optional[datetime] = None,
        state: str = "all",
        per_page: int = 100,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get pull requests from a repository."""
        if not self._client:
            raise RuntimeError("GitHub client not connected")
            
        owner, name = self._parse_repo_name(repo)
        page = 1
        
        while True:
            try:
                params = {
                    "owner": owner,
                    "repo": name,
                    "state": state,
                    "per_page": per_page,
                    "page": page,
                    "sort": "updated",
                    "direction": "desc",
                }
                
                response = await self._client.rest.pulls.async_list(**params)
                prs = response.parsed_data
                
                if not prs:
                    break
                
                for pr in prs:
                    # Filter by since date if provided
                    if since and pr.updated_at and pr.updated_at < since:
                        continue
                        
                    yield {
                        "id": pr.id,
                        "number": pr.number,
                        "title": pr.title,
                        "body": pr.body,
                        "state": pr.state,
                        "user": {
                            "id": pr.user.id if pr.user else None,
                            "login": pr.user.login if pr.user else None,
                            "type": pr.user.type if pr.user else None,
                        },
                        "assignees": [
                            {"id": assignee.id, "login": assignee.login}
                            for assignee in (pr.assignees or [])
                        ],
                        "labels": [
                            {"id": label.id, "name": label.name, "color": label.color}
                            for label in (pr.labels or [])
                        ],
                        "milestone": {
                            "id": pr.milestone.id,
                            "title": pr.milestone.title,
                            "state": pr.milestone.state,
                        } if pr.milestone else None,
                        "created_at": pr.created_at.isoformat() if pr.created_at else None,
                        "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
                        "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
                        "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                        "html_url": pr.html_url,
                        "head": {
                            "ref": pr.head.ref,
                            "sha": pr.head.sha,
                        },
                        "base": {
                            "ref": pr.base.ref,
                            "sha": pr.base.sha,
                        },
                        "merged": pr.merged,
                        "mergeable": pr.mergeable,
                        "comments": pr.comments,
                        "review_comments": pr.review_comments,
                        "commits": pr.commits,
                        "additions": pr.additions,
                        "deletions": pr.deletions,
                        "changed_files": pr.changed_files,
                        "repository": repo,
                    }
                
                page += 1
                
            except GitHubException as e:
                logger.error("Failed to get pull requests", repo=repo, page=page, error=str(e))
                raise
    
    async def get_issue_comments(
        self,
        repo: str,
        issue_number: int,
        since: Optional[datetime] = None,
        per_page: int = 100,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get comments for an issue."""
        if not self._client:
            raise RuntimeError("GitHub client not connected")
            
        owner, name = self._parse_repo_name(repo)
        page = 1
        
        while True:
            try:
                params = {
                    "owner": owner,
                    "repo": name,
                    "issue_number": issue_number,
                    "per_page": per_page,
                    "page": page,
                }
                
                if since:
                    params["since"] = since.isoformat()
                
                response = await self._client.rest.issues.async_list_comments(**params)
                comments = response.parsed_data
                
                if not comments:
                    break
                
                for comment in comments:
                    yield {
                        "id": comment.id,
                        "body": comment.body,
                        "user": {
                            "id": comment.user.id if comment.user else None,
                            "login": comment.user.login if comment.user else None,
                            "type": comment.user.type if comment.user else None,
                        },
                        "created_at": comment.created_at.isoformat() if comment.created_at else None,
                        "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
                        "html_url": comment.html_url,
                        "issue_number": issue_number,
                        "repository": repo,
                        "comment_type": "issue",
                    }
                
                page += 1
                
            except GitHubException as e:
                logger.error(
                    "Failed to get issue comments",
                    repo=repo,
                    issue_number=issue_number,
                    page=page,
                    error=str(e)
                )
                raise
    
    async def get_pull_request_comments(
        self,
        repo: str,
        pr_number: int,
        since: Optional[datetime] = None,
        per_page: int = 100,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Get comments for a pull request (issue comments and review comments)."""
        if not self._client:
            raise RuntimeError("GitHub client not connected")
            
        # Get issue comments (general comments on the PR)
        async for comment in self.get_issue_comments(repo, pr_number, since, per_page):
            comment["comment_type"] = "pull_request"
            yield comment
        
        # Get review comments (comments on code)
        owner, name = self._parse_repo_name(repo)
        page = 1
        
        while True:
            try:
                params = {
                    "owner": owner,
                    "repo": name,
                    "pull_number": pr_number,
                    "per_page": per_page,
                    "page": page,
                }
                
                if since:
                    params["since"] = since.isoformat()
                
                response = await self._client.rest.pulls.async_list_review_comments(**params)
                comments = response.parsed_data
                
                if not comments:
                    break
                
                for comment in comments:
                    yield {
                        "id": comment.id,
                        "body": comment.body,
                        "user": {
                            "id": comment.user.id if comment.user else None,
                            "login": comment.user.login if comment.user else None,
                            "type": comment.user.type if comment.user else None,
                        },
                        "created_at": comment.created_at.isoformat() if comment.created_at else None,
                        "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
                        "html_url": comment.html_url,
                        "pull_request_number": pr_number,
                        "repository": repo,
                        "comment_type": "review",
                        "path": comment.path,
                        "position": comment.position,
                        "original_position": comment.original_position,
                        "commit_id": comment.commit_id,
                        "original_commit_id": comment.original_commit_id,
                        "diff_hunk": comment.diff_hunk,
                        "in_reply_to_id": comment.in_reply_to_id,
                    }
                
                page += 1
                
            except GitHubException as e:
                logger.error(
                    "Failed to get pull request review comments",
                    repo=repo,
                    pr_number=pr_number,
                    page=page,
                    error=str(e)
                )
                raise