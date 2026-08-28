Open edX Plugins
================

This repository contains a collection of Open edX plugins that provide various custom functionalities for the Open edX platform.

Open edX Release Compatibility
-------------------------------

In August 2026 this repository raised its Django dependency floor from
``Django>=4.0`` to ``Django>=5.2`` across every plugin, to match the
``Ulmo`` (Django 5.2.11) and ``Verawood`` (Django 5.2.13) Open edX releases.
Installing a plugin version below its listed minimum on Ulmo/Verawood (or
``master``) - or above its listed maximum on Teak and earlier - can pull in
a Django release the target edx-platform doesn't support.

Individual plugins may have additional, feature-specific compatibility notes
in their own ``README.rst`` (see each plugin's ``Version Compatibility``
section) - the table below only tracks the Django 5.2 floor.

========================================  ========================================  ===================================
Plugin                                    Max version for Teak and earlier          Min version for Ulmo / Verawood+
========================================  ========================================  ===================================
edx-sysadmin                              0.4.2                                     0.5.0
edx-username-changer                      0.5.0                                     0.6.0
ol-openedx-ai-static-translations         0.1.1                                     0.2.0
ol-openedx-auto-select-language           0.1.2                                     0.2.0
ol-openedx-canvas-integration             0.8.2                                     0.9.0
ol-openedx-chat                           0.5.10                                    0.6.0
ol-openedx-chat-xblock                    0.4.6                                     0.5.0
ol-openedx-checkout-external              0.2.0                                     0.3.0
ol-openedx-course-export                  0.2.0                                     0.3.0
ol-openedx-course-outline-api             0.1.0                                     0.2.0
ol-openedx-course-structure-api           0.2.0                                     0.3.0
ol-openedx-course-sync                    1.0.1                                     1.1.0
ol-openedx-course-translations            0.8.0                                     0.9.0
ol-openedx-events-handler                 0.2.1                                     0.4.0
ol-openedx-feedback                       0.2.0                                     0.3.0
ol-openedx-git-auto-export                0.8.3                                     0.9.0
ol-openedx-logging                        0.3.5                                     0.4.0
ol-openedx-lti-utilities                  0.1.2                                     0.2.0
ol-openedx-otel-monitoring                0.2.0                                     0.3.0
ol-openedx-rapid-response-reports         0.5.1                                     0.6.0
ol-openedx-sentry                         0.4.0                                     0.5.0
ol-openedx-uai-content-customization      0.3.0                                     0.4.0
ol-social-auth                            0.2.2                                     0.3.0
openedx-companion-auth                    1.2.0                                     1.3.0
rapid-response-xblock                     0.11.0                                    0.12.0
========================================  ========================================  ===================================

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
        uv build --all-packages

  2. Install the package:

     .. code-block:: bash

        tutor dev exec <lms or cms> bash
        pip install /openedx/open-edx-plugins/dist/[package-filename]
        OR
        pip install /openedx/open-edx-plugins/src/<package> # replace <package> with the specific plugin directory


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

2. Navigate to the plugins directory:

   .. code-block:: bash

      cd <mount_path_to_open-edx-plugins e.g, /openedx/open-edx-plugins>

3. Run the tests:

   - For all plugins:

     .. code-block:: bash

       ./run_edx_integration_tests.sh --skip-build

   - For a specific plugin:

     .. code-block:: bash

       ./run_edx_integration_tests.sh --plugin <plugin_name e.g, edx_sysadmin> --skip-build

Script Flags
~~~~~~~~~~~~

The test script supports the following optional flags:

- ``--plugin``: Specify the plugin directory (e.g., ``edx_sysadmin``) to run tests for a single plugin. If omitted, tests for **all plugins** will be run.
- ``--mount-dir``: Use this if you're running the script from a different directory than the ``open-edx-plugins``.
- ``--skip-build``: Skips the build step, which includes installing test dependencies and the UV tool. You can use this flag if dependencies have already been installed and you want to run tests directly.

The script generates coverage reports in XML format and exits with a non-zero status if any tests fail.
