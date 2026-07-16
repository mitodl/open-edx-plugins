OL Open edX Course Sync
=======================

An Open edX plugin to sync course changes to its reruns.

Version Compatibility
---------------------

It supports Open edX releases from `Sumac` and onwards.

Installing The Plugin
---------------------

For detailed installation instructions, please refer to the `plugin installation guide <../../docs#installation-guide>`_.

Installation required in:

* CMS (for course sync functionality)
* LMS (for problem attempts reset and rescore functionality)

Configuration
==============

CMS Configuration
-----------------

* Add a setting ``OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME`` for the service worker and all the sync operations will be done on behalf of this user.

  * For Tutor, you can run:

    .. code-block:: bash

       tutor config save --set OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME={USERNAME}

  * If you have a ``private.py`` for the CMS settings, you can add it to ``cms/envs/private.py``.

Usage
-----

Course Sync (CMS)
~~~~~~~~~~~~~~~~~

* Install the plugin and run the migrations in the CMS.
* Add the parent/source organization in the CMS admin model `CourseSyncOrganization`.
    * Course sync will only work for this organization. It will treat all the courses under this organization as parent/source courses.
* The plugin will automatically add course re-runs created from the CMS as the child courses.
    * The organization can be different for the reruns.
* Target/rerun courses can be managed in the CMS admin model `CourseSyncMapping`.
* Now, any changes made in the source course will be synced to the target courses.

Legacy Library Migration (CMS)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The plugin provides a management command to migrate legacy (v1) ``library_content``
blocks in course(s) to reference v2 library item bank blocks.

**Command:** ``migrate_legacy_library_blocks_to_item_bank``

**Syntax:**

.. code-block:: bash

    python manage.py cms migrate_legacy_library_blocks_to_item_bank [OPTIONS]

**Options:**

* ``--course-ids COURSE_KEYS``: Migrate legacy library content blocks for the given comma-separated list of course keys.
* ``--all-source-courses``: Migrate legacy library content blocks for all source courses (i.e. all courses registered in the ``CourseSyncMapping`` admin model).
* ``--persist-publish-state``: Re-publish migrated blocks that were already published prior to the migration.

  * Exactly one of ``--course-ids`` or ``--all-source-courses`` must be provided.
  * Requires ``OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME`` to be configured; the migration task runs on behalf of this user.

**Examples:**

Migrate legacy library content blocks for two courses:

.. code-block:: bash

    python manage.py cms migrate_legacy_library_blocks_to_item_bank \
        --course-ids "course-v1:edX+DemoX.1+2014,course-v1:edX+DemoX.2+2015"

Migrate legacy library content blocks for all source courses:

.. code-block:: bash

    python manage.py cms migrate_legacy_library_blocks_to_item_bank --all-source-courses

Migrate and also re-publish blocks that were already published before the migration:

.. code-block:: bash

    python manage.py cms migrate_legacy_library_blocks_to_item_bank --all-source-courses \
        --persist-publish-state

Problem Actions (LMS)
~~~~~~~~~~~~~~~~~~~~~

The plugin provides a management command to reset learner attempts or rescore problems across the source course and all its synced target courses.

**Command:** ``sync_problem_actions``

**Syntax:**

.. code-block:: bash

    python manage.py lms sync_problem_actions <action> <source_course_key> <problem_id> [OPTIONS]

**Actions:**

* ``reset_attempts``: Resets learner attempts for a problem
* ``rescore``: Rescores learners for a problem

**Options:**

* ``--username USERNAME``: Username to run the task as (default: 'courses_service_worker')
* ``--only-if-higher`` / ``--no-only-if-higher``: Whether to rescore only if the new score is higher (default: True)

**Examples:**

Reset attempts for a problem across all synced courses:

.. code-block:: bash

    python manage.py lms sync_problem_actions reset_attempts \
        "course-v1:ORG+COURSE+RUN" \
        "block-v1:ORG+COURSE+RUN+type@problem+block@abc123" \
        --username courses_service_worker

Rescore a problem for all learners across all synced courses:

.. code-block:: bash

    python manage.py lms sync_problem_actions rescore \
        "course-v1:ORG+COURSE+RUN" \
        "block-v1:ORG+COURSE+RUN+type@problem+block@abc123" \
        --username courses_service_worker \
        --only-if-higher
