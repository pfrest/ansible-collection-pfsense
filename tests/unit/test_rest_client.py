"""Tests for RestClient."""

# pylint: disable=missing-function-docstring,missing-class-docstring
# pylint: disable=attribute-defined-outside-init

import base64
from unittest.mock import patch, MagicMock

import pytest

from ansible_collections.pfrest.pfsense.plugins.module_utils.rest import RestClient


class TestRestClientInit:
    """RestClient constructor and default values."""

    def test_base_url(self):
        client = RestClient(host="fw.local", port=443)
        assert client.base_url == "https://fw.local:443"

    def test_custom_scheme(self):
        client = RestClient(host="fw.local", port=8080, scheme="http")
        assert client.base_url == "http://fw.local:8080"

    def test_defaults(self):
        client = RestClient(host="fw.local", port=443)
        assert client.validate_certs is True
        assert client.timeout == 30
        assert client.auth_mode == "basic"
        assert client.scheme == "https"

    def test_scheme_stored(self):
        client = RestClient(host="fw.local", port=5000, scheme="http")
        assert client.scheme == "http"


class TestAuthHeaders:
    """Authentication header generation."""

    def test_basic_auth(self):
        client = RestClient(
            host="fw",
            port=443,
            auth_mode="basic",
            username="admin",
            password="secret",
        )
        headers = client.get_auth_headers()
        expected = base64.b64encode(b"admin:secret").decode()
        assert headers["Authorization"] == f"Basic {expected}"

    def test_key_auth(self):
        client = RestClient(
            host="fw",
            port=443,
            auth_mode="key",
            api_key="mykey123",
        )
        headers = client.get_auth_headers()
        assert headers["Authorization"] == "x-api-key mykey123"

    def test_invalid_auth_mode(self):
        client = RestClient(host="fw", port=443, auth_mode="oauth")
        with pytest.raises(ValueError, match="Unsupported auth_mode"):
            client.get_auth_headers()


class TestHttpMethods:
    """Verify each method calls requests correctly."""

    @pytest.fixture(autouse=True)
    def _client(self):
        self.client = RestClient(
            host="fw.local",
            port=443,
            username="admin",
            password="pw",
        )

    @patch("ansible_collections.pfrest.pfsense.plugins.module_utils.rest.requests.get")
    def test_get(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        self.client.get("/api/v2/test", params={"id": 1})
        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        assert kwargs["url"] == "https://fw.local:443/api/v2/test"
        assert kwargs["params"] == {"id": 1}
        assert kwargs["verify"] is True
        assert kwargs["timeout"] == 30

    @patch("ansible_collections.pfrest.pfsense.plugins.module_utils.rest.requests.get")
    def test_get_http_scheme(self, mock_get):
        """Requests use http:// when scheme is set to http (api_protocol)."""
        client = RestClient(
            host="fw.local",
            port=5000,
            scheme="http",
            username="admin",
            password="pw",
        )
        mock_get.return_value = MagicMock(status_code=200)
        client.get("/api/v2/test")
        _, kwargs = mock_get.call_args
        assert kwargs["url"] == "http://fw.local:5000/api/v2/test"

    @patch("ansible_collections.pfrest.pfsense.plugins.module_utils.rest.requests.post")
    def test_post(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        self.client.post("/api/v2/test", data={"name": "a"})
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == {"name": "a"}
        assert "Content-Type" in kwargs["headers"]

    @patch(
        "ansible_collections.pfrest.pfsense.plugins.module_utils.rest.requests.patch"
    )
    def test_patch(self, mock_patch):
        mock_patch.return_value = MagicMock(status_code=200)
        self.client.patch("/api/v2/test", data={"name": "b"})
        _, kwargs = mock_patch.call_args
        assert kwargs["json"] == {"name": "b"}

    @patch("ansible_collections.pfrest.pfsense.plugins.module_utils.rest.requests.put")
    def test_put(self, mock_put):
        mock_put.return_value = MagicMock(status_code=200)
        self.client.put("/api/v2/test", data=[{"name": "c"}])
        _, kwargs = mock_put.call_args
        assert kwargs["json"] == [{"name": "c"}]

    @patch(
        "ansible_collections.pfrest.pfsense.plugins.module_utils.rest.requests.delete"
    )
    def test_delete(self, mock_delete):
        mock_delete.return_value = MagicMock(status_code=200)
        self.client.delete("/api/v2/test", params={"id": 1})
        _, kwargs = mock_delete.call_args
        assert kwargs["json"] == {"id": 1}
