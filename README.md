# Important

Ensure you update the version number in `src/<plugin>/pyproject.toml` before any merge to `main`.

# Build and Publish

A [build and publish pipeline](https://cicd.odl.mit.edu/teams/main/pipelines/publish-open-edx-plugins-pypi) now exists that will automatically build, package, and publish each plugin to PyPI. The [pipeline definition](https://github.com/mitodl/ol-infrastructure/blob/main/src/ol_concourse/pipelines/open_edx/open_edx_plugins/build_publish_plugins.py) discovers plugins from `src/*/pyproject.toml`, so a new plugin needs no infrastructure code change: regenerate the definition from an updated checkout of this repo and re-apply it with `fly set-pipeline`.


# Instructions to install and test the plugins:

See [this guide](./docs/README.rst) for a step-by-step walkthrough.
