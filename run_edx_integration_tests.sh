#!/bin/bash
set -e

source /openedx/venv/bin/activate
ls
pwd

mkdir -p reports

# pip install -r ./requirements/edx/testing.txt

# Installing edx-platform
# pip install -e .

cp -r /openedx/staticfiles test_root/staticfiles

cd /openedx/open-edx-plugins

# Installing test dependencies
pip install pytest-mock==3.14.0
pip install responses==0.25.3

# Plugins that may affect the tests of other plugins.
# e.g. openedx-companion-auth adds a redirect to the authentication
# that fails the authentication process for other plugins.
isolated_plugins=("openedx-companion-auth")

# Install codecov so we can upload code coverage results
pip install codecov

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
    tarball=$(ls dist | grep "$plugin_name" | head -n 1)
    pip install "dist/$tarball"

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
    if [[ "$plugin_dir" == *"ol_openedx_chat"* ]]; then
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

# Main loop to process each plugin
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