#### Steps to install on edX platform:


You can install this plugin into any Open edX instance by using any of the following methods:


**Option 1: Install from PyPI**

.. code-block::

    # If running devstack in docker, first open a shell in LMS (make lms-shell)

    pip install ol-openedx-git-auto-export


**Option 2: Build the package locally and install it**

Follow these steps in a terminal on your machine:

1. Navigate to ``open-edx-plugins`` directory
2. If you haven't done so already, run ``./pants build``
3. Run ``./pants package ::``. This will create a "dist" directory inside "open-edx-plugins" directory with ".whl" & ".tar.gz" format packages for all the "ol_openedx_*" plugins in "open-edx-plugins/src")
4. Move/copy any of the ".whl" or ".tar.gz" files for this plugin that were generated in the above step to the machine/container running Open edX (NOTE: If running devstack via Docker, you can use ``docker cp`` to copy these files into your LMS container)
5. Run a shell in the machine/container running Open edX, and install this plugin using pip


- open cms.env and lms.env or private.py and set FEATURES flags

  ```
  "FEATURES": {
    "ENABLE_EXPORT_GIT": true,
    "ENABLE_GIT_AUTO_EXPORT": true
  }
  ```
- Update cms/envs/common. Append **INSTALLED_APPS**
    ```
    # git auto export
    'git_auto_export',
    ```
- Now run to install `pip install ol-openedx-git-auto-export.whl`. So it means just install the whl file created using pants build.
- Run server `make dev.up` or restart the server

#### If using vagrant or local env:
 If you're testing from a vagrant machine running devstack, you'll need to generate SSH keys in that
machine and add them to your Github account
(https://help.github.com/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent/ -
https://help.github.com/articles/adding-a-new-ssh-key-to-your-github-account)

#### Studio/CMS UI settings
- Open studio then course and go to advance settings.
- Choose field GIT URL and add you OLX git repo. For example `https://github.com/amir-qayyum-khan/test_edx_course.git`.
- Make a change to the course content and publish.
- Test commit count increase on your OLX repo.
