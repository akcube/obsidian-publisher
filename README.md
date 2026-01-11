# Obsidian Publisher

[![PyPI](https://img.shields.io/pypi/v/obsidian-publisher)](https://pypi.org/project/obsidian-publisher/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/obsidian-publisher)](https://pypi.org/project/obsidian-publisher/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![GitHub last commit](https://img.shields.io/github/last-commit/akcube/obsidian-publisher)](https://github.com/akcube/obsidian-publisher/commits/master)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A modular Python library for publishing notes from an Obsidian vault to static site generators like Hugo.

## Features

- **Wikilink Conversion**: Converts Obsidian `[[wikilinks]]` to standard markdown links
- **Tag Filtering**: Publish only notes with specific tags (e.g., `status/evergreen`)
- **Tag Transformation**: Filter, rename, and reformat tags for your site
- **Image Optimization**: Converts images to WebP with PNG fallback
- **Frontmatter Processing**: Transform frontmatter for Hugo or other SSGs
- **Orphan Cleanup**: Automatically removes unused images

## Installation

```bash
pip install obsidian-publisher
```

Or install from source:

```bash
git clone https://github.com/akcube/obsidian-publisher.git
cd obsidian-publisher
pip install -e .
```

## Quick Start

1. Initialize a config file:

```bash
obsidian-publish init config.yaml
```

2. Edit `config.yaml` with your vault and site paths:

```yaml
vault_path: ~/Obsidian/MyVault
output_path: ~/Sites/my-blog
source_dir: Zettelkasten
required_tags:
  - status/evergreen
```

3. Publish all eligible notes:

```bash
obsidian-publish republish -c config.yaml
```

## CLI Commands

```bash
# Republish all eligible notes
obsidian-publish republish -c config.yaml

# Preview without making changes
obsidian-publish republish -c config.yaml --dry-run

# Publish a specific note
obsidian-publish add "My Note Title" -c config.yaml

# Remove a published note
obsidian-publish delete "My Note Title" -c config.yaml

# List all publishable notes
obsidian-publish list-notes -c config.yaml
```

## Configuration

### Basic Configuration

```yaml
# Paths
vault_path: ~/Obsidian/MyVault
output_path: ~/Sites/my-blog
source_dir: Zettelkasten  # Subdirectory within vault

# Output directories
content_dir: content/posts
image_dir: static/images

# Image sources within vault
image_sources:
  - assets
  - attachments
```

### Tag Filtering

```yaml
# Required tags (note must have at least one)
required_tags:
  - status/evergreen

# Excluded tags (note with any of these is skipped)
excluded_tags:
  - status/draft
  - status/private
```

### Link Transforms

```yaml
# Relative links: [Title](slug.md)
link_transform:
  type: relative

# Absolute links: [Title](/blog/slug)
link_transform:
  type: absolute
  prefix: /blog

# Hugo ref shortcode: [Title]({{< ref "slug" >}})
link_transform:
  type: hugo_ref
```

### Tag Transforms

```yaml
# Filter tags by prefix and change separator
tag_transform:
  prefixes:
    - domain
    - type
  replace_separator:
    - "/"
    - "-"
# Result: domain/cs/algo → domain-cs-algo
```

### Frontmatter Settings

```yaml
frontmatter:
  hugo: true
  author: Your Name
```

### Image Optimization

```yaml
optimize_images: true
max_image_width: 1920
webp_quality: 85
image_path_prefix: /images
```

## Python API

### Basic Usage

```python
from pathlib import Path
from obsidian_publisher.core.publisher import Publisher, PublisherConfig

config = PublisherConfig(
    vault_path=Path("~/Obsidian/MyVault"),
    output_path=Path("~/Sites/my-blog"),
    source_dir="Zettelkasten",
    required_tags=["status/evergreen"],
)

publisher = Publisher(config)
result = publisher.republish()

print(f"Published: {result.published}")
print(f"Failed: {result.failed}")
```

### Custom Transforms

```python
from obsidian_publisher.transforms.links import absolute_link
from obsidian_publisher.transforms.tags import filter_by_prefix, replace_separator, sort_tags, compose
from obsidian_publisher.transforms.frontmatter import hugo_frontmatter

# Create custom transforms
link_transform = absolute_link("/blog")
tag_transform = compose(
    filter_by_prefix("domain", "type"),
    replace_separator("/", "-"),
    sort_tags(),  # Sort tags alphabetically
)
frontmatter_transform = hugo_frontmatter("Author Name")

publisher = Publisher(
    config,
    link_transform=link_transform,
    tag_transform=tag_transform,
    frontmatter_transform=frontmatter_transform,
)
```

## Architecture

The library is designed with modularity in mind:

```
obsidian_publisher/
├── core/
│   ├── discovery.py    # VaultDiscovery - finds publishable notes
│   ├── processor.py    # ContentProcessor - transforms content
│   ├── publisher.py    # Publisher - orchestrates everything
│   └── models.py       # Data models
├── transforms/
│   ├── links.py        # Link transform factories
│   ├── tags.py         # Tag transform factories
│   └── frontmatter.py  # Frontmatter transform factories
├── images/
│   └── optimizer.py    # ImageOptimizer - WebP conversion
└── cli/
    └── main.py         # Click CLI
```

### Transform Pattern

All transforms are factory functions that return callables:

```python
# Link transform: (title, slug) -> markdown_link
def absolute_link(prefix: str = "") -> LinkTransform:
    def transform(title: str, slug: str) -> str:
        return f"[{title}]({prefix}/{slug})"
    return transform

# Tag transform: (tags) -> tags
def filter_by_prefix(*prefixes: str) -> TagTransform:
    def transform(tags: List[str]) -> List[str]:
        return [t for t in tags if any(t.startswith(p) for p in prefixes)]
    return transform

def sort_tags() -> TagTransform:
    return lambda tags: sorted(tags)
```

## Development

```bash
# Clone and install dev dependencies
git clone https://github.com/akcube/obsidian-publisher.git
cd obsidian-publisher
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=obsidian_publisher
```

## License

MIT License
