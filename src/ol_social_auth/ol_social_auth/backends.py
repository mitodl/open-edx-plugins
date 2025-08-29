"""Open Learning social auth backend"""

import requests
from social_core.backends.oauth import BaseOAuth2


class OLOAuth2(BaseOAuth2):
    """Open Learning social auth backend"""

    name = "ol-oauth2"

    ID_KEY = "username"
    REQUIRES_EMAIL_VALIDATION = False

    ACCESS_TOKEN_METHOD = "POST"  # noqa: S105

    # at a minimum we need to be able to read the user
    DEFAULT_SCOPE = ["user:read"]

    _discovery_doc = None  # cache to avoid multiple network calls

    def _get_metadata(self):
        """Fetch OpenID provider metadata"""
        # For xPro, we don't have a discovery URL, so we get the URLs from settings
        if not self.setting("DISCOVERY_URL"):
            return {
                "authorization_endpoint": self.setting("AUTHORIZATION_URL"),
                "token_endpoint": self.setting("ACCESS_TOKEN_URL"),
                "userinfo_endpoint": self.api_url("api/users/me"),
            }

        if not self._discovery_doc:
            discovery_url = self.setting("DISCOVERY_URL")
            resp = requests.get(discovery_url, timeout=5)
            resp.raise_for_status()
            self._discovery_doc = resp.json()
        return self._discovery_doc

    def authorization_url(self):
        """Provides authorization_url from settings"""  # noqa: D401
        return self._get_metadata()["authorization_endpoint"]

    def access_token_url(self):
        """Provides access_token_url from settings"""  # noqa: D401
        return self._get_metadata()["token_endpoint"]

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
        """Return user details from MIT application account"""
        return {
            "username": response.get("username"),
            "email": response.get("email", ""),
            "name": response.get("name", ""),
        }

    def user_data(self, access_token, *args, **kwargs):  # noqa: ARG002
        """Loads user data from MIT application"""  # noqa: D401
        url = self._get_metadata()["userinfo_endpoint"]
        headers = {"Authorization": f"Bearer {access_token}"}
        return self.get_json(url, headers=headers)
