
MIT xPro Open edX Extensions
---


#### Prerequisites

- [`pyenv`](https://github.com/pyenv/pyenv#installation) for managing python versions
  - Install `python3.6` and `python2.7`
- `pip install tox tox-pyenv` for running tests and discovering python versions from `pyenv`
- [`poetry`](https://poetry.eustace.io/docs/#installation) for building, testing, and releasing

If this is your first time using `poetry`, you'll need to configure your pypi credentials via:
- Configure pypi repository:
  - `poetry config http-basic.pypi USERNAME PASSWORD`
- Configure testpypi repository:
  - `poetry config repositories.testpypi https://test.pypi.org/legacy`
  - `poetry config http-basic.testpypi USERNAME PASSWORD`

**NOTE:** when running `poetry` commands, particularly `pylint` and `black`, you must `python3.6`

#### Testing

You can just run `tox` locally to test, lint, and check formatting in the supported python versions. This works by having `tox` manage the virtualenvs, which `poetry` then detects and uses. Note that some of the tools (e.g. `pylint`, `black`) only support running in `python3.6` and this is reflected in `tox.ini`.

Run individual commands can be run interactively in a `poetry shell` session or directly via `poetry run CMD`:

- `pytest` - run python tests
- `pylint` - lint python code
- `black .` - format python code

#### Building

- `poetry build` - builds a pip-installable package into `dist/`


#### Installing

All that is required to install this in either a hosted version of Open edX or devstack is a `pip install` either from pypi or the output of `poetry build`.


#### Configuring

These extensions can be configured via settings in `lms.env.json`, they are all defined in [`mitxpro_core/settings/production.py`](mitxpro_core/settings/production.py)


#### Releasing

- `poetry version VERSION` - bump the project version (see `poetry version --help` for details)
- `poetry publish -r testpypi` - publish to testpypi
- `poetry publish` - publish to pypi
