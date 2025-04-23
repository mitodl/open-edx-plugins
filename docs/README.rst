Open edX Plugins
================

This repository contains a collection of Open edX plugins that provide various custom functionalities for the Open edX platform.

Installation Guide
------------------

You can install any plugin from this collection using one of the following methods:

Tutor
~~~~~

- Option 1: Install from PyPI

  For Tutor-based Open edX environments, it's recommended to configure plugins as persistent requirements:

  1. Add the plugin to Tutor's configuration using the following command:
      .. code-block:: bash

        tutor config save --append OPENEDX_EXTRA_PIP_REQUIREMENTS="<plugin-name>"  # Replace `<plugin-name>` with the specific plugin you want to install

      **Verify** that the requirement has been correctly added

      .. code-block:: bash

        tutor config printvalue OPENEDX_EXTRA_PIP_REQUIREMENTS

  2. Rebuild the OpenedX image using one of the following commands:
      - **For development environment**

        .. code-block:: bash

          tutor images build openedx-dev

      - **For production environment**

        .. code-block:: bash

          tutor images build openedx

  3. Restart your Tutor environment using one of the following commands:
      - **For development environment**

        .. code-block:: bash

          tutor dev start

      - **For production environment**

        .. code-block:: bash

          tutor local start

  Note: While it's possible to install plugins directly inside the Tutor LMS/CMS containers using pip, these changes will not persist after rebuilding the containers. The method above ensures plugins remain installed across container rebuilds.

- Option 2: Local Development

  For local development and testing with Tutor, you can mount a local directory and install packages directly:

  1. Clone, mount and build the plugins:

     .. code-block:: bash

        git clone https://github.com/mitodl/open-edx-plugins/
        tutor mounts add lms,cms:/path/to/open-edx-plugins:/openedx/open-edx-plugins
        cd open-edx-plugins
        pants package ::

  2. Install the package:

     .. code-block:: bash

        tutor dev exec <lms or cms> bash
        pip install /openedx/open-edx-plugins/dist/[package-filename]

  **Note:** The package filename in the dist/ directory will include the plugin name, version number, and other information (e.g., edx-sysadmin-0.3.0.tar.gz). Make sure to check the dist/ directory for the exact filename before installation.

Post-Installation Steps
~~~~~~~~~~~~~~~~~~~~~~~

1. After installing any plugin, you may need to restart the edx-platform services to apply the changes. You can restart lms/cms by running run ``tutor dev restart <lms or cms>``
2. Some plugins may require additional configuration - refer to the individual plugin's documentation for specific setup instructions


Testing Guide
-------------

Running Integration tests
~~~~~~~~~~~~~~~~~~~~~~~~~

**Note:** If you have followed the above installation steps, your local ``open-edx-plugins`` clone
should be mounted at ``/openedx/open-edx-plugins`` in both `LMS` and `CMS` containers. This path is used to run the
tests script in the below commands. If you have mounted ``open-edx-plugins`` at a different path,
please update the path in ``run_edx_integration_tests.sh``.

1. Access the container:

   .. code-block:: bash

      tutor dev exec lms/cms bash

2. Run the tests:

   - For all plugins:

     .. code-block:: bash

       /openedx/open-edx-plugins/run_edx_integration_tests.sh

   - For a specific plugin:

     .. code-block:: bash

       /openedx/open-edx-plugins/run_edx_integration_tests.sh <plugin-name>

The script generates coverage reports in XML format and exits with a non-zero status if any tests fail.
