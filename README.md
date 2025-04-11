# Build and Publish

Ensure you update the version number in `src/<plugin>/pyproject.toml` before any merge to `main`.

A [build and publish pipeline](https://cicd.odl.mit.edu/teams/main/pipelines/publish-open-edx-plugins-pypi) now exists that will automatically build, package, and publish each plugin to PyPI using standard Python build tools (`build` or `uv`). If you're adding a new plugin to this repo be sure to open a PR to update the configuration dictonary located [here](https://github.com/mitodl/ol-infrastructure/blob/main/src/ol_concourse/pipelines/open_edx/open_edx_plugins/build_publish_plugins.py).

To build a package locally (e.g., for testing):
```bash
# Install build tool (if needed)
# python -m pip install build uv
# Navigate to the repository root
cd /path/to/your/repo
# Build the desired package (replace <plugin_dir> with the actual directory)
python -m build src/<plugin_dir>
# Or using uv (if installed)
# uv build src/<plugin_dir>
```
The built wheel and sdist will be placed in `src/<plugin_dir>/dist/`.
