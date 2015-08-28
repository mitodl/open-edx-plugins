Developing on edx-sga
==============================

Setup (including devstack setup)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Install vagrant_
#. Install virtualbox_
#. Set up devstack::

    mkdir devstack
    cd devstack
    curl -L https://raw.githubusercontent.com/edx/configuration/master/vagrant/release/devstack/Vagrantfile > Vagrantfile
    vagrant plugin install vagrant-vbguest
    vagrant up
    cd themes/

#. Fork https://github.com/mitodl/edx-sga.git to your own github account.
#. Set up your development environment::

    git clone https://github.com/your-name/edx-sga.git    
    vagrant ssh    
    sudo su edxapp    
    cd /edx/app/edxapp/themes/    
    pip uninstall edx-sga     (since it's part of the edx distribution, we have to remove the installed version)
    cd edx-sga/    
    pip install -e .    
    paver run_all_servers    

You should now see your fork of the most recent master branch of edx-sga running in the LMS.

Developing
~~~~~~~~~~

#. In your host filesystem::

    cd /path/to/devstack/themes/edx-sga     
    git branch feature/your-name/name-of-feature    

#. Write Code, then::

    git add .    
    git commit -m "Description of feature added."    
    git push origin feature/your-name/name-of-feature    

#. Rebase your branch against mitodl/master and resolve any conflicts, following this process_.
#. Open a pull request from your fork/feature branch to mitodl/master

Also, see testing_. Javascript testing will be added soon.

.. _Install vagrant: http://docs.vagrantup.com/v2/installation/
.. _Install virtualbox: https://www.virtualbox.org/wiki/Downloads
.. _this process: https://github.com/edx/edx-platform/wiki/How-to-Rebase-a-Pull-Request
.. _testing: https://github.com/mitodl/edx-sga#testing
