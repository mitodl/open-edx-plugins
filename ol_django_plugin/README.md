# mitol-django-ol_ai_static_translations

Django application for AI-powered static translation management. Provides management commands and utilities for synchronizing translation keys, translating using LLM providers, and creating pull requests with translated content.

## Features

- Sync translation keys from source repositories
- Translate using multiple LLM providers (OpenAI, Gemini, Mistral, DeepL)
- Create pull requests with translated content
- Support for PO and JSON translation file formats
- Glossary support for domain-specific terminology

## Installation

```bash
pip install mitol-django-ol_ai_static_translations
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    "mitol.ol_ai_static_translations",
]
```

## Usage

```bash
./manage.py sync_and_translate_language el
./manage.py sync_and_translate_language el --provider openai --model gpt-4-turbo --glossary
```
