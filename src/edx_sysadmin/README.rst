edx-sysadmin
=============================

This is a django app plugin extracted from `edx-platform <https://github.com/edx/edx-platform>`_ which enables certian users to perform some specific operations in Open edX environment (which are described under ``Features`` section below).
Earlier, ``Sysadmin Dashboard`` was a part of ``edx-platform``, however starting from `lilac release <https://github.com/edx/edx-platform/tree/open-release/lilac.master>`_ of Open edX the sysadmin panel has been removed
and transitioned to as separate plugin.

NOTE:
It is recommended that you use edx-sysadmin plugin with Open edX's `lilac <https://github.com/edx/edx-platform/tree/open-release/lilac.master>`_ release and successors.
If you wish to use the ``Sysadmin Dashboard`` with Open edX releases before ``lilac`` you don't have to install this plugin and can simply enable ``ENABLE_SYSADMIN_DASHBOARD`` feature flag in environment files (e.g ``lms.yml`` or ``lms.env.json``) to access sysadmin dashboard features.

Features
~~~~~~~~

edx-sysadmin provides different features such as:

* Register Users:
    * You can ``register new user accounts`` with an easy to use form via ``Users`` tab.
* Delete Courses:
    * You can ``delete any course by using a course ID or directory`` via ``Courses`` tab.
* Git Import:
    * You can ``import any course maintained through a git repository`` via ``Git Import`` tab.
* Git Logs
    * You can ``check the logs for all imported courses`` through git via ``Git Logs`` tab.
* Git Reload (Not directly visible)
    * You can configure Github webhooks with this plugin to ensure reload/import of your courses on new commits


Configurations
--------------
You have the following configuration properties to customize your plugin behavior:

* **GIT_REPO_DIR:** This path defines where the imported repositories will be places in storage. Default value is ``/edx/var/edxapp/course_repos``.
* **GIT_IMPORT_STATIC:** This is a boolean that tells the plugin to either load the static content from the course repo or not. Default value is ``True``
* **SYSADMIN_GITHUB_WEBHOOK_KEY:** This value is used to save either of ``sha256 or sha1`` hashes. (This key is only used for Github Webhooks). Default value is ``None``.
* **SYSADMIN_DEFAULT_BRANCH:** This value is used to specify environment specific branch name to be used for course reload/import through Github Webhooks. (This key is only used for Github Webhooks). Default value is ``None``


Installing The Plugin
~~~~~~~~~~~~~~~~~~~~~

* You can install the plugin into your Open edX environment using PyPI e.g. ``pip install edx-sysadmin`` or directly from github e.g. ``pip install https://github.com/mitodl/edx-sysadmin.git``
* Once you have installed the plugin you can visit ``<EDX_BASE_URL>/sysadmin`` to access the plugin features.
* If you decide to make your own changes in the plugin you can go to ``Development Workflow`` section below.

``Note``: In some cases you might need to restart edx-platform after installing the plugin to reflect the changes.


Development Workflow
--------------------

For development you need to install this plugin into your Open edX instance.

.. code-block::

  # Clone edx-sysadmin to a directory which can be accessed from inside lms container i.e. ``src`` folder of
  # Open edX devstack setup, which is present under root directory (sibling directory of edx-platform directory)
  # and mapped at ``/edx/src`` inside edx-platform's lms container.
  cd src
  git clone git@github.com:mitodl/edx-sysadmin.git

  # Open LMS shell
  cd ../devstack
  make lms-shell

  # Remove edx-sysadmin plugin if already installed
  pip uninstall edx-sysadmin

  # Install plugin in editable mode
  pip install -e /edx/src/edx-sysadmin

  # If edx-sysadmin plugin doesn't reflect anything you can simply restart lms container (optional)
  make lms-restart

After installation the plugin should be directly getting served through your edx-sysadmin cloned repo (present at src folder) and you can do live changes to the plugin and they will be reflected in your Open edX instance.

Testing
~~~~~~~

edx-sysadmin tests are dependednt on edx-platform that's why they can only be run from inside of lms shell

.. code-block::

  # Enter LMS shell
  cd devstack
  make lms-shell

  # Go to the directory where edx-sysadmin is mapped inside container i.e. ``/edx/src/edx-sysadmin``
  cd /edx/src/edx-sysadmin

  # Install requirements for running tests (you can also install requirements inside a virtual environment)
  pip install -r ./requirements/quality.txt

  # Run Pytest
  pytest .

  # Run black formatter
  black --check .

  # Run Pycodestyle
  pycodestyle edx_sysadmin tests

  # Run Pylint
  pylint ./edx_sysadmin


License
-------

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.
Please see `LICENSE.txt <LICENSE.txt>`_ for details.

How To Contribute
-----------------

Contributions are very welcome.
Even though they were written with ``edx-platform`` in mind, the guidelines should be followed in all Open edX projects including this plugin.
