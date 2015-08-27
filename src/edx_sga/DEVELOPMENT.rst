Developing on edx-sga
==============================

Setup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Install devstack [as described here](http://mitodl.github.io/edx-dev-intro-slides/#6), but don't ``paver run_all_servers`` yet.
2. Instead, pip uninstall edx-sga (since it's part of the edx distribution, we have to remove the installed version)
3. ``cd /edx/app/edxapp/themes/``
4. Fork https://github.com/mitodl/edx-sga.git to your own github account.
5. ``git clone https://github.com/your-name/edx-sga.git``

6. ``cd edx-sga/``
7. ``pip install -e .``
8. ``paver run_all_servers``

You should now see your fork of the most recent master branch of edx-sga running in the LMS.

Developing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. ``cd /edx/app/edxapp/themes/edx-sga/``
2. ``git branch feature/your-name/name-of-feature``
3. write code
4. ``git add .``
5. ``git commit -m "Description of feature added."``
6. ``git push origin feature/your-name/name-of-feature``
7. Rebase your branch against mitodl/master and resolve any conflicts.
8. Open a pull request from your fork/feature branch to mitodl/master

Also, see: [testing](https://github.com/mitodl/edx-sga#testing). Javascript testing will be added soon.
