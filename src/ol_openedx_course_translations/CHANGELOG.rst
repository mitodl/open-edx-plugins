Change Log
----------

..
   All enhancements and patches to ol_openedx_course_translations will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).
.. There should always be an "Unreleased" section for changes pending release.

Unreleased
~~~~~~~~~~

[0.11.0] - 2026-09-30
~~~~~~~~~~~~~~~~~~~~~
Added
-----
* ``azure`` translation provider for Azure OpenAI. It sends LiteLLM
  ``azure/<deployment>`` model names and authenticates with an Entra token from
  ``DefaultAzureCredential`` (workload identity in-cluster, ``az login``
  locally), never an API key.
* The flat ``AZURE_OPENAI_ENDPOINT``, ``AZURE_OPENAI_API_VERSION`` and
  ``AZURE_OPENAI_DEFAULT_DEPLOYMENT`` settings are folded into
  ``TRANSLATIONS_PROVIDERS["azure"]`` when ``AZURE_OPENAI_ENDPOINT`` is set.
  This happens in both the common and production settings hooks, because
  production YAML is loaded after the common hook runs.
