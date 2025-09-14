"""Tests for GitHub client module."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from github_elasticsearch_sync.client import GitHubClient
from github_elasticsearch_sync.config import GitHubConfig


class TestGitHubClient:
    """Test GitHub client functionality."""
    
    @pytest.fixture
    def github_config(self):
        """Create test GitHub configuration."""
        config = GitHubConfig()
        config.token = "test_token"
        return config
    
    @pytest.fixture
    def github_client(self, github_config):
        """Create test GitHub client."""
        return GitHubClient(github_config)
    
    def test_init(self, github_client, github_config):
        """Test client initialization."""
        assert github_client.config == github_config
        assert github_client._client is None
    
    def test_parse_repo_name_valid(self, github_client):
        """Test parsing valid repository name."""
        owner, repo = github_client._parse_repo_name("owner/repo")
        assert owner == "owner"
        assert repo == "repo"
    
    def test_parse_repo_name_invalid(self, github_client):
        """Test parsing invalid repository name."""
        with pytest.raises(ValueError, match="Repository must be in format 'owner/repo'"):
            github_client._parse_repo_name("invalid_repo_name")
    
    @pytest.mark.asyncio
    async def test_connect_not_connected_error(self, github_client):
        """Test operations when client is not connected."""
        with pytest.raises(RuntimeError, match="GitHub client not connected"):
            await github_client.get_repository_info("owner/repo")
    
    @pytest.mark.asyncio
    @patch('github_elasticsearch_sync.client.GitHub')
    async def test_connect_success(self, mock_github_class, github_client):
        """Test successful connection."""
        # Mock the GitHub client
        mock_github_instance = AsyncMock()
        mock_github_class.return_value = mock_github_instance
        
        # Mock the authentication test
        mock_github_instance.rest.users.async_get_authenticated.return_value = AsyncMock()
        
        # Test connection
        await github_client.connect()
        
        assert github_client._client is not None
        mock_github_instance.rest.users.async_get_authenticated.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close(self, github_client):
        """Test closing client connection."""
        # Set up a mock client
        mock_client = AsyncMock()
        github_client._client = mock_client
        
        await github_client.close()
        
        mock_client.aclose.assert_called_once()
        assert github_client._client is None
    
    @pytest.mark.asyncio
    @patch('github_elasticsearch_sync.client.GitHub')
    async def test_get_repository_info(self, mock_github_class, github_client):
        """Test getting repository information."""
        # Mock the GitHub client
        mock_github_instance = AsyncMock()
        mock_github_class.return_value = mock_github_instance
        github_client._client = mock_github_instance
        
        # Mock repository data
        mock_repo_data = AsyncMock()
        mock_repo_data.id = 123456
        mock_repo_data.name = "test-repo"
        mock_repo_data.full_name = "owner/test-repo"
        mock_repo_data.description = "Test repository"
        mock_repo_data.html_url = "https://github.com/owner/test-repo"
        mock_repo_data.created_at = datetime.now(timezone.utc)
        mock_repo_data.updated_at = datetime.now(timezone.utc)
        mock_repo_data.language = "Python"
        mock_repo_data.stargazers_count = 100
        mock_repo_data.forks_count = 50
        mock_repo_data.open_issues_count = 10
        mock_repo_data.topics = ["python", "github"]
        mock_repo_data.visibility = "public"
        mock_repo_data.default_branch = "main"
        
        mock_response = AsyncMock()
        mock_response.parsed_data = mock_repo_data
        mock_github_instance.rest.repos.async_get.return_value = mock_response
        
        # Test getting repository info
        repo_info = await github_client.get_repository_info("owner/test-repo")
        
        assert repo_info["id"] == 123456
        assert repo_info["name"] == "test-repo"
        assert repo_info["full_name"] == "owner/test-repo"
        assert repo_info["description"] == "Test repository"
        assert repo_info["language"] == "Python"
        assert repo_info["stargazers_count"] == 100
        
        mock_github_instance.rest.repos.async_get.assert_called_once_with(
            owner="owner", repo="test-repo"
        )