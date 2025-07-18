#!/bin/bash
set -e

# Default values
PLUGIN_NAME=""
MOUNT_DIR=""

# Parse named arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --plugin)
      PLUGIN_NAME="$2"
      shift # past argument
      shift # past value
      ;;
    --mount-dir)
      MOUNT_DIR="$2"
      shift
      shift
      ;;
    *)    # unknown option
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

echo "Running edx integration tests with the following parameters:"

if [ -n "$PLUGIN_NAME" ]; then
  echo "PLUGIN_NAME: $PLUGIN_NAME"
else
  echo "PLUGIN_NAME: (Running tests for ALL plugins)"
fi

# Remove trailing slash if present (but not if it's just "/")
if [ -n "$MOUNT_DIR" ] && [ "$MOUNT_DIR" != "/" ]; then
  MOUNT_DIR="${MOUNT_DIR%/}"
fi

if [ -n "$MOUNT_DIR" ]; then
  echo "MOUNT_DIR: $MOUNT_DIR"
else
  echo "MOUNT_DIR: (Using current working directory: $(pwd))"
fi
echo "=========================================="

source /openedx/venv/bin/activate
ls
pwd

mkdir -p reports

if [ $CI ]; then
  pip install -r ./requirements/edx/testing.txt

  # Installing edx-platform
  pip install -e .
fi

echo "Copying static files in edx-platform test_root if it doesn't exist"

if [ ! -d "/openedx/edx-platform/test_root/staticfiles" ]; then
  cp -r /openedx/staticfiles /openedx/edx-platform/test_root/staticfiles
fi

if [ -n "$MOUNT_DIR" ]; then
  echo "Switching to mount directory: $MOUNT_DIR"
  cd "$MOUNT_DIR" || { echo "Failed to cd into $MOUNT_DIR"; exit 1; }
fi


# Installing test dependencies using UV (this includes pytest-mock, responses, codecov, etc.)
echo "===== Installing uv ====="
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
echo "===== Installing Packages ====="
uv export --only-dev --no-hashes --no-annotate > ol_test_requirements.txt
pip install -r ol_test_requirements.txt
# Plugins that may affect the tests of other plugins.
# e.g. openedx-companion-auth adds a redirect to the authentication
# that fails the authentication process for other plugins.
isolated_plugins=("openedx-companion-auth")

# output the packages which are installed for logging
echo "===== Installed Python Packages ====="
pip freeze | sort
echo "====================================="

export EDXAPP_TEST_MONGO_HOST=mongodb

# Function to run tests for a plugin
run_plugin_tests() {

    local plugin_dir="$1"
    local tests_directory="$plugin_dir/tests"

    # Check if tests directory exists
    if [ ! -d "$tests_directory" ]; then
        return 0
    fi

    # Installing the plugin
    plugin_name=$(basename "$plugin_dir" | sed 's/src\///' | sed 's/_/-/g')

    # Check if we have a built wheel/tarball for the plugin
    # Try both underscore and hyphen versions of the name
    plugin_name_underscore=$(basename "$plugin_dir" | sed 's/src\///')

    tarball=""
    # Look for wheel first, then tarball
    for ext in "whl" "tar.gz"; do
        for name_variant in "$plugin_name" "$plugin_name_underscore"; do
            found_file=$(ls dist 2>/dev/null | grep -E "^${name_variant}-.*\.${ext}$" | head -n 1)
            if [ -n "$found_file" ]; then
                tarball="$found_file"
                break 2
            fi
        done
    done

    if [ -n "$tarball" ]; then
        echo "Installing $plugin_name from dist/$tarball"
        pip install "dist/$tarball"
    else
        echo "No built package found for $plugin_name, installing in development mode"
        pip install -e "$plugin_dir"
    fi

    # Copying test_root only if it doesn't exist

    if [ -n "$MOUNT_DIR" ]; then
        DEST="$MOUNT_DIR/$plugin_dir/test_root"
    else
        DEST="$plugin_dir/test_root"
    fi

    if [ ! -d "$DEST" ]; then
        echo "Copying test_root to $DEST"
        cp -r /openedx/edx-platform/test_root/ "$DEST"
    else
        echo "test_root already exists at $DEST, skipping copy."
    fi
    echo "==============Running $plugin_dir tests=================="
    cd "$plugin_dir"

    # Check for the existence of settings/test.py
    if [ -f "settings/test.py" ]; then
        pytest_command="pytest . --cov . --ds=settings.test"
    else
        pytest_command="pytest . --cov . --ds=lms.envs.test"
    fi

    # Run the pytest command
    local PYTEST_SUCCESS=0
    if $pytest_command --collect-only; then
        $pytest_command
        PYTEST_SUCCESS=$?
    else
        echo "No tests found, skipping pytest."
    fi

    if [[ $PYTEST_SUCCESS -ne 0 ]]
    then
        echo "pytest exited with a non-zero status"
        exit $PYTEST_SUCCESS
    fi

    # Run the pytest command with CMS settings (for ol_openedx_chat)
    if [[ "$plugin_dir" == *"ol_openedx_chat"* || "$plugin_dir" == *"ol_openedx_course_sync"* ]]; then
        pytest . --cov . --ds=cms.envs.test

        PYTEST_SUCCESS=$?
        if [[ $PYTEST_SUCCESS -ne 0 ]]
        then
            echo "pytest exited with a non-zero status"
            exit $PYTEST_SUCCESS
        fi
    fi

    coverage xml

    # Check if the plugin name is in the isolated_plugins list and uninstall it
    for plugin in "${isolated_plugins[@]}"; do
        if [[ "$plugin_name" == "$plugin" ]]; then
            pip uninstall -y "$plugin_name"
            break
        fi
    done
    cd ../..
}

# Check if a specific plugin name was provided
plugin="$PLUGIN_NAME"

set +e
if [ -n "$plugin" ]; then
    # Run tests only for the specified plugin
    plugin_dir="src/$plugin"
    if [ -d "$plugin_dir" ]; then
        echo "Running tests for specified plugin: $plugin"
        run_plugin_tests "$plugin_dir"
    else
        echo "Error: Plugin directory '$plugin_dir' not found."
        exit 1
    fi
else
    # Run tests for all plugins
    echo "Running tests for all plugins"
    for subdir in "src"/*; do
        if [ -d "$subdir" ]; then
            run_plugin_tests "$subdir"
        fi
    done
fi
set -e
