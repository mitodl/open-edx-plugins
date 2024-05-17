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

# Loop through each tar.gz file in the dist folder and install them using pip
for file in "dist"/*.tar.gz; do
    pip install "$file"
done

# Install codecov so we can upload code coverage results
pip install codecov

# output the packages which are installed for logging
pip freeze

set +e


set +e
for subdir in "src"/*; do
    if [ -d "$subdir" ]; then
        tests_directory="$subdir/tests"

        # Check if tests directory exists
        if [ -d "$tests_directory" ]; then
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
            cd ../..
        fi
    fi
done
set -e
