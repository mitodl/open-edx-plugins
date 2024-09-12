"""MIT xPro social auth backend"""

from social_core.backends.oauth import BaseOAuth2


class MITxProOAuth2(BaseOAuth2):
    """MIT xPro social auth backend"""

    name = "mitxpro-oauth2"

    ID_KEY = "username"
    REQUIRES_EMAIL_VALIDATION = False

    ACCESS_TOKEN_METHOD = "POST"  # noqa: S105

    # at a minimum we need to be able to read the user
    DEFAULT_SCOPE = ["user:read"]  # noqa: RUF012

    def authorization_url(self):
        """Provides authorization_url from settings"""  # noqa: D401
        return self.setting("AUTHORIZATION_URL")

    def access_token_url(self):
        """Provides access_token_url from settings"""  # noqa: D401
        return self.setting("ACCESS_TOKEN_URL")

    def api_root(self):
        """Returns the API root as configured"""  # noqa: D401
        root = self.setting("API_ROOT")

        if root and root[-1] != "/":
            root = f"{root}/"

        return root

    def auth_html(self):  # pragma: no cover
        """No html for this provider"""
        # NOTE: this is only here to stop the pylint warning about this abstract
        # method not being overridden without disabling it for the entire class
        return ""

    def api_url(self, path):
        """
        Returns the full api url given a relative path

        Args:
            path (str): relative api path
        """  # noqa: D401
        return f"{self.api_root()}{path}"

    def get_user_details(self, response):
        """Return user details from xPro account"""
        return {
            "username": response.get("username"),
            "email": response.get("email", ""),
            "name": response.get("name", ""),
        }

    def user_data(self, access_token, *args, **kwargs):  # noqa: ARG002
        """Loads user data from xpro"""  # noqa: D401
        url = self.api_url("api/users/me")
        headers = {"Authorization": f"Bearer {access_token}"}
        return self.get_json(url, headers=headers)
