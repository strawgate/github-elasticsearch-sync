"""Command-line interface for GitHub Elasticsearch Sync."""

import asyncio
import sys
from pathlib import Path
from typing import Optional, List
import click
import structlog
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.text import Text

from .config import Config
from .sync_engine import SyncEngine

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
console = Console()


def setup_logging(verbose: bool = False, quiet: bool = False):
    """Set up logging configuration."""
    import logging
    
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    
    logging.basicConfig(level=level)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--quiet", "-q", is_flag=True, help="Enable quiet mode (errors only)")
@click.pass_context
def cli(ctx, verbose: bool, quiet: bool):
    """GitHub Elasticsearch Sync - Sync GitHub repository data to Elasticsearch."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    setup_logging(verbose, quiet)


@cli.command()
@click.option(
    "--repositories", "-r",
    multiple=True,
    help="Repository to sync (format: owner/repo). Can be specified multiple times."
)
@click.option(
    "--config-file", "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file"
)
@click.option(
    "--full-sync", "-f",
    is_flag=True,
    help="Perform full sync (ignore last sync timestamps)"
)
@click.option(
    "--elasticsearch-hosts",
    help="Elasticsearch hosts (comma-separated)"
)
@click.option(
    "--github-token",
    help="GitHub personal access token"
)
@click.option(
    "--index-prefix",
    default="github",
    help="Elasticsearch index prefix"
)
@click.pass_context
def sync(
    ctx,
    repositories: tuple,
    config_file: Optional[Path],
    full_sync: bool,
    elasticsearch_hosts: Optional[str],
    github_token: Optional[str],
    index_prefix: str,
):
    """Sync GitHub repositories to Elasticsearch."""
    try:
        # Load configuration
        config = Config.from_env()
        
        # Override with command line options
        if repositories:
            config.sync.repositories = list(repositories)
        if elasticsearch_hosts:
            config.elasticsearch.hosts = [host.strip() for host in elasticsearch_hosts.split(",")]
        if github_token:
            config.github.token = github_token
        if index_prefix:
            config.sync.index_prefix = index_prefix
        
        # Validate configuration
        try:
            config.validate()
        except ValueError as e:
            console.print(f"[red]Configuration error: {e}[/red]")
            sys.exit(1)
        
        # Run sync
        asyncio.run(_run_sync(config, full_sync, ctx.obj["verbose"]))
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Sync cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Sync failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


async def _run_sync(config: Config, full_sync: bool, verbose: bool):
    """Run the synchronization process."""
    console.print(Panel.fit(
        "[bold blue]GitHub Elasticsearch Sync[/bold blue]\n"
        f"Repositories: {', '.join(config.sync.repositories)}\n"
        f"Elasticsearch: {', '.join(config.elasticsearch.hosts)}\n"
        f"Full sync: {'Yes' if full_sync else 'No'}",
        title="Configuration"
    ))
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        
        task = progress.add_task("Initializing...", total=None)
        
        async with SyncEngine(config) as sync_engine:
            progress.update(task, description="Starting repository sync...")
            
            results = await sync_engine.sync_all_repositories(full_sync=full_sync)
            
            progress.update(task, description="Sync completed", completed=True)
    
    # Display results
    _display_results(results, verbose)


def _display_results(results: List[dict], verbose: bool):
    """Display sync results in a formatted table."""
    table = Table(title="Sync Results")
    table.add_column("Repository", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Issues", justify="right")
    table.add_column("PRs", justify="right")
    table.add_column("Comments", justify="right")
    table.add_column("Duration", justify="right")
    
    if verbose:
        table.add_column("Errors", style="red")
    
    total_issues = 0
    total_prs = 0
    total_comments = 0
    successful_repos = 0
    
    for result in results:
        status = "[green]✓[/green]" if result.get("success", False) else "[red]✗[/red]"
        issues = result.get("issues_synced", 0)
        prs = result.get("pull_requests_synced", 0)
        comments = result.get("comments_synced", 0)
        
        duration = ""
        if "duration_seconds" in result:
            duration = f"{result['duration_seconds']:.1f}s"
        
        row = [
            result["repository"],
            status,
            str(issues),
            str(prs),
            str(comments),
            duration,
        ]
        
        if verbose:
            errors = result.get("errors", [])
            error_text = f"{len(errors)} errors" if errors else "None"
            row.append(error_text)
        
        table.add_row(*row)
        
        if result.get("success", False):
            successful_repos += 1
            total_issues += issues
            total_prs += prs
            total_comments += comments
    
    console.print()
    console.print(table)
    
    # Summary
    console.print()
    console.print(Panel.fit(
        f"[bold]Summary[/bold]\n"
        f"Repositories: {successful_repos}/{len(results)} successful\n"
        f"Total synced: {total_issues} issues, {total_prs} PRs, {total_comments} comments",
        title="Sync Summary"
    ))
    
    # Show errors if any
    if verbose:
        for result in results:
            errors = result.get("errors", [])
            if errors:
                console.print(f"\n[red]Errors for {result['repository']}:[/red]")
                for error in errors:
                    console.print(f"  • {error}")


@cli.command()
@click.option(
    "--elasticsearch-hosts",
    help="Elasticsearch hosts (comma-separated)"
)
@click.option(
    "--repository", "-r",
    help="Repository to check (format: owner/repo)"
)
@click.option(
    "--index-prefix",
    default="github",
    help="Elasticsearch index prefix"
)
@click.pass_context
def status(ctx, elasticsearch_hosts: Optional[str], repository: Optional[str], index_prefix: str):
    """Check sync status and index information."""
    try:
        config = Config.from_env()
        
        if elasticsearch_hosts:
            config.elasticsearch.hosts = [host.strip() for host in elasticsearch_hosts.split(",")]
        if index_prefix:
            config.sync.index_prefix = index_prefix
        
        asyncio.run(_show_status(config, repository))
        
    except Exception as e:
        console.print(f"[red]Status check failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


async def _show_status(config: Config, repository: Optional[str]):
    """Show sync status information."""
    from .elasticsearch_client import ElasticsearchClient
    
    async with ElasticsearchClient(config.elasticsearch) as es_client:
        console.print("[blue]Checking Elasticsearch connection...[/blue]")
        
        # Get cluster health
        health = await es_client._client.cluster.health()
        console.print(f"Cluster status: [{'green' if health['status'] == 'green' else 'yellow'}]{health['status']}[/]")
        
        # Check repositories
        repositories = [repository] if repository else config.sync.repositories
        
        if not repositories:
            console.print("[yellow]No repositories specified[/yellow]")
            return
        
        table = Table(title="Repository Status")
        table.add_column("Repository", style="cyan")
        table.add_column("Issues Index", justify="center")
        table.add_column("PRs Index", justify="center")
        table.add_column("Comments Index", justify="center")
        table.add_column("Last Sync", justify="center")
        
        for repo in repositories:
            # Check indices
            indices_status = {}
            last_sync = None
            
            for data_type in ["issues", "pull_requests", "comments"]:
                index_name = es_client._get_index_name(repo, data_type, config.sync.index_prefix)
                exists = await es_client._client.indices.exists(index=index_name)
                indices_status[data_type] = "[green]✓[/green]" if exists else "[red]✗[/red]"
                
                if exists and not last_sync:
                    timestamp = await es_client.get_last_synced_timestamp(repo, data_type, config.sync.index_prefix)
                    if timestamp:
                        last_sync = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            
            table.add_row(
                repo,
                indices_status.get("issues", "[red]✗[/red]"),
                indices_status.get("pull_requests", "[red]✗[/red]"),
                indices_status.get("comments", "[red]✗[/red]"),
                last_sync or "Never"
            )
        
        console.print()
        console.print(table)


@cli.command()
@click.option(
    "--elasticsearch-hosts",
    help="Elasticsearch hosts (comma-separated)"
)
@click.option(
    "--repository", "-r",
    required=True,
    help="Repository to clean (format: owner/repo)"
)
@click.option(
    "--index-prefix",
    default="github",
    help="Elasticsearch index prefix"
)
@click.option(
    "--confirm", "-y",
    is_flag=True,
    help="Skip confirmation prompt"
)
@click.pass_context
def clean(ctx, elasticsearch_hosts: Optional[str], repository: str, index_prefix: str, confirm: bool):
    """Clean (delete) all indices for a repository."""
    try:
        config = Config.from_env()
        
        if elasticsearch_hosts:
            config.elasticsearch.hosts = [host.strip() for host in elasticsearch_hosts.split(",")]
        if index_prefix:
            config.sync.index_prefix = index_prefix
        
        if not confirm:
            console.print(f"[yellow]This will delete all indices for repository '{repository}'[/yellow]")
            if not click.confirm("Are you sure?"):
                console.print("Cancelled")
                return
        
        asyncio.run(_clean_repository(config, repository))
        
    except Exception as e:
        console.print(f"[red]Clean failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print_exception()
        sys.exit(1)


async def _clean_repository(config: Config, repository: str):
    """Clean all indices for a repository."""
    from .elasticsearch_client import ElasticsearchClient
    
    async with ElasticsearchClient(config.elasticsearch) as es_client:
        data_types = ["issues", "pull_requests", "comments", "repository"]
        
        for data_type in data_types:
            index_name = es_client._get_index_name(repository, data_type, config.sync.index_prefix)
            try:
                await es_client.delete_index(index_name)
                console.print(f"[green]Deleted index: {index_name}[/green]")
            except Exception as e:
                console.print(f"[yellow]Could not delete {index_name}: {e}[/yellow]")
        
        console.print(f"[green]Cleaned all indices for repository: {repository}[/green]")


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()