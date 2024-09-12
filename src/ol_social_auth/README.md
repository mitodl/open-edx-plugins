
social-auth-mitxpro
---


#### Prerequisites

- [`pyenv`](https://github.com/pyenv/pyenv#installation) for managing python versions
  - Install `python3.8` and `python3.11`
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

You can just run `tox` locally to test, lint, and check formatting in the supported python versions. This works by having `tox` manage the virtualenvs, which `poetry` then detects and uses.

Run individual commands can be run interactively in a `poetry shell` session or directly via `poetry run CMD`:

- `pytest` - run python tests
- `ruff check` - lint python code
- `ruff format` - format python code

#### Building

- `poetry build` - builds a pip-installable package into `dist/`

#### Releasing

- `poetry version VERSION` - bump the project version (see `poetry version --help` for details)
- `poetry publish -r testpypi` - publish to testpypi
- `poetry publish` - publish to pypi
