"""Bump the patch version in a plugin's pyproject.toml.

This script reads a pyproject.toml file, increments the patch version
in the [project] section, and writes it back while preserving formatting.

Usage:
    python scripts/bump_plugin_version.py src/edx_sysadmin/pyproject.toml
    python scripts/bump_plugin_version.py --all-modified
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

VERSION_PATTERN = re.compile(r'^(version\s*=\s*")(\d+\.\d+\.\d+)(")', re.MULTILINE)


def bump_patch_version(version: str) -> str:
    """Increment the patch component of a semver version string."""
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def bump_version_in_file(filepath: Path) -> bool:
    """Bump the patch version in a pyproject.toml file.

    Returns True if the version was bumped, False otherwise.
    """
    content = filepath.read_text(encoding="utf-8")

    match = VERSION_PATTERN.search(content)
    if not match:
        print(f"  No version field found in {filepath}", file=sys.stderr)
        return False

    old_version = match.group(2)
    new_version = bump_patch_version(old_version)

    new_content = VERSION_PATTERN.sub(
        rf"\g<1>{new_version}\3",
        content,
        count=1,
    )

    filepath.write_text(new_content, encoding="utf-8")
    print(f"  {filepath}: {old_version} -> {new_version}")
    return True


def get_modified_plugin_pyproject_files() -> list[Path]:
    """Get plugin pyproject.toml files modified in the current branch.

    Compares against the default branch (origin/main) to find which
    plugin pyproject.toml files have been modified.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )

    modified_files = []
    for line in result.stdout.strip().split("\n"):
        path = Path(line)
        if path.match("src/*/pyproject.toml") and path.exists():
            modified_files.append(path)

    return modified_files


def main() -> None:
    """Run the version bump."""
    parser = argparse.ArgumentParser(
        description="Bump patch version in plugin pyproject.toml files",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Paths to pyproject.toml files to bump",
    )
    parser.add_argument(
        "--all-modified",
        action="store_true",
        help="Bump all plugin pyproject.toml files modified in current branch",
    )

    args = parser.parse_args()

    if args.all_modified:
        files = get_modified_plugin_pyproject_files()
        if not files:
            print("No modified plugin pyproject.toml files found.")
            return
    elif args.files:
        files = [Path(f) for f in args.files]
    else:
        parser.print_help()
        sys.exit(1)

    bumped = 0
    for filepath in files:
        if not filepath.exists():
            print(f"  File not found: {filepath}", file=sys.stderr)
            continue
        if bump_version_in_file(filepath):
            bumped += 1

    print(f"\nBumped {bumped} plugin version(s).")


if __name__ == "__main__":
    main()
