================================
OL Course Outline API
================================

**Plan (what can be done this way):** One public endpoint returns per-module (chapter)
title, estimated time, and counts. We **do not have** a module summary/description (Open edX
has no such field). For **time**: we can use the platform’s effort only for **videos** (and
readings); there is **no mechanism** to count time for assignments. Counts come from the
Blocks API: **videos** = ``video`` blocks, **readings** = ``html`` blocks, **assignments** =
graded sequentials (count), **app_items** = other leaf blocks (not video/html/problem).
Visibility and effort follow platform settings; no new storage.

**Endpoint:** ``GET /api/course-outline/v0/{course_id}/``

----------------------------------------------------------------------------
What does the API return?
----------------------------------------------------------------------------

We do **not** have a module summary or description (Open edX does not expose that for
chapters). The response is one JSON object per request with:

- **course_id** – Course key (e.g. ``course-v1:Org+Course+Run``).
- **generated_at** – ISO timestamp when the outline was built.
- **modules** – List of modules (one per Open edX **chapter**), each with:
  - **id** – Chapter block usage key.
  - **title** – Chapter display name.
  - **estimated_time_seconds** – Total estimated time for the chapter (seconds).
  - **counts** – Object with **videos**, **readings**, **assignments**, **app_items** (integers).

The front end can format ``estimated_time_seconds`` (e.g. hours/minutes) and combine title
and counts into a line like "Module 1: Introduction — 5 videos, 3 readings, 1 assignment, 2 activities" (time only reflects video + reading; no assignment time).

----------------------------------------------------------------------------
How is estimated time (estimated_time_seconds) obtained?
----------------------------------------------------------------------------

**Where it comes from:** We use the Open edX **EffortEstimationTransformer** (Blocks API).
We **can** count time for **videos** (duration from video pipeline/edxval); the platform
also estimates **reading** time from HTML word count. It does **not** provide time for
assignments or other block types. At the chapter level, ``estimated_time_seconds`` is
the platform’s aggregate of video + reading time only. There is no fallback; if the
platform returns 0, we return 0.

**How to get non-zero values:** See the section *How to get non-zero estimated_time_seconds?* below (publish, video durations, waffle flag).

**What about time for assignments?** There is **no mechanism** in Open edX to set or
derive time for assignments/subsections. We only have **estimated_time_seconds** (video +
reading). **counts.assignments** is the number of graded sequentials, not a duration.

----------------------------------------------------------------------------
How are the content counts (mappings) done?
----------------------------------------------------------------------------

We call the **Blocks API** (``get_blocks``) with ``block_counts=["video", "html", "problem"]``
and use the block tree under each chapter. Mappings:

- **videos** – Blocks with type ``video`` under the chapter (Blocks API ``block_counts.video``).
- **readings** – Blocks with type ``html`` under the chapter (``block_counts.html``).
- **assignments** – Count of **graded sequentials** (``type == "sequential"`` and ``graded == True``); not problem count.
- **app_items** – **Leaf** blocks (no children) whose type is not ``video``, ``html``, or ``problem``, and not a container (``course``, ``chapter``, ``sequential``, ``vertical``)—e.g. custom XBlocks, drag-and-drop.

----------------------------------------------------------------------------
How to get non-zero estimated_time_seconds?
----------------------------------------------------------------------------

The platform only fills ``effort_time`` when the EffortEstimationTransformer runs and has enough data. Do the following.

**1. Re-publish the course**

Block structure (and effort) is updated on course publish. In **Studio**, open the course and use **Publish**. After the background task completes (often within a minute), chapter-level ``effort_time`` is available. Re-publish again after changing content or fixing video durations.

**2. Ensure every video has a duration**

The transformer uses the video pipeline (e.g. edxval). If *any* course video has missing or zero duration, the transformer disables estimation for the **entire** course. Use **Video Uploads** in Studio (or your pipeline) so every video has duration metadata; fix or re-process any video that does not.

**3. Leave effort estimation enabled for the course**

The course-level waffle flag ``effort_estimation.disabled`` must be **off** for the course.

- **Django Admin:** **Waffle Utils > Waffle flag course overrides**. If there is an override for ``effort_estimation.disabled`` and your course, set **Override choice** to **Force Off**. If there is no override, estimation is enabled by default.
- Do not force the flag **On** for this course, or ``estimated_time_seconds`` will stay 0.

When all three are done, the API will return non-zero ``estimated_time_seconds`` when the Blocks API provides them.
