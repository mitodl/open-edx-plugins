ol-openedx-chat
###############

An xBlock aside to add MIT Open Learning chat into xBlocks.


Purpose
*******

MIT's AI chatbot for Open edX

Setup
=====

1) Add OL chat as a dependency
------------------------------

For local development, you can use one of the following options to add
this as a dependency in the ``edx-platform`` repo:

-  **Install directly via pip.**

   ::

      # From the devstack directory, run bash in a running LMS container...
      make dev.shell.lms

      # In bash, install the package
      source /edx/app/edxapp/edxapp_env && pip install ol-openedx-chat==<version>

      # Do the same for studio
      make dev.shell.studio

      # In bash, install the package
      source /edx/app/edxapp/edxapp_env && pip install ol-openedx-chat==<version>

-  **Build the package locally and install it**

   ::

      Follow these steps in a terminal on your machine:

      1. Navigate to open-edx-plugins directory

      2. If you haven't done so already, run "pants build"

      3. Run "pants package ::". This will create a "dist" directory inside "open-edx-plugins" directory with ".whl" & ".tar.gz" format packages for "ol_openedx_chat" and other "ol_openedx_*" plugins in "open-edx-plugins/src"

      4. Move/copy any of the ".whl" or ".tar.gz" files for this plugin that were generated in the above step to the machine/container running Open edX (NOTE: If running devstack via Docker, you can use "docker cp" to copy these files into your LMS or CMS containers)

      5. Run a shell in the machine/container running Open edX, and install this plugin using pip

Configuration
=============

1. edx-platform configuration
-----------------------------

   ::


   Add the following configuration values to the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/lms.yml``. These should be added to the top level. **Ask a fellow developer or devops for these values.**

   .. code-block::


   OL_CHAT_SETTINGS: {<MODEL_NAME>: <MODEL_API_KEY>, <MODEL_NAME>: <MODEL_API_KEY>}

2. Add database record
----------------------

- Create a record for the
``XBlockAsidesConfig`` model (LMS admin URL:
``/admin/lms_xblock/xblockasidesconfig/``).

- Create a record in the ``StudioConfig`` model (CMS admin URL:
``/admin/xblock_config/studioconfig/``).


Documentation
=============

License
*******

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see `LICENSE.txt <LICENSE.txt>`_ for details.
