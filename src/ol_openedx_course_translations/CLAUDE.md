# CLAUDE.md — ol_openedx_course_translations

A CMS/LMS Django app that translates an entire course's content (XML/HTML,
subtitles, grading policy, course updates) into another language using
pluggable LLM providers (OpenAI, Gemini, Mistral, via `litellm`), then imports
the result as a new target course directly through the modulestore — no
manual export/TAR handling required. Exposed as a single CMS management
command, `translate_course`.

## Key files
- `ol_openedx_course_translations/management/commands/translate_course.py`:
  the main entry point. Reads the source course from the modulestore, exports
  it to XML (`export_course_to_xml`), translates files/subtitles/policy in
  parallel via Celery `group`, imports into the target course
  (`import_course_from_xml`), and logs a `CourseTranslationLog` row.
- `ol_openedx_course_translations/tasks.py`: Celery tasks used by the command
  for per-file/per-subtitle translation work (bounded by
  `TRANSLATE_FILE_TASK_LIMITS`).
- `ol_openedx_course_translations/providers/base.py`: `TranslationProvider`
  abstract base — defines `translate_subtitles`, `translate_text`,
  `translate_document`, plus shared SRT validation/retry logic
  (`translate_srt_with_validation`, timestamp/index/blank-content checks, one
  automatic retry before raising `ValueError`).
- `ol_openedx_course_translations/providers/llm_providers.py`: concrete
  provider implementations built on `litellm` (OpenAI/Gemini/Mistral).
- `ol_openedx_course_translations/utils/course_translations.py`: core helpers
  — `create_translated_copy`, `get_translatable_file_paths`,
  `get_translation_provider`, `translate_grading_policy`,
  `update_course_language_attribute`.
- `ol_openedx_course_translations/utils/constants.py`: language codes,
  provider name constants (e.g. `PROVIDER_MISTRAL`, `ENGLISH_LANGUAGE_CODE`).
- `ol_openedx_course_translations/models.py`: `CourseTranslationLog` — one row
  per translation run (source/target course, languages, providers/models used,
  command stats).
- `ol_openedx_course_translations/settings/{lms,cms}.py` +
  `settings/common.py`: `apply_common_settings` defines all default settings
  (target directories, translatable extensions, provider config, task limits,
  supported languages).

## Entry points & settings
- Registered under both `[project.entry-points."cms.djangoapp"]` and
  `"lms.djangoapp"` → `ol_openedx_course_translations.apps:OLOpenedXCourseTranslationsConfig`.
  Install required in both Studio (CMS) and LMS.
- Key settings (all defined with defaults in `settings/common.py`, override via
  `ENV_TOKENS`/`lms.yml`/`cms.yml`/`private.py`):
  - `TRANSLATIONS_PROVIDERS`: dict of provider configs (`api_key`,
    `default_model` per provider) plus `default_provider`. **API keys must be
    supplied by the deployer** — defaults ship as empty strings.
  - `COURSE_TRANSLATIONS_BASE_DIR` (default `/openedx/data/course_translations/`).
  - `COURSE_TRANSLATIONS_UPDATES_ITEMS_JSON_RELATIVE_PATH` (default
    `info/updates.items.json`).
  - `LITE_LLM_REQUEST_TIMEOUT`, `LLM_HTMLXML_MAX_UNITS_PER_REQUEST`,
    `LLM_HTMLXML_MAX_CHARS_PER_REQUEST`, `LLM_HTMLXML_MAX_CHARS_PER_UNIT`,
    `LLM_TRANSLATION_CACHE_MAX_ENTRIES`: tuning/safety knobs for LLM calls.
  - `TRANSLATE_FILE_TASK_LIMITS`: Celery soft/hard time limits and retry policy
    for translation tasks (29/30 min limits, 1 retry).
  - `COURSE_TRANSLATIONS_SUPPORTED_LANGUAGES`: the language-code → name map
    accepted by `--target-language`.
- Test settings module: `lms.envs.test` (per `setup.cfg`).

## Notes
- Providers/models are specified as `provider` or `provider/model` on the CLI
  (e.g. `openai/gpt-5.2`); when only the provider is given, the configured
  `default_model` is used.
- Subtitle (SRT) translation has a hard correctness gate: cue count, index,
  and timestamps must match the original exactly, and non-empty subtitles
  can't translate to blank. One retry is attempted automatically; if
  validation still fails, the whole course translation aborts and cleans up
  the partially-translated directory rather than leaving corrupt output.
- Content and SRT glossaries are optional and independent — pass one, both,
  or neither via `--content-glossary`/`--srt-glossary`.
- Real external LLM API calls are involved — no key configured for the chosen
  provider means translation will fail at runtime, not at plugin load time.
