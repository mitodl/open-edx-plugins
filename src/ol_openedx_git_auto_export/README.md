#### Steps to install on edX platform:


You can install this plugin into any Open edX instance by using any of the following methods:


**Option 1: Install from PyPI**

    # If running devstack in docker, first open a shell in CMS (make studio-shell)

    pip install ol-openedx-git-auto-export


**Option 2: Build the package locally and install it**

Follow these steps in a terminal on your machine:

1. Navigate to ``open-edx-plugins`` directory
2. If you haven't done so already, run ``./pants build``
3. Run ``./pants package ::``. This will create a "dist" directory inside "open-edx-plugins" directory with ".whl" & ".tar.gz" format packages for all the "ol_openedx_*" plugins in "open-edx-plugins/src")
4. Move/copy any of the ".whl" or ".tar.gz" files for this plugin that were generated in the above step to the machine/container running Open edX (NOTE: If running devstack via Docker, you can use ``docker cp`` to copy these files into your LMS container)
5. Run a shell in the machine/container running Open edX, and install this plugin using pip

Configuration
------------
**1) edx-platform configuration**

- Enable the following FEATURES flags in the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/cms.yml``. If using `private.py`, you will need to enable these FEATURES in `cms/envs/private.py`.

  ```
  "FEATURES": {
    "ENABLE_EXPORT_GIT": true,
  }
  ```
- Set your commit user in `cms/envs/common.py`, if you don't want to use the default one
```
GIT_EXPORT_DEFAULT_IDENT = {
    'name': 'STUDIO_EXPORT_TO_GIT',
    'email': 'STUDIO_EXPORT_TO_GIT@example.com'
}
```
- Restart the server using `make studio-restart`

#### Setup github authentication for plugin:
 If you're testing from a docker machine running devstack setup github authentictaion for plugin, you'll need to generate SSH keys in that
machine and add them to your Github account
(https://help.github.com/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent/ -
https://help.github.com/articles/adding-a-new-ssh-key-to-your-github-account)

#### Studio/CMS UI settings
- Open studio then course and go to advance settings.
- Choose field GIT URL and add you OLX git repo. For example `https://github.com/amir-qayyum-khan/test_edx_course.git`.
- Make a change to the course content and publish.
- Test commit count increase on your OLX repo.
