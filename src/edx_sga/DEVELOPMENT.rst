Developing on edx-sga
==============================

Setup (including devstack setup)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Install vagrant: http://docs.vagrantup.com/v2/installation/
2. Install virtualbox: https://www.virtualbox.org/wiki/Downloads
3. ``mkdir devstack``
4. ``cd devstack``
5. ``curl -L https://raw.githubusercontent.com/edx/configuration/master/vagrant/release/devstack/Vagrantfile > Vagrantfile``
6. ``vagrant plugin install vagrant-vbguest``
7. ``vagrant up``
8. ``cd themes/``
9. Fork https://github.com/mitodl/edx-sga.git to your own github account.
10. ``git clone https://github.com/your-name/edx-sga.git``
11. ``vagrant ssh``
12. ``sudo su edxapp``
13. ``cd /edx/app/edxapp/themes/``
14. ``pip uninstall edx-sga`` (since it's part of the edx distribution, we have to remove the installed version)
15. ``cd edx-sga/``
16. ``pip install -e .``
17. ``paver run_all_servers``

You should now see your fork of the most recent master branch of edx-sga running in the LMS.

Developing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. ``cd /path/to/devstack/themes/edx-sga`` in your host filesystem
2. ``git branch feature/your-name/name-of-feature``
3. write code
4. ``git add .``
5. ``git commit -m "Description of feature added."``
6. ``git push origin feature/your-name/name-of-feature``
7. Rebase your branch against mitodl/master and resolve any conflicts, following this process: https://github.com/edx/edx-platform/wiki/How-to-Rebase-a-Pull-Request.
8. Open a pull request from your fork/feature branch to mitodl/master

Also, see testing: https://github.com/mitodl/edx-sga#testing. Javascript testing will be added soon.
