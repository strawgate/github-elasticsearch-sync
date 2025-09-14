#!/usr/bin/env python3
"""
Demo script showing basic usage of github-elasticsearch-sync
"""

import os
from github_elasticsearch_sync.config import Config, GitHubConfig, ElasticsearchConfig, SyncConfig

def demo_configuration():
    """Demonstrate configuration loading and validation."""
    print("🔧 GitHub Elasticsearch Sync - Configuration Demo")
    print("=" * 50)
    
    # Create a test configuration
    config = Config(
        github=GitHubConfig(token="demo_token"),
        elasticsearch=ElasticsearchConfig(hosts=["http://localhost:9200"]),
        sync=SyncConfig(repositories=["octocat/Hello-World"])
    )
    
    print("✅ Sample configuration created:")
    print(f"   GitHub: {'Token auth' if config.github.token else 'App auth'}")
    print(f"   Elasticsearch: {', '.join(config.elasticsearch.hosts)}")
    print(f"   Repositories: {', '.join(config.sync.repositories)}")
    print(f"   Index prefix: {config.sync.index_prefix}")
    
    # Test validation
    try:
        config.validate()
        print("✅ Configuration validation passed")
    except ValueError as e:
        print(f"❌ Configuration validation failed: {e}")
    
    print()

def demo_environment_config():
    """Demonstrate environment-based configuration."""
    print("🌍 Environment Configuration Demo")
    print("=" * 40)
    
    # Set some demo environment variables
    os.environ.update({
        'GITHUB_TOKEN': 'demo_github_token',
        'ELASTICSEARCH_HOSTS': 'http://es1:9200,http://es2:9200',
        'GITHUB_REPOSITORIES': 'microsoft/vscode,facebook/react',
        'SYNC_ISSUES': 'true',
        'SYNC_PULL_REQUESTS': 'true',
        'SYNC_COMMENTS': 'false',
        'BATCH_SIZE': '50',
        'INDEX_PREFIX': 'demo'
    })
    
    # Load configuration from environment
    config = Config.from_env()
    
    print("✅ Configuration loaded from environment:")
    print(f"   GitHub token: {config.github.token[:10]}..." if config.github.token else "   No token")
    print(f"   Elasticsearch hosts: {', '.join(config.elasticsearch.hosts)}")
    print(f"   Repositories: {', '.join(config.sync.repositories)}")
    print(f"   Sync settings: Issues={config.sync.sync_issues}, PRs={config.sync.sync_pull_requests}, Comments={config.sync.sync_comments}")
    print(f"   Batch size: {config.sync.batch_size}")
    print(f"   Index prefix: {config.sync.index_prefix}")
    
    print()

def demo_index_names():
    """Demonstrate index naming convention."""
    print("📁 Index Naming Convention Demo")
    print("=" * 35)
    
    from github_elasticsearch_sync.elasticsearch_client import ElasticsearchClient
    from github_elasticsearch_sync.config import ElasticsearchConfig
    
    # Create a demo elasticsearch client
    es_config = ElasticsearchConfig()
    es_client = ElasticsearchClient(es_config)
    
    repositories = [
        "microsoft/vscode",
        "facebook/react", 
        "google/chromium",
        "apache/kafka"
    ]
    
    print("Repository -> Index mapping:")
    for repo in repositories:
        for data_type in ["issues", "pull_requests", "comments", "repository"]:
            index_name = es_client._get_index_name(repo, data_type, "github")
            print(f"   {repo:20} {data_type:15} -> {index_name}")
    
    print()

def main():
    """Run all demo functions."""
    print("🚀 GitHub Elasticsearch Sync - Demo")
    print("=" * 60)
    print("This demo shows the basic functionality without requiring")
    print("actual GitHub or Elasticsearch connections.")
    print()
    
    demo_configuration()
    demo_environment_config()
    demo_index_names()
    
    print("🎉 Demo completed!")
    print("\nTo use the tool for real:")
    print("1. Set GITHUB_TOKEN environment variable")
    print("2. Start Elasticsearch cluster")
    print("3. Run: github-elasticsearch-sync sync -r owner/repo")

if __name__ == "__main__":
    main()