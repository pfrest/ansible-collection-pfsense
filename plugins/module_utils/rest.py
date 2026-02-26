"""
Module containing a client for Ansible to communicate with pfSense-pkg-RESTAPI.
"""
import base64
import requests


class RestClient:
    """
    A simple REST client for communicating with pfSense-pkg-RESTAPI.

    Attributes:
        host (str): The hostname of the REST API server.
        port (int): The port number of the REST API server.
        scheme (str): The URL scheme (http or https).
        timeout (int): The timeout for requests in seconds.
        base_url (str): The base URL constructed from scheme, host, and port.
        validate_certs (bool): Whether to validate SSL certificates.
        auth_mode (str): The authentication mode (e.g., basic, key).
        username (str): The username for authentication. (if basic auth is used)
        password (str): The password for authentication. (if basic auth is used)
        api_key (str): The API key for authentication (if key auth is used).
    """
    host: str
    port: int
    scheme: str
    timeout: int
    base_url: str
    validate_certs: bool
    auth_mode: str
    username: str
    password: str
    api_key: str

    def __init__(
        self,
        host: str,
        port: int,
        scheme: str = "https",
        timeout: int = 30,
        validate_certs: bool = True,
        auth_mode: str = "basic",
        username: str = "",
        password: str = "",
        api_key: str = "",
    ):
        """
        Initialize the RestClient with connection parameters.

        Args:
            host (str): The hostname of the REST API server.
            port (int): The port number of the REST API server.
            scheme (str): The URL scheme (http or https).
            timeout (int): The timeout for requests in seconds.
            validate_certs (bool): Whether to validate SSL certificates.
            auth_mode (str): The authentication mode (e.g., basic, key).
            username (str): The username for authentication.
            password (str): The password for authentication.
            api_key (str): The API key for authentication.
        """
        self.host = host
        self.port = port
        self.scheme = scheme
        self.timeout = timeout
        self.base_url = f"{self.scheme}://{self.host}:{self.port}"
        self.validate_certs = validate_certs
        self.auth_mode = auth_mode
        self.username = username
        self.password = password
        self.api_key = api_key

    def get_auth_headers(self) -> dict:
        """
        Generate authentication headers based on the auth_mode.

        Returns:
            dict: A dictionary of headers for authentication.
        """
        if self.auth_mode == "basic":
            credentials = f"{self.username}:{self.password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            return {"Authorization": f"Basic {encoded_credentials}"}
        elif self.auth_mode == "key":
            return {"Authorization": f"x-api-key {self.api_key}"}
        else:
            raise ValueError(f"Unsupported auth_mode {self.auth_mode} was provided. Please use 'basic' or 'key'.")
        
    def get(self, endpoint: str, params: dict = None) -> requests.Response:
        """
        Perform a GET request to the specified endpoint.

        Args:
            endpoint (str): The REST API endpoint URL.
            params (dict): Optional query parameters.

        Returns:
            requests.Response: The response object from the GET request.
        """
        url = f"{self.base_url}{endpoint}"
        headers = self.get_auth_headers()
        response = requests.get(
            url=url,
            headers=headers,
            params=params,
            verify=self.validate_certs,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response
    
    def post(self, endpoint: str, data: dict = None) -> requests.Response:
        """
        Perform a POST request to the specified endpoint.

        Args:
            endpoint (str): The REST API endpoint URL.
            data (dict): The data to send in the POST request.

        Returns:
            requests.Response: The response object from the POST request.
        """
        url = f"{self.base_url}{endpoint}"
        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"
        response = requests.post(
            url=url,
            headers=headers,
            json=data,
            verify=self.validate_certs,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response
    
    def patch(self, endpoint: str, data: dict = None) -> requests.Response:
        """
        Perform a PATCH request to the specified endpoint.

        Args:
            endpoint (str): The REST API endpoint URL.
            data (dict): The data to send in the PATCH request.

        Returns:
            requests.Response: The response object from the PATCH request.
        """
        url = f"{self.base_url}{endpoint}"
        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"
        response = requests.patch(
            url=url,
            headers=headers,
            json=data,
            verify=self.validate_certs,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response
    
    def put(self, endpoint: str, data: dict|list = None) -> requests.Response:
        """
        Perform a PUT request to the specified endpoint.

        Args:
            endpoint (str): The REST API endpoint URL.
            data (dict|list): The data to send in the PUT request.

        Returns:
            requests.Response: The response object from the PUT request.
        """
        url = f"{self.base_url}{endpoint}"
        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"
        response = requests.put(
            url=url,
            headers=headers,
            json=data,
            verify=self.validate_certs,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response
    
    def delete(self, endpoint: str, params: dict = None) -> requests.Response:
        """
        Perform a DELETE request to the specified endpoint.

        Args:
            endpoint (str): The REST API endpoint URL.
            params (dict): The data to send in the DELETE request.

        Returns:
            requests.Response: The response object from the DELETE request.
        """
        url = f"{self.base_url}{endpoint}"
        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"
        response = requests.delete(
            url=url,
            headers=headers,
            json=params,
            verify=self.validate_certs,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response
    
