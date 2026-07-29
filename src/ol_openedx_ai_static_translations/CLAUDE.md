# CLAUDE.md — ol_openedx_ai_static_translations

A CMS-only Django app providing a single management command,
`sync_and_translate_language`, that syncs static UI translation strings
(frontend MFE JSON + backend Django `.po` files) from edx-platform/MFE
sources, machine-translates the empty keys via an LLM provider (OpenAI,
Gemini, or Mistral, through `litellm`), and opens a pull request with the
result in an external translations repo (default:
`mitxonline-translations`).

## Key files
- `ol_openedx_ai_static_translations/management/commands/sync_and_translate_language.py`:
  The entire workflow — clone/checkout repo, extract empty keys, call the LLM
  in batches, apply translations to JSON/PO files, commit to a new branch,
  open a PR. Most of the logic (glossary matching, plural-form handling,
  retries) lives here.
- `ol_openedx_ai_static_translations/utils.py`: Helper functions the command
  delegates to — glossary loading/matching, PO plural-count detection,
  branch-name/language-code validation, provider/model resolution.
- `ol_openedx_ai_static_translations/constants.py`: Provider names, the
  `LEARNER_FACING_APPS` MFE list, `PLURAL_FORMS` (GNU gettext plural rules per
  language), `TRANSLATABLE_PLUGINS` (backend plugin apps eligible for PO
  translation), HTTP status/retry constants.
- `ol_openedx_ai_static_translations/settings/{common,cms}.py`: `apply_common_settings`
  seeds `TRANSLATIONS_PROVIDERS`/`TRANSLATIONS_GITHUB_TOKEN`/etc. only if not
  already set.

## Entry points & settings
- Registered only for `cms.djangoapp` as
  `ol_openedx_ai_static_translations.apps:OLOpenedXAIStaticTranslationsConfig`;
  no URLs, CMS-only (Studio) install.
- Shares its settings namespace with the separate `ol_openedx_course_translations`
  plugin — if both are installed, that plugin's settings win since both
  define the same keys and this one only sets defaults when unset:
  - `TRANSLATIONS_PROVIDERS`: dict of `default_provider` + per-provider
    `api_key`/`default_model` (openai, gemini, mistral, deepl).
  - `TRANSLATIONS_GITHUB_TOKEN`: PAT with repo write access, needed to push
    branches/open PRs.
  - `TRANSLATIONS_REPO_URL` / `TRANSLATIONS_REPO_PATH`: remote and local
    checkout location for the translations repo.
  - `LITE_LLM_REQUEST_TIMEOUT`: default 300s.
- No `setup.cfg`/pytest config or `tests/` dir in this plugin.

## Notes
- Requires network access to the configured LLM provider and to GitHub (to
  clone, push, and open a PR) — this command is not safe/useful to run without
  valid API keys and a `TRANSLATIONS_GITHUB_TOKEN`.
- `--dry-run` skips the commit/PR step, useful for testing translation output
  without touching the remote repo.
- Run from the CMS shell/container: `./manage.py cms sync_and_translate_language <lang> [options]`.
