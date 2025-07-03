"""Exceptions for External Checkout plugin"""


class ExternalCheckoutError(Exception):
    """
    Convenience exception class for external checkout errors
    """

    def __init__(self, message):
        # Force the lazy i18n values to turn into actual unicode objects
        super().__init__(str(message))
