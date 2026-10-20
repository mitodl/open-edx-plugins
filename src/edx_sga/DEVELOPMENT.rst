Developing on edx-sga
=====================

edx-sga lives in the `open-edx-plugins <https://github.com/mitodl/open-edx-plugins>`_ monorepo under ``src/edx_sga``. It moved there from ``mitodl/edx-sga``, which is no longer where changes land.

- Open pull requests against ``mitodl/open-edx-plugins``. Its ``AGENTS.md`` and ``docs/README.rst`` cover the workspace setup, the Tutor development environment, the version-bump rule and the release-compatibility table.
- Running the tests is described in the Testing section of this package's ``README.md``.
- Translations: the ``Makefile`` here extracts and validates the catalogues in ``edx_sga/conf/locale``.
