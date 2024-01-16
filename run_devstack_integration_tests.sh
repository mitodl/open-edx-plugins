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
cp -r test_root/ /open-edx-plugins/src/edx_sysadmin/test_root

cd /open-edx-plugins

pip install dist/edx-sysadmin-0.3.0.tar.gz
pip install dist/ol-openedx-canvas-integration-0.3.0.tar.gz
pip install dist/ol-openedx-checkout-external-0.1.3.tar.gz
pip install dist/ol-openedx-course-export-0.1.2.tar.gz
pip install dist/ol-openedx-course-structure-api-0.1.3.tar.gz
pip install dist/ol-openedx-git-auto-export-0.3.1.tar.gz
pip install dist/ol-openedx-logging-0.1.0.tar.gz
pip install dist/ol-openedx-rapid-response-reports-0.3.0.tar.gz
pip install dist/ol-openedx-sentry-0.1.2.tar.gz

# Install codecov so we can upload code coverage results
pip install codecov

# output the packages which are installed for logging
pip freeze

set +e

echo "Running pycodestyle"
pycodestyle open_edx-plugins tests
PYCODESTYLE_SUCCESS=$?

echo "Running pylint"
(cd /edx/app/edxapp/edx-platform; pylint /open-edx-plugins/src)
PYLINT_SUCCESS=$?

if [[ $PYCODESTYLE_SUCCESS -ne 0 ]]
then
    echo "pycodestyle exited with a non-zero status"
    exit $PYCODESTYLE_SUCCESS
fi
if [[ $PYLINT_SUCCESS -ne 0 ]]
then
    echo "pylint exited with a non-zero status"
    exit $PYLINT_SUCCESS
fi

echo ==============Running edx_sysadmin test===================
cd src/edx_sysadmin
pytest . --cov .
PYTEST_SUCCESS=$?

if [[ $PYTEST_SUCCESS -ne 0 ]]
then
    echo "pytest exited with a non-zero status"
    exit $PYTEST_SUCCESS
fi
set -e
coverage xml
cd ../..
