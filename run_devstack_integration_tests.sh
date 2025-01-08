#!/bin/bash
set -e

source /openedx/venv/bin/activate
ls
pwd

mkdir -p reports

pip install -r ./requirements/edx/testing.txt

# Installing edx-platform
pip install -e .

cp -r /openedx/staticfiles test_root/staticfiles

cd /open-edx-plugins

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
set +e
for subdir in "src"/*; do
    if [ -d "$subdir" ]; then
        tests_directory="$subdir/tests"

        # Check if tests directory exists
        if [ -d "$tests_directory" ]; then

            # Installing the plugin
            plugin_name=$(basename "$subdir" | sed 's/src\///' | sed 's/_/-/g')
            tarball=$(ls dist | grep "$plugin_name" | head -n 1)
            pip install "dist/$tarball"

            cp -r /openedx/edx-platform/test_root/ "/open-edx-plugins/$subdir/test_root"
            echo "==============Running $subdir tests=================="
            cd "$subdir"

            # Check for the existence of settings/test.py
            if [ -f "settings/test.py" ]; then
                pytest_command="pytest . --cov . --ds=settings.test"
            else
                pytest_command="pytest . --cov . --ds=lms.envs.test"
            fi

            # Run the pytest command
            if $pytest_command --collect-only; then
                $pytest_command
            else
                echo "No tests found, skipping pytest."
            fi

            PYTEST_SUCCESS=$?

            if [[ $PYTEST_SUCCESS -ne 0 ]]
            then
                echo "pytest exited with a non-zero status"
                exit $PYTEST_SUCCESS
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
        fi
    fi
done
set -e
