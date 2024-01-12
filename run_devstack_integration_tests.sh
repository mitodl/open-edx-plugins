#!/bin/bash
set -e

source /edx/app/edxapp/venvs/edxapp/bin/activate

cd /edx/app/edxapp/edx-platform
mkdir -p reports

pip install -r ./requirements/edx/testing.txt

pip install -e .

mkdir -p test_root  # for edx
paver update_assets lms --settings=test_static_optimized

cp test_root/staticfiles/lms/webpack-stats.json test_root/staticfiles/webpack-stats.json
cp -r test_root/ /open-edx-plugins/src/edx_sysadmin/test_root
cd /open-edx-plugins

pip install dist/edx-sysadmin-0.3.0.tar.gz

# Install codecov so we can upload code coverage results
pip install codecov

# output the packages which are installed for logging
pip freeze


set +e

pytest src/edx_sysadmin --cov .
PYTEST_SUCCESS=$?

if [[ $PYTEST_SUCCESS -ne 0 ]]
then
    echo "pytest exited with a non-zero status"
    exit $PYTEST_SUCCESS
fi
set -e
coverage xml