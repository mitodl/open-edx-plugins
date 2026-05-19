"""Django admin for UAI course generation jobs."""

from django.contrib import admin, messages

from ol_openedx_uai_content_customization.models import UAICourseGenerationJob
from ol_openedx_uai_content_customization.tasks import run_uai_course_generation_job


@admin.register(UAICourseGenerationJob)
class UAICourseGenerationJobAdmin(admin.ModelAdmin):
    """Admin UI for creating and running UAI generation jobs."""

    list_display = (
        "id",
        "status",
        "dry_run",
        "username",
        "created_by",
        "created_at",
        "started_at",
        "completed_at",
    )
    list_filter = ("status", "dry_run", "created_at")
    search_fields = ("username", "created_by__username", "task_id")
    readonly_fields = (
        "status",
        "output",
        "task_id",
        "created_by",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    )
    actions = ("run_selected_jobs",)

    @admin.action(description="Run selected UAI generation job(s)")
    def run_selected_jobs(self, request, queryset):
        """Queue selected jobs for asynchronous execution."""
        queued = 0
        skipped = 0

        for job in queryset:
            if job.status == UAICourseGenerationJob.Status.RUNNING:
                skipped += 1
                continue

            job.status = UAICourseGenerationJob.Status.PENDING
            job.started_at = None
            job.completed_at = None
            job.output = ""
            task = run_uai_course_generation_job.delay(job.id)
            job.task_id = task.id or ""
            job.save(
                update_fields=[
                    "status",
                    "started_at",
                    "completed_at",
                    "output",
                    "task_id",
                    "updated_at",
                ]
            )
            queued += 1

        if queued:
            self.message_user(
                request,
                f"Queued {queued} UAI generation job(s).",
                level=messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                f"Skipped {skipped} running job(s).",
                level=messages.WARNING,
            )

    def save_model(self, request, obj, form, change):
        """Stamp job creator for new records."""
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
