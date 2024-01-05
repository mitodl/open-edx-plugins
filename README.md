# Important

Ensure you update the version number in `src/<plugin>/BUILD` before any merge to `main`.

# Build and Publish

A [build and publish pipeline](https://cicd.odl.mit.edu/teams/main/pipelines/publish-open-edx-plugins-pypi) now exists that will automatically build, package, and publish each plugin to PyPI. If you're adding a new plugin to this repo be sure to open a PR to update the configuration dictonary located [here](https://github.com/mitodl/ol-infrastructure/blob/main/src/ol_concourse/pipelines/open_edx/open_edx_plugins/build_publish_plugins.py).
