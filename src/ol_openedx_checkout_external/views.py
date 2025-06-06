"""Views for External Checkout"""

import logging
from urllib.parse import quote

from common.djangoapps.course_modes.models import CourseMode
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseRedirect

from ol_openedx_checkout_external.exceptions import ExternalCheckoutError

log = logging.getLogger(__name__)


@login_required
def external_checkout(request):
    """
    An API View for external checkout that redirects to the marketing site for checkout

    **Example Requests**

    GET /checkout-external/?sku=TESTSKU

    **Example Responses**

    The API will return two types of response codes in general
    302, 404, 500

    A 302 redirect for the marketing site checkout would be returned in case the request was successful

    A 404 would be returned in case there is no sku matching products

    A 500 would be returned if there are any configuration errors
    """  # noqa: D401, E501

    if request.method != "GET":
        msg = "API only supports GET requests"
        raise NotImplementedError(msg)

    if not settings.MARKETING_SITE_CHECKOUT_URL:
        msg = "MARKETING_SITE_CHECKOUT_URL value is not configured properly"
        raise ExternalCheckoutError(msg)

    product_sku = request.GET.get("sku")

    if not product_sku:
        log.error("No Product SKU was found")
        raise Http404

    course_modes = CourseMode.objects.filter(sku=product_sku)
    if not course_modes:
        log.error(
            f"No CourseMode was found against the given product SKU ({product_sku})"  # noqa: G004
        )
        raise Http404

    # Because there is no unique constraint on SKU, so there could be multiple CourseModes with same SKU  # noqa: E501
    if len(course_modes) > 1:
        msg = f"Found multiple CourseModes for the same SKU ({product_sku})"
        raise ExternalCheckoutError(msg)

    #  Generate a URL to redirect to marketing site based on its checkout URL with and added  # noqa: E501
    #  course ID query param)
    course_id = quote(str(course_modes.first().course.id))
    redirect_url = f"{settings.MARKETING_SITE_CHECKOUT_URL}?course_id={course_id}"
    return HttpResponseRedirect(redirect_to=redirect_url)
