"""Tests for CLI module."""

import pytest
from unittest.mock import patch, AsyncMock
from click.testing import CliRunner

from github_elasticsearch_sync.cli import cli


class TestCLI:
    """Test CLI functionality."""
    
    def test_cli_help(self):
        """Test CLI help command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "GitHub Elasticsearch Sync" in result.output
    
    def test_sync_help(self):
        """Test sync command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["sync", "--help"])
        assert result.exit_code == 0
        assert "Sync GitHub repositories to Elasticsearch" in result.output
    
    def test_status_help(self):
        """Test status command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0
        assert "Check sync status and index information" in result.output
    
    def test_clean_help(self):
        """Test clean command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["clean", "--help"])
        assert result.exit_code == 0
        assert "Clean (delete) all indices for a repository" in result.output
    
    @patch.dict('os.environ', {
        'GITHUB_TOKEN': 'test_token',
        'ELASTICSEARCH_HOSTS': 'http://localhost:9200'
    })
    def test_sync_no_repositories(self):
        """Test sync command with no repositories configured."""
        runner = CliRunner()
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 1
        assert "Configuration error" in result.output
    
    @patch.dict('os.environ', {
        'GITHUB_TOKEN': 'test_token',
        'ELASTICSEARCH_HOSTS': 'http://localhost:9200',
        'GITHUB_REPOSITORIES': 'owner/repo'
    })
    @patch('github_elasticsearch_sync.cli._run_sync')
    def test_sync_with_repositories(self, mock_run_sync):
        """Test sync command with repositories configured."""
        mock_run_sync.return_value = AsyncMock()
        runner = CliRunner()
        result = runner.invoke(cli, ["sync"])
        # Should attempt to run sync (will fail due to mocking, but config should be valid)
        mock_run_sync.assert_called_once()
    
    def test_sync_missing_github_auth(self):
        """Test sync command with missing GitHub authentication."""
        runner = CliRunner()
        result = runner.invoke(cli, ["sync", "-r", "owner/repo"])
        assert result.exit_code == 1
        assert "Configuration error" in result.output