from django.db import models


class CourseGitRepo(models.Model):
    """
    Model to store Git repository information for courses.
    """

    course_id = models.CharField(max_length=255, unique=True, primary_key=True)
    git_url = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Course Git Repository"
        verbose_name_plural = "Course Git Repositories"
        ordering = ["-created_at"]

    def __str__(self):
        return f"CourseGitRepo(course_id={self.course_id}, git_url={self.git_url})"
