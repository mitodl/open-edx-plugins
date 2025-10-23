# Open edX Plugins Repository - Agent Guide

## Repository Overview

This repository contains a collection of 17+ Open edX plugins that extend and enhance the Open edX platform functionality. The plugins are MIT Open Learning Engineering's custom extensions for features like system administration, authentication, monitoring, course management, and integrations.

**Repository Type:** Python monorepo with multiple independent plugin packages
**Size:** ~170 Python source files across 17 plugins
**Languages/Frameworks:** Python 3.11+, Django 4.0+, Open edX platform
**Build System:** UV (modern Python package manager), Hatchling backend
**Target Runtime:** Open edX platform (tested against master, sumac.master, and teak releases)

## Repository Structure

```
edx-extensions/
├── src/                          # Source code (workspace with 17 plugin packages)
│   ├── edx_sysadmin/            # SysAdmin dashboard plugin
│   ├── edx_username_changer/    # Username modification plugin
│   ├── ol_openedx_chat/         # Chat integration
│   ├── ol_openedx_chat_xblock/  # Chat XBlock
│   ├── ol_openedx_course_sync/  # Course synchronization
│   ├── ol_openedx_git_auto_export/ # Git export automation
│   ├── ol_openedx_logging/      # Logging enhancements
│   ├── ol_openedx_otel_monitoring/ # OpenTelemetry monitoring
│   ├── ol_openedx_sentry/       # Sentry integration
│   ├── ol_social_auth/          # Social authentication
│   ├── openedx_companion_auth/  # Companion authentication
│   ├── rapid_response_xblock/   # Rapid response XBlock
│   └── [others...]              # Additional plugins
├── docs/                         # Installation and testing guide (README.rst)
├── .github/workflows/            # CI/CD workflows
│   ├── ci.yml                   # Integration tests with Tutor/edX
│   └── test-and-build.yml       # Unit tests and package building
├── pyproject.toml               # Root workspace configuration
├── uv.lock                      # Locked dependencies
├── setup.cfg                    # Legacy flake8/mypy config
├── .pre-commit-config.yaml      # Pre-commit hooks configuration
├── run_edx_integration_tests.sh # Test runner script
└── image_check.sh               # Docker image verification

Each plugin directory contains:
- pyproject.toml          # Plugin-specific package metadata
- setup.cfg               # Additional configuration
- <plugin_name>/          # Source code directory
  ├── apps.py            # Django app configuration
  ├── models.py          # Django models
  ├── views.py           # Views/APIs
  ├── settings/          # Plugin settings (some plugins)
  ├── static/            # Static assets
  └── templates/         # Django templates
- tests/                 # Plugin tests
- README.rst             # Plugin documentation
```

## Build & Development Workflow

### Prerequisites
- Python 3.11 or later
- UV package manager (installed automatically in CI, or install via: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- For integration tests: Tutor and Docker (Open edX development environment)

### Essential Commands

**Install dependencies:**
```bash
uv sync --dev
```
This installs all workspace dependencies and dev tools (pytest, ruff, pre-commit, etc.). Always run this first in a clean environment or after pulling changes.

**Build all packages:**
```bash
uv build --all-packages
```
Builds wheel and source distributions for all 17 plugins. Output goes to `dist/` directory. Takes ~30-60 seconds.

**Run linter:**
```bash
uv run ruff check .
uv run ruff format .  # Auto-format code
```
Lints all Python code using Ruff with extensive rule set (see pyproject.toml). Must pass for CI.

**Run pre-commit hooks:**
```bash
pre-commit run --all-files
```
Runs all quality checks: trailing whitespace, YAML validation, secrets detection, ruff format, ruff linting, mypy type checking, and actionlint. Takes ~2-3 minutes on first run (caches environments).

**Unit tests (standalone - will fail):**
```bash
uv run pytest --cov=src --cov-report=xml
```
**NOTE:** Unit tests CANNOT run standalone without Open edX environment. They require Django settings from edx-platform and will fail with "django.core.exceptions.ImproperlyConfigured" or module import errors. See integration tests section below.

### Integration Tests (Required for Testing)

**IMPORTANT:** Tests must be run inside a Tutor/Open edX container with edx-platform installed.

**Setup (one-time):**
```bash
# From host machine
git clone https://github.com/mitodl/open-edx-plugins/
cd open-edx-plugins
uv build --all-packages

# Install Tutor (version depends on Open edX release)
pip install "tutor>=19.0.0,<20.0.0"  # For sumac.master
# OR pip install "tutor>=20.0.0,<21.0.0"  # For teak release
# OR install from main branch for master

# Mount plugin directory
tutor mounts add lms,cms:/path/to/open-edx-plugins:/openedx/open-edx-plugins

# Launch Tutor (takes 10-15 minutes first time)
tutor dev launch -I --skip-build
```

**Run tests:**
```bash
# Access LMS container
tutor dev exec lms bash

# Navigate to mounted plugins
cd /openedx/open-edx-plugins

# Run all tests (takes 5-10 minutes)
./run_edx_integration_tests.sh --skip-build

# Run specific plugin tests
./run_edx_integration_tests.sh --plugin edx_sysadmin --skip-build
```

**Test script flags:**
- `--plugin <name>`: Test only specified plugin (e.g., `edx_sysadmin`)
- `--mount-dir <path>`: Specify different mount directory
- `--skip-build`: Skip UV installation and dependency setup (use after first run)

**Test script behavior:**
- Activates edx-platform's venv
- Installs test dependencies from workspace
- Copies edx-platform test_root to each plugin
- Installs plugin from dist/ or in dev mode
- Runs pytest with coverage using `--ds=settings.test` or `--ds=lms.envs.test`
- Some plugins (ol_openedx_chat, ol_openedx_course_sync) run tests twice with CMS settings
- Isolated plugins (openedx-companion-auth) are uninstalled after testing to avoid interference

## CI/CD Workflows

### GitHub Actions Workflows

**1. CI Workflow (`.github/workflows/ci.yml`)**
- **Triggers:** Push to main, all PRs
- **Matrix:** Python 3.11 × 3 Open edX branches (master, sumac.master, teak)
- **Steps:**
  1. Checkout code
  2. Setup UV with caching
  3. Build all packages with `uv build --all-packages`
  4. Install Tutor (version-specific based on edX branch)
  5. Clone edx-platform and checkout target branch
  6. Build Tutor openedx-dev image (~15-20 minutes)
  7. Launch Tutor (initialize services)
  8. Run integration tests via Docker Compose
  9. Upload coverage to CodeCov
- **Time:** ~30-45 minutes per matrix job
- **Critical:** Must pass all matrix combinations for merge

**2. Test and Build Workflow (`.github/workflows/test-and-build.yml`)**
- **Triggers:** Push to main/develop, PRs to main
- **Jobs:**
  - `test`: Run pytest with coverage (NOTE: Will collect only 1 test and error on 14+ collection failures - this is expected as unit tests need edX environment)
  - `build`: Build all packages, upload artifacts
  - `publish`: Publish to PyPI (only on main branch pushes, requires PYPI_TOKEN secret)
- **Time:** ~5-10 minutes
- **Note:** This workflow's test job shows errors because tests require Open edX environment

### Pre-commit Hooks
All the following run automatically on `git commit` or via `pre-commit run --all-files`:
- trailing-whitespace, end-of-file-fixer, check-yaml, check-toml
- check-added-large-files, check-merge-conflicts, debug-statements
- yamlfmt (format YAML with specific width/indent rules)
- yamllint (lint YAML with relaxed rules)
- detect-secrets (excludes uv.lock)
- ruff-format, ruff linting (with --extend-ignore=D1, --fix)
- mypy type checking (with types-pytz, types-requests, types-python-dateutil, types-setuptools)
- actionlint (GitHub Actions workflow validation)

## Plugin Architecture

**Plugin Entry Points:**
Each plugin registers with Open edX via entry points in `pyproject.toml`:
```toml
[project.entry-points."lms.djangoapp"]
plugin_name = "plugin_name.apps:ConfigClass"

[project.entry-points."cms.djangoapp"]  # If CMS support needed
plugin_name = "plugin_name.apps:ConfigClass"
```

**Common Plugin Components:**
- `apps.py`: Django AppConfig with plugin metadata and ready() hook
- `models.py`: Database models (if needed)
- `views.py` or `api/views.py`: REST API endpoints
- `urls.py`: URL routing
- `settings/`: Plugin-specific settings (production.py, common.py, test.py)
- `conf/`: Configuration templates
- `management/commands/`: Django management commands
- `migrations/`: Database migrations
- `static/`: CSS, JS, images
- `templates/`: Django templates
- `templatetags/`: Custom template tags
- `test_utils/`: Testing utilities

**Plugin Types:**
- Django apps: Standard Open edX plugins (most plugins)
- XBlocks: Course content components (ol_openedx_chat_xblock, rapid_response_xblock)

## Making Changes

**Workflow for code changes:**

1. **Always run linting before committing:**
   ```bash
   uv run ruff format .
   uv run ruff check . --fix
   pre-commit run --all-files
   ```

2. **Test changes:**
   - Build packages: `uv build --all-packages`
   - For edX integration changes, run integration tests in Tutor container
   - Cannot validate with standalone pytest

3. **Version updates:**
   - **CRITICAL:** Update version in `src/<plugin>/pyproject.toml` before merging to main
   - Version follows semantic versioning
   - Publishing to PyPI happens automatically on main branch merge

4. **Common issues:**
   - **Django not configured:** Tests need Open edX environment
   - **Module import errors:** Missing edx-platform dependencies
   - **Isolated plugin test failures:** Some plugins (openedx-companion-auth) modify auth flow and must be tested in isolation

## Validation Checklist

Before submitting changes:
- [ ] Updated plugin version in `src/<plugin>/pyproject.toml` (if applicable)
- [ ] Code formatted: `uv run ruff format .`
- [ ] Linting passes: `uv run ruff check .`
- [ ] Pre-commit hooks pass: `pre-commit run --all-files`
- [ ] Packages build successfully: `uv build --all-packages`
- [ ] Integration tests pass (if modifying plugin logic)
- [ ] Documentation updated (if changing functionality)

## Important Notes

1. **Trust these instructions:** This repository requires specific tooling (UV, Tutor) and workflow. Running standard pytest will fail - always use the integration test script inside Tutor containers.

2. **Test environment dependency:** All plugin tests depend on Open edX's edx-platform being installed and configured. This is why CI uses Tutor.

3. **Plugin isolation:** The `openedx-companion-auth` plugin modifies authentication flow and can break other tests. The test script automatically uninstalls it after testing.

4. **Multiple test runs:** Some plugins (ol_openedx_chat, ol_openedx_course_sync) must be tested with both LMS and CMS Django settings, so tests run twice.

5. **Build artifacts:** The `dist/` directory contains built packages. The test script prefers installing from dist/ over editable installs.

6. **Tutor version matching:** CI matrix tests against multiple Open edX releases, each requiring specific Tutor versions. Match your local Tutor version to the target Open edX release.

7. **First-time setup time:** Building Tutor openedx-dev image takes 15-20 minutes. Plan accordingly.

8. **Search only when needed:** These instructions cover standard workflows. Only search the codebase if you encounter errors not described here or need to understand specific plugin implementation details.
