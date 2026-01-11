"""Command-line interface for Obsidian Publisher."""

import sys
from pathlib import Path
import click

from obsidian_publisher.core.publisher import create_publisher_from_config, PublishResult


def print_result(result: PublishResult) -> None:
    """Print publish result summary."""
    if result.dry_run:
        click.echo(click.style("DRY RUN - No changes made", fg='yellow'))
        click.echo()

    if result.published_titles:
        click.echo(click.style(f"Published ({len(result.published_titles)}):", fg='green'))
        for name in result.published_titles:
            click.echo(f"  - {name}")

    if result.failures:
        click.echo(click.style(f"Failed ({len(result.failures)}):", fg='red'))
        for failure in result.failures:
            click.echo(f"  - {failure.note_title}: {failure.error}")

    if result.removed_image_paths:
        click.echo(click.style(f"Orphans removed ({len(result.removed_image_paths)}):", fg='yellow'))
        for path in result.removed_image_paths:
            click.echo(f"  - {path}")

    # Summary
    click.echo()
    if result.published_titles and not result.failures:
        click.echo(click.style("Success!", fg='green', bold=True))
    elif result.failures:
        click.echo(click.style("Completed with errors", fg='red', bold=True))


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Obsidian to Static Site Publisher.

    Publish notes from your Obsidian vault to a static site generator.
    Supports wikilink conversion, image optimization, and tag filtering.
    """
    pass


@cli.command()
@click.option(
    '--config', '-c',
    type=click.Path(exists=True, path_type=Path),
    default='config.yaml',
    help='Path to configuration file'
)
@click.option(
    '--dry-run', '-n',
    is_flag=True,
    help="Preview without making changes"
)
def republish(config: Path, dry_run: bool):
    """Republish all eligible notes.

    Discovers all notes matching the tag filters and publishes them
    to the configured output directory. Also processes referenced images
    and cleans up orphaned images.
    """
    try:
        publisher = create_publisher_from_config(config)
        result = publisher.republish(dry_run=dry_run)
        print_result(result)

        if result.failures:
            sys.exit(1)

    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'), err=True)
        sys.exit(1)


@cli.command()
@click.argument('note_name')
@click.option(
    '--config', '-c',
    type=click.Path(exists=True, path_type=Path),
    default='config.yaml',
    help='Path to configuration file'
)
@click.option(
    '--dry-run', '-n',
    is_flag=True,
    help="Preview without making changes"
)
def add(note_name: str, config: Path, dry_run: bool):
    """Add or update a specific note.

    Publishes a single note by name. The note must match the configured
    tag filters to be published.

    NOTE_NAME can be the note title, filename, or path.
    """
    try:
        publisher = create_publisher_from_config(config)
        result = publisher.add(note_name, dry_run=dry_run)
        print_result(result)

        if result.failures:
            sys.exit(1)

    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'), err=True)
        sys.exit(1)


@cli.command()
@click.argument('note_name')
@click.option(
    '--config', '-c',
    type=click.Path(exists=True, path_type=Path),
    default='config.yaml',
    help='Path to configuration file'
)
@click.option(
    '--dry-run', '-n',
    is_flag=True,
    help="Preview without making changes"
)
def delete(note_name: str, config: Path, dry_run: bool):
    """Delete a published note.

    Removes the published note and cleans up any orphaned images
    that are no longer referenced by other published notes.

    NOTE_NAME is the note title or slug.
    """
    try:
        publisher = create_publisher_from_config(config)
        result = publisher.delete(note_name, dry_run=dry_run)
        print_result(result)

        if result.failures:
            sys.exit(1)

    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'), err=True)
        sys.exit(1)


@cli.command()
@click.option(
    '--config', '-c',
    type=click.Path(exists=True, path_type=Path),
    default='config.yaml',
    help='Path to configuration file'
)
def list_notes(config: Path):
    """List all publishable notes.

    Shows all notes in the vault that match the configured tag filters.
    """
    try:
        publisher = create_publisher_from_config(config)
        notes = publisher.discovery.discover_all()

        if not notes:
            click.echo("No publishable notes found.")
            return

        click.echo(f"Found {len(notes)} publishable note(s):")
        click.echo()

        for note in sorted(notes, key=lambda n: n.title):
            tags_str = ", ".join(note.tags[:3])
            if len(note.tags) > 3:
                tags_str += f" (+{len(note.tags) - 3} more)"
            click.echo(f"  {note.title}")
            click.echo(click.style(f"    Tags: {tags_str}", dim=True))

    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg='red'), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg='red'), err=True)
        sys.exit(1)


@cli.command()
@click.argument('output', type=click.Path(path_type=Path))
def init(output: Path):
    """Initialize a new config file.

    Creates a sample config.yaml file with sensible defaults.
    """
    if output.exists():
        click.echo(click.style(f"Error: {output} already exists", fg='red'), err=True)
        sys.exit(1)

    sample_config = """# Obsidian Publisher Configuration

# Path to your Obsidian vault
vault_path: ~/Obsidian/MyVault

# Path to your static site (e.g., Hugo site)
output_path: ~/Sites/my-blog

# Subdirectory within vault to scan for notes (default: vault root)
source_dir: "."

# Output directories within the static site
content_dir: content/posts
image_dir: static/images

# Directories within vault to search for images
image_sources:
  - assets
  - attachments

# Tags for filtering notes
required_tags:
  - evergreen
excluded_tags:
  - draft
  - private

# Image optimization settings
optimize_images: true
max_image_width: 1920
webp_quality: 85
image_path_prefix: /images

# Link transform: relative, absolute, or hugo_ref
link_transform:
  type: absolute
  prefix: /posts

# Tag transform: filter and format tags for output
tag_transform:
  prefixes:
    - domain
    - type
  replace_separator:
    - "/"
    - "-"

# Frontmatter settings
frontmatter:
  hugo: true
  author: Your Name
"""

    output.write_text(sample_config)
    click.echo(click.style(f"Created {output}", fg='green'))
    click.echo("Edit this file with your vault and site paths.")


if __name__ == '__main__':
    cli()
