# Configuration Guide: Feature Flags

This document describes the available feature flags for controlling git auto-export behavior for courses and libraries.

## Feature Flags Overview

### Course-Specific Flags

#### `ENABLE_GIT_AUTO_EXPORT`
- **Type**: Boolean
- **Default**: `False`
- **Purpose**: Controls automatic git export for courses when they are published
- **Scope**: Courses only (unless library flag not set, see below)
- **Location**: `settings.FEATURES['ENABLE_GIT_AUTO_EXPORT']`

**Example**:
```python
FEATURES['ENABLE_GIT_AUTO_EXPORT'] = True
```

#### `ENABLE_AUTO_GITHUB_REPO_CREATION`
- **Type**: Boolean
- **Default**: `False`
- **Purpose**: Controls automatic GitHub repository creation for new courses
- **Scope**: Courses only (unless library flag not set, see below)
- **Location**: `settings.FEATURES['ENABLE_AUTO_GITHUB_REPO_CREATION']`

**Example**:
```python
FEATURES['ENABLE_AUTO_GITHUB_REPO_CREATION'] = True
```

### Library-Specific Flags

#### `ENABLE_GIT_AUTO_LIBRARY_EXPORT`
- **Type**: Boolean
- **Default**: False
- **Purpose**: Controls automatic git export for libraries when they are updated
- **Scope**: Libraries only
- **Location**: `settings.FEATURES['ENABLE_GIT_AUTO_LIBRARY_EXPORT']`

**Example**:
```python
# Enable library export separately from courses
FEATURES['ENABLE_GIT_AUTO_LIBRARY_EXPORT'] = True

# Or disable library export while keeping course export enabled
FEATURES['ENABLE_GIT_AUTO_EXPORT'] = True
FEATURES['ENABLE_GIT_AUTO_LIBRARY_EXPORT'] = False
```

#### `ENABLE_AUTO_GITHUB_LIBRARY_REPO_CREATION`
- **Type**: Boolean
- **Default**: False
- **Purpose**: Controls automatic GitHub repository creation for new libraries
- **Scope**: Libraries only
- **Location**: `settings.FEATURES['ENABLE_AUTO_GITHUB_LIBRARY_REPO_CREATION']`

**Example**:
```python
# Enable library repo creation separately from courses
FEATURES['ENABLE_AUTO_GITHUB_LIBRARY_REPO_CREATION'] = True

# Or disable library repo creation while keeping course repo creation enabled
FEATURES['ENABLE_AUTO_GITHUB_REPO_CREATION'] = True
FEATURES['ENABLE_AUTO_GITHUB_LIBRARY_REPO_CREATION'] = False
```

### Required Settings (for both courses and libraries)

#### `ENABLE_EXPORT_GIT`
- **Type**: Boolean
- **Purpose**: Master switch for git export functionality
- **Note**: Must be enabled for any git export to work
- **Location**: `settings.FEATURES['ENABLE_EXPORT_GIT']`

#### `GITHUB_ORG_API_URL`
- **Type**: String (URL)
- **Purpose**: GitHub organization API URL for creating repositories
- **Example**: `https://api.github.com/orgs/your-org`
- **Location**: `settings.GITHUB_ORG_API_URL`

#### `GITHUB_ACCESS_TOKEN`
- **Type**: String (Token)
- **Purpose**: GitHub personal access token with repo creation permissions
- **Location**: `settings.GITHUB_ACCESS_TOKEN`
- **Security**: Should be stored securely (e.g., environment variable, secrets management)

#### `GIT_REPO_EXPORT_DIR`
- **Type**: String (Path)
- **Purpose**: Directory path for git export operations
- **Default**: `/openedx/export_course_repos`
- **Location**: `settings.GIT_REPO_EXPORT_DIR`

## Security Considerations

- **Never commit `GITHUB_ACCESS_TOKEN` to version control**
- Use environment variables or secrets management
- Ensure GitHub token has minimum required permissions:
  - `repo` scope for repository creation
  - `write:org` if creating repos in an organization
- Rotate tokens regularly
- Use different tokens for different environments (dev/staging/prod)
