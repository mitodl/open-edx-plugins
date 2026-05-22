Git Auto Export Plugin
######################

Installation
============

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* Studio (CMS)

Configuration
=============

- Enable the following FEATURES flags in the config file in Open edX. For any release after Juniper, that config file is ``/edx/etc/cms.yml``. If you're using ``private.py``, you will need to enable these FEATURES in ``cms/envs/private.py``.

  .. code-block::

    "FEATURES": {
        "ENABLE_EXPORT_GIT": true,
        "ENABLE_AUTO_GITHUB_REPO_CREATION": true  # Optional, to auto create github repo for new courses
    }
    # Set when ENABLE_AUTO_GITHUB_REPO_CREATION is true
    GITHUB_ORG_API_URL = "https://api.github.com/orgs/<GITHUB_ORG_NAME>"  # For GitHub Enterprise, change the URL accordingly
    GITHUB_ACCESS_TOKEN = "<GITHUB_PERSONAL_ACCESS_TOKEN>"  # Token must have 'repo - Full control of private repositories' permission


- Set your commit user in ``cms/envs/common.py``, if you don't want to use the default one

  .. code-block::

    GIT_EXPORT_DEFAULT_IDENT = {
        'name': 'STUDIO_EXPORT_TO_GIT',
        'email': 'STUDIO_EXPORT_TO_GIT@example.com'
    }

- Restart the server using ``make studio-restart`` on Devstack or ``tutor dev/local restart openedx`` on Tutor.
- For Tutor installations, these values can also be managed through a `custom tutor plugin <https://docs.tutor.edly.io/tutorials/plugin.html#plugin-development-tutorial>`_.

Setup github authentication for plugin
---------------------------------------
If you're testing from a docker machine running devstack setup github authentication for plugin, you'll need to generate SSH keys in that
machine and add them to your Github account
(https://help.github.com/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent/ -
https://help.github.com/articles/adding-a-new-ssh-key-to-your-github-account)

Studio/CMS UI settings
----------------------
- Open studio admin  at ``/admin/ol_openedx_git_auto_export/contentgitrepository/``
- Add your course_id and in the GIT URL, add your OLX git repo. For example ``git@github.com:<GITHUB_USERNAME>/edx4edxlite.git``.
- Make a change to the course content and publish.
   - When using Tutor, attach with the CMS container using ``tutor dev/local start cms`` and enter ``yes`` to the prompt to add the GitHub to known hosts.
   - You should see a new commit in your OLX repo.
   - Commit user should be the one that published the change.
   - If user is not available, it should be the default one set in ``GIT_EXPORT_DEFAULT_IDENT``.
- Test commit count increase on your OLX repo.
Library Support
===============

This plugin supports automatic git export for both **courses** and **content libraries**.

Library v1 (Legacy Libraries)
------------------------------

**Library Key Format:** ``library-v1:org+library``

**Supported Operations:**

- ✅ **Auto-export on update**: When you update/publish a library v1, changes are automatically exported to git
- ✅ **Auto-repo creation**: Library v1 does NOT have a creation signal in Open edX, so the GitHub repository is automatically created on the first library update signal

**Setup for Library v1:**

1. Enable the library feature flags in your config:

   .. code-block::

     "FEATURES": {
         "ENABLE_GIT_AUTO_LIBRARY_EXPORT": true,
         "ENABLE_AUTO_GITHUB_LIBRARY_REPO_CREATION": true
     }

2. Make changes to your library and publish

Library v2 (Content Libraries)
-------------------------------

**Library Key Format:** ``lib:org:slug``

**Supported Operations:**

- ✅ **Auto-export on update**: When you update a library v2, changes are automatically exported to git
- ✅ **Auto-repo creation**: When you create a new library v2, a GitHub repository can be automatically created

**Setup for Library v2:**

1. Enable the library feature flags in your config:

   .. code-block::

     "FEATURES": {
         "ENABLE_GIT_AUTO_LIBRARY_EXPORT": true,
         "ENABLE_AUTO_GITHUB_LIBRARY_REPO_CREATION": true
     }

2. When creating a new library v2, if ``ENABLE_AUTO_GITHUB_LIBRARY_REPO_CREATION`` is enabled, a GitHub repository will be created automatically
3. Updates to the library will be automatically exported to git

**Important Notes:**

- Library v1 does not emit a creation signal, so the GitHub repository is automatically created on the first library update
- Library v2 uses the new event architecture and supports both creation and update signals for immediate repository creation
- Both library types support automatic git export on updates once configured
