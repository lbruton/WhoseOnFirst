#!/usr/bin/env python3
"""
Version Bump Script for WhoseOnFirst
=====================================

Automatically updates version numbers across all project files.

Usage:
    python scripts/bump_version.py 1.0.3
    python scripts/bump_version.py 1.1.0 --changelog "Added new feature X"

Updates version in:
- VERSION (canonical source of truth — every runtime surface reads this)
- README.md (badge + current version)
- CLAUDE.md (multiple locations)
- Foundation docs (.context/ files)
- CHANGELOG.md (creates new release entry)

Runtime surfaces (src/main.py FastAPI app + /api + /health, /api/v1/version,
and the sidebar footer badge) read VERSION dynamically, so they need no
rewriting here — bumping VERSION is enough (WOF-14).
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

# ANSI color codes for pretty output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.END}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.CYAN}→ {text}{Colors.END}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def get_current_version(version_file: Path) -> str:
    """Read the current version from the canonical VERSION file."""
    if version_file.exists():
        return version_file.read_text().strip()
    return "unknown"


def update_file(file_path: Path, old_version: str, new_version: str) -> Tuple[bool, int]:
    """
    Update version in a file.

    Returns:
        Tuple of (success: bool, replacements_count: int)
    """
    if not file_path.exists():
        print_warning(f"File not found: {file_path}")
        return False, 0

    content = file_path.read_text()

    # Count replacements before making changes
    count = content.count(old_version)

    if count == 0:
        print_info(f"No version references in {file_path.name}")
        return True, 0

    # Perform replacement
    updated = content.replace(old_version, new_version)

    # Write back
    file_path.write_text(updated)

    print_success(f"Updated {file_path.name} ({count} replacements)")
    return True, count


def update_changelog(changelog_path: Path, new_version: str, notes: str = None):
    """Add new version entry to CHANGELOG.md"""

    if not changelog_path.exists():
        print_error("CHANGELOG.md not found")
        return False

    content = changelog_path.read_text()
    today = datetime.now().strftime("%Y-%m-%d")

    # Find where to insert (after header, before first version)
    unreleased_pattern = r'## \[Unreleased\]'

    # Template for new version entry
    new_entry = f"""## [{new_version}] - {today}

### Added

-

### Changed

-

### Fixed

-

---

"""

    # If changelog has Unreleased section, insert after it
    if '## [Unreleased]' in content:
        # Insert after Unreleased section
        content = re.sub(
            r'(## \[Unreleased\].*?)(---\n+)',
            rf'\1{new_entry}\2',
            content,
            flags=re.DOTALL
        )
    else:
        # Insert after main header
        content = re.sub(
            r'(---\n+)',
            rf'\1{new_entry}',
            content,
            count=1
        )

    # Update version links at bottom
    # Add new version link
    version_links = f"\n[{new_version}]: https://github.com/Lonnie-Bruton/WhoseOnFirst/compare/v{get_previous_version(content, new_version)}...v{new_version}"
    content = content.rstrip() + version_links + "\n"

    changelog_path.write_text(content)
    print_success(f"Added v{new_version} entry to CHANGELOG.md")
    print_info("Don't forget to fill in the Added/Changed/Fixed sections!")

    return True


def get_previous_version(changelog_content: str, current_version: str) -> str:
    """Extract the previous version from changelog"""
    versions = re.findall(r'\[(\d+\.\d+\.\d+)\]', changelog_content)
    if len(versions) > 1:
        return versions[1]  # Second version is the previous one
    return "1.0.0"


def main():
    """Main version bump workflow"""

    if len(sys.argv) < 2:
        print_error("Usage: python scripts/bump_version.py <new_version> [--changelog <notes>]")
        print_info("Example: python scripts/bump_version.py 1.0.3")
        sys.exit(1)

    new_version = sys.argv[1]

    # Validate version format (semantic versioning)
    if not re.match(r'^\d+\.\d+\.\d+$', new_version):
        print_error(f"Invalid version format: {new_version}")
        print_info("Version must be in format: X.Y.Z (e.g., 1.0.3)")
        sys.exit(1)

    # Project root
    root = Path(__file__).parent.parent

    # Get current version from the canonical VERSION file (single source of truth).
    # src/main.py now derives its version from VERSION at runtime (WOF-14), so the
    # only literals left to rewrite are VERSION itself and the docs.
    version_file = root / "VERSION"
    old_version = get_current_version(version_file)

    print_header(f"WhoseOnFirst Version Bump: {old_version} → {new_version}")

    if old_version == new_version:
        print_warning("New version is the same as current version")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print_info("Aborted")
            sys.exit(0)

    # Files to update
    files_to_update = [
        # Canonical source of truth — every runtime surface reads this
        root / "VERSION",

        # Docs that embed the version as text
        root / "README.md",
        root / "CLAUDE.md",

        # Foundation docs (.context/)
        root / ".context" / "architecture.md",
        root / ".context" / "technical-stack.md",
        root / ".context" / "code-patterns.md",
        root / ".context" / "rpi-process.md",
        root / ".context" / "authentication.md",
    ]

    total_replacements = 0
    updated_files = 0

    print_info(f"Updating {len(files_to_update)} files...")
    print()

    for file_path in files_to_update:
        success, count = update_file(file_path, old_version, new_version)
        if success and count > 0:
            updated_files += 1
            total_replacements += count

    print()
    print_header("Summary")
    print_success(f"Updated {updated_files} files")
    print_success(f"Made {total_replacements} replacements")

    # Update changelog
    print()
    print_info("Updating CHANGELOG.md...")
    update_changelog(root / "CHANGELOG.md", new_version)

    print()
    print_header("Next Steps")
    print_info("1. Review changes with: git diff")
    print_info("2. Fill in CHANGELOG.md with release notes")
    print_info("3. Rebuild Docker: docker-compose -f docker-compose.dev.yml down && docker-compose -f docker-compose.dev.yml build && docker-compose -f docker-compose.dev.yml up -d")
    print_info("4. Test the application")
    print_info("5. Commit: git add . && git commit -m 'chore: bump version to v{new_version}'")
    print_info(f"6. Tag: git tag -a v{new_version} -m 'Release v{new_version}'")
    print_info("7. Push: git push && git push --tags")
    print()

    print_success(f"Version bump to v{new_version} complete!")


if __name__ == "__main__":
    main()
