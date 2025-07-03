#!/bin/bash
set -e

source /openedx/venv/bin/activate
ls
pwd

mkdir -p reports

if [ $CI ]; then
  pip install -r ./requirements/edx/testing.txt

  # Installing edx-platform
  pip install -e .
fi

cp -r /openedx/staticfiles test_root/staticfiles

cd /openedx/open-edx-plugins

# Installing test dependencies using UV (this includes pytest-mock, responses, codecov, etc.)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
uv sync --dev

# Plugins that may affect the tests of other plugins.
# e.g. openedx-companion-auth adds a redirect to the authentication
# that fails the authentication process for other plugins.
isolated_plugins=("openedx-companion-auth")

# output the packages which are installed for logging
pip freeze

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

    cp -r /openedx/edx-platform/test_root/ "/openedx/open-edx-plugins/$plugin_dir/test_root"
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
plugin="$1"

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
