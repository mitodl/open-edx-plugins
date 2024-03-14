"""Views for Rapid Response xBlock"""

import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from opaque_keys.edx.keys import UsageKey
from openedx.core.lib.xblock_utils import get_aside_from_xblock
from xmodule.modulestore.django import modulestore

log = logging.getLogger(__name__)


@login_required
@require_http_methods(
    [
        "POST",
    ]
)
def toggle_rapid_response(request):
    """
    An API View to toggle rapid response xblock enable status for a problem

    **Example Requests**

    POST:
     toggle-rapid-response/aside-usage-v2:block-v1$:Arbisoft+ARB_RR_1+1+type@problem+block@<key>::rapid_response_xblock

    **Example Responses**

    The API will return two types of response codes in general

    200 would be returned on successful rapid response enable status update

    A 500 would be returned if there are any configuration errors or the method is not
    supported
    """  # noqa: D401

    if request.method != "POST":
        msg = "API only supports POST requests"
        raise NotImplementedError(msg)

    block_key = request.path
    block_key = block_key.replace("/toggle-rapid-response/", "").replace(
        "/handler/", ""
    )
    usage_key = UsageKey.from_string(block_key)

    block = modulestore().get_item(usage_key.usage_key)
    handler_block = get_aside_from_xblock(block, usage_key.aside_type)

    handler_block.enabled = not handler_block.enabled
    try:
        modulestore().update_item(block, request.user.id, asides=[handler_block])
        modulestore().publish(block.location, request.user.id)
    except Exception as ex:  # pylint: disable=broad-except
        # Updating and publishing item might throw errors when the initial state of a block is draft (Unpublished).  # noqa: E501
        # Let them flow silently
        log.exception("Something went wrong with updating/publishing rapid response block."  # noqa: E501
                      " Most likely the block is in draft %s", ex)  # noqa: TRY401

    return JsonResponse({"is_enabled": handler_block.enabled})
