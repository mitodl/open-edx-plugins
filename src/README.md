# Open edX Plugins

This repository contains a collection of Open edX plugins that provide various custom functionalities for the Open edX platform.

## Installation Guide

You can install any plugin from this collection using one of the following methods:

### Option 1: Install from PyPI

The simplest way to install a plugin is directly from PyPI. If you're running devstack in Docker, first open a shell in LMS:

```bash
make lms-shell
```

Then install the desired plugin using pip:

```bash
pip install <plugin-name>
```

Replace `<plugin-name>` with the specific plugin you want to install. For version-specific installation, use [plugin-name]==<version>.

### Option 2: Build the package locally and install it

Follow these steps in a terminal on your machine:

1. Navigate to the `open-edx-plugins` directory
2. If you haven't done so already, run ``./pants build``
3. Run ``./pants package ::``. This will create a "dist" directory inside "open-edx-plugins" directory with ".whl" & ".tar.gz" format packages for all plugins

4. Move/copy any of the ".whl" or ".tar.gz" files for this plugin that were generated in the above step to the machine/container running Open edX (NOTE: If running devstack via Docker, you can use ``docker cp`` to copy these files into your LMS or CMS containers)

5. Run a shell in the machine/container running Open edX, and install the plugin using pip

### Post-Installation Steps

1. After installing any plugin, you may need to restart the edx-platform services to apply the changes
2. Some plugins may require additional configuration - refer to the individual plugin's documentation for specific setup instructions
