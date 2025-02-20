# Open edX Plugins

This repository contains a collection of Open edX plugins that provide various custom functionalities for the Open edX platform.

## Installation Guide

You can install any plugin from this collection using one of the following methods:

### Option 1A: Install from PyPI (Devstack)

The simplest way to install a plugin in Devstack is directly from PyPI. If you're running devstack in Docker, first open a shell as per requirement and then install the desired plugin using pip:

```bash
# For LMS or CMS installation
make lms-shell  # For LMS
make cms-shell  # For Studio (CMS) installation

pip install <plugin-name>  # Replace `<plugin-name>` with the specific plugin you want to install
```

### Option 1B: Install using Tutor

For Tutor-based Open edX environments, it's recommended to configure plugins as persistent requirements:

1. Add the plugin to Tutor's configuration:
```bash
# For PyPI packages
tutor config save --append OPENEDX_EXTRA_PIP_REQUIREMENTS="<plugin-name>"  # Replace `<plugin-name>` with the specific plugin you want to install

# For GitHub repositories
tutor config save --append OPENEDX_EXTRA_PIP_REQUIREMENTS="git+<github-repository-url>"

# Verify that the requirement has been correctly added
tutor config printvalue OPENEDX_EXTRA_PIP_REQUIREMENTS
```

2. Rebuild the OpenedX image:
```bash
# For development environment
tutor images build openedx-dev

# For production environment
tutor images build openedx
```

3. Restart your Tutor environment:
```bash
# For development environment
tutor dev start

# For production environment
tutor local start
```

Note: While it's possible to install plugins directly inside the Tutor LMS/CMS containers using pip, these changes will not persist after rebuilding the containers. The method above ensures plugins remain installed across container rebuilds.

### Option 2A: Build the package locally and install it (Devstack)

Follow these steps in a terminal on your machine:

1. Navigate to the `open-edx-plugins` directory
2. If you haven't done so already, run ``./pants build``
3. Run ``./pants package ::``. This will create a "dist" directory inside "open-edx-plugins" directory with ".whl" & ".tar.gz" format packages for all plugins

4. Move/copy any of the ".whl" or ".tar.gz" files for this plugin that were generated in the above step to the machine/container running Open edX (NOTE: If running devstack via Docker, you can use ``docker cp`` to copy these files into your LMS or CMS containers)

5. Run a shell in the machine/container running Open edX, and install the plugin using pip

### Option 2B: Local Development with Tutor

For local development and testing with Tutor, you can mount a local directory and install packages directly:

1. Create and mount a source directory:
```bash
# Create src directory (recommended: adjacent to edx-platform)
mkdir src
tutor mounts add lms,cms:/path/to/src:/openedx/src
```

2. Clone and build the plugins:
```bash
cd src
git clone https://github.com/mitodl/open-edx-plugins/
cd open-edx-plugins
pants package :: .
```

3. Rebuild and launch Tutor:
```bash
tutor images build openedx-dev
tutor dev launch --skip-build
```

4. Install the package:
```bash
tutor dev exec lms/cms bash
pip install /openedx/src/open-edx-plugins/dist/[package-filename]
```

Note: The package filename in the dist/ directory will include the package name, version number, and other information (e.g., edx-sysadmin-0.3.0.tar.gz). Make sure to check the dist/ directory for the exact filename before installation.


### Post-Installation Steps

1. After installing any plugin, you may need to restart the edx-platform services to apply the changes
2. Some plugins may require additional configuration - refer to the individual plugin's documentation for specific setup instructions
