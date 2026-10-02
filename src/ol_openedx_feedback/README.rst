ol-openedx-feedback
###################

An Open edX plugin that adds a "Send feedback" megaphone to course blocks in the
LMS via an ``XBlockAside``. Clicking it opens the feedback drawer in the Learning
MFE, which submits the learner's feedback to the **mit-learn** service. This
plugin renders the trigger and nothing else: no models, no REST API, nothing
persisted in edx-platform.

The trigger renders only for authenticated learners — never in Studio
author/preview mode, never for anonymous users. It sits right-aligned below the
block, or docked beside the AskTIM button on blocks that have one.

Messages
========

The aside talks to its parent window (the Learning MFE) with
``window.parent.postMessage``, always addressed to
``settings.LEARNING_MICROFRONTEND_URL`` and never to ``"*"``.

Sent on click, as ``ol-feedback::drawer-open``:

- ``payload.courseId`` — the course key
- ``payload.blockUsageKey`` — the block's usage key
- ``payload.blockType`` — the XBlock category (e.g. ``video``, ``problem``)
- ``payload.blockDisplayName`` — the Studio ``display_name``. Recorded on the
  submission so the content team can find the component; the drawer doesn't
  display it.
- ``payload.visibleTitle`` — the title the learner can see on the page, or ``""``
  when this plugin can't confirm there is one. This is the only name the drawer
  displays; see `Visible titles`_.
- ``viaKeyboard`` — true when the click came from the keyboard. The drawer
  renders cross-origin and so can't use ``:focus-visible``; it uses this to
  decide whether to highlight its heading.

Received from the MFE, both so keyboard focus can return to the megaphone
(WCAG 2.4.3):

- ``ol-feedback::drawer-closed`` — the drawer has closed; focus the trigger that
  opened it.
- ``ol-feedback::focus-trigger`` — the drawer's "return to block" link; focus the
  trigger but leave the drawer open.

Version Compatibility
=====================

For this plugin's compatibility with Open edX, see the
`Open edX Release Compatibility table <../../docs#open-edx-release-compatibility>`_.

Installation
============

1. Install the package into the LMS Python environment and restart the LMS:

   .. code-block:: bash

       pip install ol-openedx-feedback

   The plugin registers itself through its entry points — the ``xblock_asides.v1``
   aside plus the ``lms.djangoapp`` app config — so ``INSTALLED_APPS`` needs no
   change. The trigger is learner-facing only, so the plugin is LMS-only and is
   not installed in Studio/CMS.

2. **Enable XBlock asides.** No aside renders until they are switched on. In the
   LMS admin, open **XBlock Asides Config**
   (``/admin/lms_xblock/xblockasidesconfig/``), add an entry, and check
   **Enabled**. Keep the block types you want the trigger on out of **Disabled
   blocks** (space-separated; defaults to ``about course_info static_tab``).

3. **Turn on the waffle flag.** The trigger is gated per course by the
   ``ol_openedx_feedback.feedback_enabled`` course waffle flag, off by default.
   Enable it for the courses you're rolling out to, or globally.

Configuration
=============

Both settings below are read from ``ENV_TOKENS`` (e.g. in ``lms.yml``) by the
plugin's ``settings.common`` hook and exposed as Django settings of the same
name.

Excluded block types
--------------------

The trigger renders on every block type except a set of structural containers.
Override the set to exclude more types — for example ``html``:

.. code-block:: yaml

    OL_OPENEDX_FEEDBACK_EXCLUDED_BLOCK_TYPES:
      - course
      - chapter
      - sequential
      - vertical
      - html

Unset, it defaults to ``course``, ``chapter``, ``sequential`` and ``vertical``.

Text label
----------

The trigger is icon-only by default. To render the "Feedback" text label beside
the megaphone:

.. code-block:: yaml

    OL_OPENEDX_FEEDBACK_SHOW_LABEL: true

Visible titles
==============

For most block types ``display_name`` is an authoring label that never appears
on the page ("Wk3 intro copy - REVISED, do not reuse"), so showing it in the
feedback drawer would confuse the learner. The plugin therefore keeps a curated
map of the types that *do* render a title, and the field holding it —
``display_name`` for most, ``title`` for ``openassessment``, ``block_name`` for
``survey``. Types outside the map send an empty ``visibleTitle``, which the
drawer renders as generic block-type wording.

Two details:

- A type whose title is author-toggleable (``drag-and-drop-v2``'s ``show_title``)
  reports its title only when the toggle is on.
- Keys are usage-key block types (``category``). The extracted
  ``xblocks-contrib`` variants register under ``_<name>_extracted`` entry points
  but keep the plain category, so they need no separate entry.

**The map is not a setting.** Each entry asserts that the block type draws that
field on the learner's page, and the value goes verbatim into the drawer's
question text — so a wrong entry leaks the author's private note, which is the
bug the map exists to prevent. Changing it means editing
``DEFAULT_VISIBLE_TITLE_FIELDS`` in ``constants.py`` and having the claim
reviewed. Leaving a type out only costs generic wording.
