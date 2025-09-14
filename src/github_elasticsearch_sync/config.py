"""Configuration management for GitHub Elasticsearch Sync."""

from typing import Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


@dataclass
class GitHubConfig:
    """GitHub configuration settings."""
    
    token: Optional[str] = None
    app_id: Optional[str] = None
    private_key: Optional[str] = None
    installation_id: Optional[str] = None
    base_url: str = "https://api.github.com"
    
    def __post_init__(self):
        """Load configuration from environment variables if not provided."""
        if not self.token:
            self.token = os.getenv("GITHUB_TOKEN")
        if not self.app_id:
            self.app_id = os.getenv("GITHUB_APP_ID")
        if not self.private_key:
            private_key_path = os.getenv("GITHUB_PRIVATE_KEY_PATH")
            if private_key_path and Path(private_key_path).exists():
                self.private_key = Path(private_key_path).read_text()
            else:
                self.private_key = os.getenv("GITHUB_PRIVATE_KEY")
        if not self.installation_id:
            self.installation_id = os.getenv("GITHUB_INSTALLATION_ID")


@dataclass
class ElasticsearchConfig:
    """Elasticsearch configuration settings."""
    
    hosts: List[str] = field(default_factory=lambda: ["http://localhost:9200"])
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    cloud_id: Optional[str] = None
    ca_certs: Optional[str] = None
    verify_certs: bool = True
    
    def __post_init__(self):
        """Load configuration from environment variables if not provided."""
        if hosts_env := os.getenv("ELASTICSEARCH_HOSTS"):
            self.hosts = [host.strip() for host in hosts_env.split(",")]
        if not self.username:
            self.username = os.getenv("ELASTICSEARCH_USERNAME")
        if not self.password:
            self.password = os.getenv("ELASTICSEARCH_PASSWORD")
        if not self.api_key:
            self.api_key = os.getenv("ELASTICSEARCH_API_KEY")
        if not self.cloud_id:
            self.cloud_id = os.getenv("ELASTICSEARCH_CLOUD_ID")
        if not self.ca_certs:
            self.ca_certs = os.getenv("ELASTICSEARCH_CA_CERTS")
        if verify_env := os.getenv("ELASTICSEARCH_VERIFY_CERTS"):
            self.verify_certs = verify_env.lower() in ("true", "1", "yes")


@dataclass
class SyncConfig:
    """Sync configuration settings."""
    
    repositories: List[str] = field(default_factory=list)
    sync_issues: bool = True
    sync_pull_requests: bool = True
    sync_comments: bool = True
    batch_size: int = 100
    max_concurrent_requests: int = 10
    partial_sync: bool = True
    index_prefix: str = "github"
    
    def __post_init__(self):
        """Load configuration from environment variables if not provided."""
        if repos_env := os.getenv("GITHUB_REPOSITORIES"):
            self.repositories = [repo.strip() for repo in repos_env.split(",")]
        if sync_issues_env := os.getenv("SYNC_ISSUES"):
            self.sync_issues = sync_issues_env.lower() in ("true", "1", "yes")
        if sync_prs_env := os.getenv("SYNC_PULL_REQUESTS"):
            self.sync_pull_requests = sync_prs_env.lower() in ("true", "1", "yes")
        if sync_comments_env := os.getenv("SYNC_COMMENTS"):
            self.sync_comments = sync_comments_env.lower() in ("true", "1", "yes")
        if batch_size_env := os.getenv("BATCH_SIZE"):
            self.batch_size = int(batch_size_env)
        if max_concurrent_env := os.getenv("MAX_CONCURRENT_REQUESTS"):
            self.max_concurrent_requests = int(max_concurrent_env)
        if partial_sync_env := os.getenv("PARTIAL_SYNC"):
            self.partial_sync = partial_sync_env.lower() in ("true", "1", "yes")
        if index_prefix_env := os.getenv("INDEX_PREFIX"):
            self.index_prefix = index_prefix_env


@dataclass
class Config:
    """Main configuration class combining all settings."""
    
    github: GitHubConfig = field(default_factory=GitHubConfig)
    elasticsearch: ElasticsearchConfig = field(default_factory=ElasticsearchConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        return cls(
            github=GitHubConfig(),
            elasticsearch=ElasticsearchConfig(),
            sync=SyncConfig(),
        )
    
    def validate(self) -> None:
        """Validate the configuration."""
        errors = []
        
        # Validate GitHub configuration
        if not self.github.token and not (
            self.github.app_id and self.github.private_key and self.github.installation_id
        ):
            errors.append(
                "GitHub authentication required: either GITHUB_TOKEN or "
                "GITHUB_APP_ID, GITHUB_PRIVATE_KEY, and GITHUB_INSTALLATION_ID"
            )
        
        # Validate repositories
        if not self.sync.repositories:
            errors.append("At least one repository must be specified")
        
        # Validate Elasticsearch configuration
        if not self.elasticsearch.hosts:
            errors.append("Elasticsearch hosts must be specified")
        
        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors))