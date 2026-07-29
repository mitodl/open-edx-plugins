# CLAUDE.md — ol_openedx_checkout_external

A small LMS Django app plugin that adds a single GET API (`/checkout-external/?sku=<sku>`) which redirects the user to an external ecommerce/marketing-site checkout flow instead of edX's built-in ecommerce checkout, when they click "Upgrade" on the dashboard or in the Learning MFE.

## Key files
- `ol_openedx_checkout_external/views.py`: `external_checkout` — the only view. Looks up `CourseMode` by SKU, 404s if none/ambiguous, 302-redirects to `MARKETING_SITE_CHECKOUT_URL` with the resolved `course_id` as a query param.
- `ol_openedx_checkout_external/urls.py`: mounts the view at the plugin's URL root (see `PluginURLs.REGEX` below) under name `checkout_external`.
- `ol_openedx_checkout_external/exceptions.py`: `ExternalCheckoutError`, raised (surfaces as a 500) when `MARKETING_SITE_CHECKOUT_URL` is unset or multiple `CourseMode`s share a SKU.
- `ol_openedx_checkout_external/app.py`: `ExternalCheckoutConfig` — registers the URL (`^checkout-external/`) and settings for LMS only.
- `ol_openedx_checkout_external/settings/common.py`, `settings/production.py`: define/override `MARKETING_SITE_CHECKOUT_URL` (production reads it from `ENV_TOKENS`).

## Entry points & settings
- `lms.djangoapp`: `ol_openedx_checkout_external.app:ExternalCheckoutConfig`, URL regex `^checkout-external/`, settings wired for common + production only (no devstack module).
- Required settings (top-level in `lms.yml`/`private.py`): `MARKETING_SITE_CHECKOUT_URL` (the external checkout/cart endpoint to redirect to) and `ECOMMERCE_PUBLIC_URL_ROOT` (set to the LMS base URL so the platform treats ecommerce as external).
- Also requires Django-admin config: a `CommerceConfiguration` record with "Basket checkout page" = `/checkout-external/`, enabled, and "Checkout on ecommerce service" checked; and `CourseMode` records with non-empty, unique `sku` values for each course.

## Notes
- No `tests/` directory in this plugin — it's exercised via the repo-wide Tutor integration test flow, not standalone pytest.
- Only supports GET; any other HTTP method raises `NotImplementedError` (not caught, so it surfaces as a 500).
- SKU-to-course resolution assumes SKUs are unique per `CourseMode`; if duplicates exist (no DB-level unique constraint), the view intentionally errors rather than guessing.
