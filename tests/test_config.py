"""Tests for configuration module."""

import os
import pytest
from unittest.mock import patch

from github_elasticsearch_sync.config import Config, GitHubConfig, ElasticsearchConfig, SyncConfig


class TestGitHubConfig:
    """Test GitHub configuration."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = GitHubConfig()
        assert config.token is None
        assert config.app_id is None
        assert config.private_key is None
        assert config.installation_id is None
        assert config.base_url == "https://api.github.com"
    
    @patch.dict(os.environ, {
        "GITHUB_TOKEN": "test_token",
        "GITHUB_APP_ID": "123",
        "GITHUB_PRIVATE_KEY": "test_key",
        "GITHUB_INSTALLATION_ID": "456"
    })
    def test_from_environment(self):
        """Test loading from environment variables."""
        config = GitHubConfig()
        assert config.token == "test_token"
        assert config.app_id == "123"
        assert config.private_key == "test_key"
        assert config.installation_id == "456"


class TestElasticsearchConfig:
    """Test Elasticsearch configuration."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = ElasticsearchConfig()
        assert config.hosts == ["http://localhost:9200"]
        assert config.username is None
        assert config.password is None
        assert config.verify_certs is True
    
    @patch.dict(os.environ, {
        "ELASTICSEARCH_HOSTS": "http://es1:9200,http://es2:9200",
        "ELASTICSEARCH_USERNAME": "elastic",
        "ELASTICSEARCH_PASSWORD": "password123",
        "ELASTICSEARCH_VERIFY_CERTS": "false"
    })
    def test_from_environment(self):
        """Test loading from environment variables."""
        config = ElasticsearchConfig()
        assert config.hosts == ["http://es1:9200", "http://es2:9200"]
        assert config.username == "elastic"
        assert config.password == "password123"
        assert config.verify_certs is False


class TestSyncConfig:
    """Test sync configuration."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = SyncConfig()
        assert config.repositories == []
        assert config.sync_issues is True
        assert config.sync_pull_requests is True
        assert config.sync_comments is True
        assert config.batch_size == 100
        assert config.max_concurrent_requests == 10
        assert config.partial_sync is True
        assert config.index_prefix == "github"
    
    @patch.dict(os.environ, {
        "GITHUB_REPOSITORIES": "owner/repo1,owner/repo2",
        "SYNC_ISSUES": "false",
        "BATCH_SIZE": "50",
        "INDEX_PREFIX": "test"
    })
    def test_from_environment(self):
        """Test loading from environment variables."""
        config = SyncConfig()
        assert config.repositories == ["owner/repo1", "owner/repo2"]
        assert config.sync_issues is False
        assert config.batch_size == 50
        assert config.index_prefix == "test"


class TestConfig:
    """Test main configuration class."""
    
    def test_from_env(self):
        """Test creating config from environment."""
        config = Config.from_env()
        assert isinstance(config.github, GitHubConfig)
        assert isinstance(config.elasticsearch, ElasticsearchConfig)
        assert isinstance(config.sync, SyncConfig)
    
    def test_validate_missing_auth(self):
        """Test validation with missing authentication."""
        config = Config()
        with pytest.raises(ValueError, match="GitHub authentication required"):
            config.validate()
    
    def test_validate_missing_repositories(self):
        """Test validation with missing repositories."""
        config = Config()
        config.github.token = "test_token"
        with pytest.raises(ValueError, match="At least one repository must be specified"):
            config.validate()
    
    def test_validate_success(self):
        """Test successful validation."""
        config = Config()
        config.github.token = "test_token"
        config.sync.repositories = ["owner/repo"]
        # Should not raise
        config.validate()