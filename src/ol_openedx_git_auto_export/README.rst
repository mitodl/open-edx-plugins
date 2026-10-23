Git Auto Export Plugin
######################

Version Compatibility
======================

For this plugin's compatibility with Open edX, see the
`Open edX Release Compatibility table <../../docs#open-edx-release-compatibility>`_.

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

- Optionally route export tasks to their own Celery queue. Exports take tens of
  seconds, so on the default queue they hold up Studio's short publish tasks.
  Unset, exports use edx-platform's default routing. A worker must consume the
  queue, or exports wait there indefinitely. Repository creation stays on the
  default queue.

  .. code-block::

    GIT_AUTO_EXPORT_CELERY_QUEUE: "edx.cms.core.git_export"

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

Re-exporting Without a Publish
==============================

Courses are exported only when published and libraries only when updated, so
content whose export failed stays stale in git until its next change. A failed
export fails its Celery task, so it shows in task metrics; it is not retried.
To queue an export on demand, fix whatever made the export fail, then use
either:

- The ``Export selected content to git`` action on the Content Git Repositories
  page in Django admin.
- The ``export_to_git`` management command:

  .. code-block::

    # Specific courses or libraries
    ./manage.py cms export_to_git --content-keys course-v1:MITx+6.00x+2T2024 lib:MITx:mylib

    # Every repository with export enabled; --dry-run lists without queueing
    ./manage.py cms export_to_git --all --dry-run

Both skip, and report, content that no longer exists and content whose
auto-export settings (``ENABLE_EXPORT_GIT`` plus the course or library flag)
are off, and report content whose export could not be queued. The admin action
and ``--content-keys`` also skip rows with ``is_export_enabled`` off, while
``--all`` only considers rows with it on. The command also reports keys with
no repository, and exits non-zero if any
key errored or, with ``--content-keys``, if any named key was skipped. Exports
go through the same debounce as publish-triggered ones: a request made during
a pending export's 5-second countdown is merged into it, but one made after
that export has started queues another.

How Exports Are Scheduled
=========================

- A burst of publish signals for one course or library becomes one export,
  which runs once no signal has arrived for 5 seconds. A burst that keeps
  going is exported anyway every 10 minutes.
- Exports of the same course or library wait for each other, since they share
  one clone directory. An export queued while another is running waits for it,
  then exports whatever changed since.
- An export is killed after 10 minutes. Removing a ``.git/index.lock`` left by
  a killed export waits until the lock is a minute old.
