# GitHub Elasticsearch Sync

A modern Python tool for syncing GitHub repository data (issues, pull requests, and comments) to Elasticsearch clusters. Built with async/await patterns using GitHubKit and AsyncElasticsearch for high-performance data synchronization.

## Features

- **Modern Python Architecture**: Built with Python 3.9+ using async/await patterns
- **Multiple Repository Support**: Sync multiple repositories into separate Elasticsearch indices
- **Comprehensive Data Sync**: Issues, pull requests, and comments with full metadata
- **Smart Partial Sync**: Incremental updates based on last sync timestamps
- **Flexible Authentication**: Support for GitHub tokens and GitHub Apps
- **Rich CLI Interface**: Beautiful command-line interface with progress tracking
- **Robust Error Handling**: Comprehensive error handling and logging
- **Configurable**: Environment variables and command-line configuration
- **Production Ready**: Structured logging, bulk operations, and concurrent processing

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/strawgate/github-elasticsearch-sync.git
cd github-elasticsearch-sync

# Install with pip (development mode)
pip install -e .

# Or install with UV (recommended)
uv pip install -e .
```

### Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your configuration:
```bash
# GitHub Authentication (choose one)
GITHUB_TOKEN=your_github_token_here

# Elasticsearch Configuration
ELASTICSEARCH_HOSTS=http://localhost:9200

# Repositories to sync
GITHUB_REPOSITORIES=owner/repo1,owner/repo2
```

### Basic Usage

```bash
# Sync all configured repositories
github-elasticsearch-sync sync

# Sync specific repositories
github-elasticsearch-sync sync -r owner/repo1 -r owner/repo2

# Perform a full sync (ignore incremental timestamps)
github-elasticsearch-sync sync --full-sync

# Check sync status
github-elasticsearch-sync status

# Clean all data for a repository
github-elasticsearch-sync clean -r owner/repo
```

## Configuration

### Environment Variables

#### GitHub Configuration
- `GITHUB_TOKEN`: Personal access token for GitHub API
- `GITHUB_APP_ID`: GitHub App ID (alternative to token)
- `GITHUB_PRIVATE_KEY`: GitHub App private key (alternative to token)
- `GITHUB_PRIVATE_KEY_PATH`: Path to GitHub App private key file
- `GITHUB_INSTALLATION_ID`: GitHub App installation ID

#### Elasticsearch Configuration
- `ELASTICSEARCH_HOSTS`: Comma-separated list of Elasticsearch hosts
- `ELASTICSEARCH_USERNAME`: Username for basic authentication
- `ELASTICSEARCH_PASSWORD`: Password for basic authentication
- `ELASTICSEARCH_API_KEY`: API key for authentication
- `ELASTICSEARCH_CLOUD_ID`: Elastic Cloud ID
- `ELASTICSEARCH_CA_CERTS`: Path to CA certificates
- `ELASTICSEARCH_VERIFY_CERTS`: Whether to verify certificates (true/false)

#### Sync Configuration
- `GITHUB_REPOSITORIES`: Comma-separated list of repositories (owner/repo format)
- `SYNC_ISSUES`: Whether to sync issues (true/false)
- `SYNC_PULL_REQUESTS`: Whether to sync pull requests (true/false)
- `SYNC_COMMENTS`: Whether to sync comments (true/false)
- `BATCH_SIZE`: Number of items to process in each batch
- `MAX_CONCURRENT_REQUESTS`: Maximum concurrent API requests
- `PARTIAL_SYNC`: Whether to use incremental sync (true/false)
- `INDEX_PREFIX`: Prefix for Elasticsearch indices

### GitHub Authentication

#### Personal Access Token (Recommended for Development)
```bash
GITHUB_TOKEN=ghp_your_token_here
```

Required scopes:
- `repo` (for private repositories)
- `public_repo` (for public repositories)

#### GitHub App (Recommended for Production)
```bash
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY_PATH=/path/to/private-key.pem
GITHUB_INSTALLATION_ID=12345678
```

## CLI Commands

### `sync` - Synchronize Repositories

```bash
# Basic sync
github-elasticsearch-sync sync

# Sync specific repositories
github-elasticsearch-sync sync -r owner/repo1 -r owner/repo2

# Full sync (ignore incremental timestamps)
github-elasticsearch-sync sync --full-sync

# Custom Elasticsearch hosts
github-elasticsearch-sync sync --elasticsearch-hosts http://localhost:9200,http://localhost:9201

# Custom index prefix
github-elasticsearch-sync sync --index-prefix myproject
```

### `status` - Check Sync Status

```bash
# Check all configured repositories
github-elasticsearch-sync status

# Check specific repository
github-elasticsearch-sync status -r owner/repo

# Custom Elasticsearch hosts
github-elasticsearch-sync status --elasticsearch-hosts http://localhost:9200
```

### `clean` - Clean Repository Data

```bash
# Clean all data for a repository (with confirmation)
github-elasticsearch-sync clean -r owner/repo

# Clean without confirmation
github-elasticsearch-sync clean -r owner/repo -y
```

## Index Structure

The tool creates separate indices for each repository and data type:

- `{prefix}_{owner}_{repo}_issues` - Issues
- `{prefix}_{owner}_{repo}_pull_requests` - Pull requests
- `{prefix}_{owner}_{repo}_comments` - Comments (issues and PR comments)
- `{prefix}_{owner}_{repo}_repository` - Repository metadata

### Example Index Names
For repository `octocat/Hello-World` with prefix `github`:
- `github_octocat_hello_world_issues`
- `github_octocat_hello_world_pull_requests`
- `github_octocat_hello_world_comments`
- `github_octocat_hello_world_repository`

## Data Schema

### Issues
```json
{
  "id": 123456789,
  "number": 1,
  "title": "Issue title",
  "body": "Issue description",
  "state": "open",
  "user": {
    "id": 123456,
    "login": "username",
    "type": "User"
  },
  "assignees": [...],
  "labels": [...],
  "milestone": {...},
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-02T00:00:00Z",
  "closed_at": null,
  "html_url": "https://github.com/owner/repo/issues/1",
  "comments": 5,
  "repository": "owner/repo",
  "synced_at": "2024-01-03T00:00:00Z"
}
```

### Pull Requests
```json
{
  "id": 123456789,
  "number": 1,
  "title": "PR title",
  "body": "PR description",
  "state": "open",
  "user": {...},
  "head": {
    "ref": "feature-branch",
    "sha": "abc123..."
  },
  "base": {
    "ref": "main",
    "sha": "def456..."
  },
  "merged": false,
  "mergeable": true,
  "comments": 3,
  "review_comments": 2,
  "commits": 5,
  "additions": 100,
  "deletions": 50,
  "changed_files": 3,
  "repository": "owner/repo",
  "synced_at": "2024-01-03T00:00:00Z"
}
```

### Comments
```json
{
  "id": 123456789,
  "body": "Comment text",
  "user": {...},
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-02T00:00:00Z",
  "html_url": "https://github.com/owner/repo/issues/1#issuecomment-123456789",
  "issue_number": 1,
  "repository": "owner/repo",
  "comment_type": "issue",
  "synced_at": "2024-01-03T00:00:00Z"
}
```

## Development

### Setup Development Environment

```bash
# Clone and install
git clone https://github.com/strawgate/github-elasticsearch-sync.git
cd github-elasticsearch-sync

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific tests
pytest tests/test_client.py
```

### Code Quality

```bash
# Format code
black src tests

# Sort imports
isort src tests

# Lint code
flake8 src tests

# Type checking
mypy src
```

## Docker Support

### Docker Compose Example

```yaml
version: '3.8'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
  
  github-sync:
    build: .
    environment:
      - GITHUB_TOKEN=your_token_here
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
      - GITHUB_REPOSITORIES=owner/repo1,owner/repo2
    depends_on:
      - elasticsearch
    command: ["sync"]
```

## Production Deployment

### Kubernetes Example

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: github-elasticsearch-sync
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: sync
            image: github-elasticsearch-sync:latest
            command: ["github-elasticsearch-sync", "sync"]
            env:
            - name: GITHUB_TOKEN
              valueFrom:
                secretKeyRef:
                  name: github-secrets
                  key: token
            - name: ELASTICSEARCH_HOSTS
              value: "http://elasticsearch:9200"
            - name: GITHUB_REPOSITORIES
              value: "owner/repo1,owner/repo2"
          restartPolicy: OnFailure
```

## Monitoring

### Logging

The tool uses structured logging with JSON output. Key log fields:
- `level`: Log level (DEBUG, INFO, WARNING, ERROR)
- `timestamp`: ISO 8601 timestamp
- `repository`: Repository being processed
- `event`: Event type (sync_start, sync_complete, etc.)
- `count`: Number of items processed
- `duration_seconds`: Operation duration

### Metrics

Monitor these key metrics:
- Sync duration per repository
- Number of items synced (issues, PRs, comments)
- Error rates and types
- Elasticsearch indexing performance

## Troubleshooting

### Common Issues

#### Authentication Errors
- Verify GitHub token has correct scopes
- Check token hasn't expired
- For GitHub Apps, verify installation ID and private key

#### Elasticsearch Connection Issues
- Verify Elasticsearch hosts are accessible
- Check authentication credentials
- Verify SSL/TLS configuration

#### Rate Limiting
- GitHub API rate limits: 5000 requests/hour for authenticated users
- Reduce `MAX_CONCURRENT_REQUESTS` if hitting rate limits
- Consider using GitHub Apps for higher rate limits

#### Memory Usage
- Reduce `BATCH_SIZE` for large repositories
- Monitor memory usage during sync operations

### Debug Mode

```bash
# Enable verbose logging
github-elasticsearch-sync -v sync

# Check Elasticsearch cluster health
curl http://localhost:9200/_cluster/health

# List all indices
curl http://localhost:9200/_cat/indices?v
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.
