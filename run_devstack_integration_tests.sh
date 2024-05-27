#!/bin/bash
set -e

source /edx/app/edxapp/venvs/edxapp/bin/activate

cd /edx/app/edxapp/edx-platform
mkdir -p reports

pip install -r ./requirements/edx/testing.txt
pip install -r ./requirements/edx/paver.txt

mkdir -p test_root  # for edx
paver update_assets lms --settings=test_static_optimized

cp test_root/staticfiles/lms/webpack-stats.json test_root/staticfiles/webpack-stats.json

cd /open-edx-plugins

# Installing dev dependencies
pip install poetry
poetry install --no-interaction --only dev

# Function to install or uninstall the plugin based on the subdirectory name and action
manage_plugin() {
    subdir=$1
    action=$2
    plugin_name=$(basename "$subdir" | sed 's/src\///' | sed 's/_/-/g')

    tarball=$(ls dist | grep "$plugin_name" | head -n 1)

    if [[ $action == "install" ]]; then
        if [[ -n $tarball ]]; then
            pip install "dist/$tarball"
        else
            echo "No matching tarball found for $plugin_name"
            exit 1
        fi
    elif [[ $action == "uninstall" ]]; then
        if [[ -n $plugin_name ]]; then
            pip uninstall -y "$plugin_name"
        else
            echo "No plugin name found for $subdir"
            exit 1
        fi
    else
        echo "Invalid action: $action"
        exit 1
    fi
}

# Install codecov so we can upload code coverage results
pip install codecov

# output the packages which are installed for logging
pip freeze

set +e
for subdir in "src"/*; do
    if [ -d "$subdir" ]; then
        tests_directory="$subdir/tests"

        # Check if tests directory exists
        if [ -d "$tests_directory" ]; then
            # Install the plugin from the subdirectory
            manage_plugin "$subdir" "install"

            cp -r /edx/app/edxapp/edx-platform/test_root/ "/open-edx-plugins/$subdir/test_root"
            echo "==============Running $subdir test==================="
            cd "$subdir"

            # Check for the existence of settings/test.py
            if [ -f "settings/test.py" ]; then
                pytest_command="pytest . --cov . --ds=settings.test"
            else
                pytest_command="pytest . --cov ."
            fi

            # Run the pytest command
            $pytest_command

            PYTEST_SUCCESS=$?

            if [[ $PYTEST_SUCCESS -ne 0 ]]
            then
                echo "pytest exited with a non-zero status"
                exit $PYTEST_SUCCESS
            fi
            coverage xml

            # Uninstall the plugin after the test run
            manage_plugin "$subdir" "uninstall"

            cd ../..
        fi
    fi
done
set -e
