import os
from dotenv import load_dotenv
import requests
from datetime import date, timedelta
from Base.OccReturnsBase import OccReturnsBase
import io
import json

load_dotenv(dotenv_path="./secret.env")


class OccReturns(OccReturnsBase):
    """
    High-level client for requesting returns data from OCC with automatic
    token loading, validation and refresh.

    This class encapsulates all token-related logic:
      - loading token from local file,
      - validating its expected size,
      - refreshing it when file is missing, corrupted or expired,
      - retrying failed requests on 401 errors.

    The business code should only call `get_returns()`, while all token
    handling and request retry logic remains fully private.
    """

    TOKEN_PATH = "./token.json"

    # ===== Token handling =====

    def _load_token(self):
        """
        Load token from token.json with sanity checks.

        Token file is considered invalid if:
          - it does not exist, or
          - its size is outside expected range (160–196 bytes).
        
        In this case a new token is automatically requested.

        Returns:
            dict: Parsed token data.
        """
        if (
            not os.path.exists(self.TOKEN_PATH) 
            or os.path.getsize(self.TOKEN_PATH) not in range(160, 196)
        ):
            return self._refresh_token()

        with open(self.TOKEN_PATH, "r", encoding="utf-8") as file:
            return json.load(file)

    def _save_token(self, token_data):
        """
        Save token to token.json.

        Args:
            token_data (dict): Token payload returned by OCC.
        """
        with open(self.TOKEN_PATH, "w", encoding="utf-8") as file:
            json.dump(token_data, file, ensure_ascii=False, indent=2)

    def _refresh_token(self):
        """
        Request a fresh token from OCC and save it to token.json.

        The method:
          - performs a POST request to the REFRESH_TOKEN_URL,
          - validates response,
          - saves token,
          - returns parsed JSON.

        Returns:
            dict: New token payload.
        """
        url = os.getenv("REFRESH_TOKEN_URL")
        response = requests.post(url=url)

        response.raise_for_status()
        token_data = response.json()

        self._save_token(token_data)
        return token_data
    
    # ===== Request builders =====

    def _build_headers(self, **kwargs):
        """
        Build request headers using the loaded or refreshed token.

        Returns:
            dict: Fully prepared request headers.
        """
        return {k: v for k, v in kwargs.items() if v is not None}

    def _build_params(self, **kwargs):
        """
        Build query parameters for OCC API requests.

        The method:
        - accepts an arbitrary set of query parameters,
        - removes parameters with None values,
        - returns a clean dictionary suitable for HTTP requests.

        Args:
            **kwargs: Arbitrary keyword arguments representing query parameters.

        Returns:
            dict: Dictionary of query parameters without None values.
        """
        return {k: v for k, v in kwargs.items() if v is not None}

    def _build_body(self, **kwargs):
        """
        Build POST request body for returns list API.

        Returns:
            dict: POST body.
        """
        return {k: v for k, v in kwargs.items() if v is not None}

    # ===== HTTP layer =====

    def _send_request(self, url, http_method: str, **kwargs):
        """
        Execute POST request with automatic token refresh on 401 responses.

        The method:
          - performs up to 2 attempts,
          - tries request with the current token,
          - if server returns 401 Unauthorized, refreshes token and retries.

        Args:
            url (str): API endpoint.
            http_method (str): request method.

        Returns:
            Response: HTTP response object (possibly with 401 if repeated).
        """
        if http_method.lower() == "post":
            for _ in range(2):        # 2 attempts: initial + after refresh
                response = requests.post(url=url, params=kwargs["params"], headers=kwargs["headers"], json=kwargs["body"])

                if response.status_code != 401:
                    return response

                # 401 -> refresh token and retry
                new_token = self._refresh_token()
                kwargs["headers"]["Authorization"] = f"{new_token['token_type']} {new_token['access_token']}"

        if http_method.lower() == "get":
            for _ in range(2):        # 2 attempts: initial + after refresh
                response = requests.get(url=url, params=kwargs["params"], headers=kwargs["headers"])

                if response.status_code != 401:
                    return response

                # 401 -> refresh token and retry
                new_token = self._refresh_token()
                kwargs["headers"]["Authorization"] = f"{new_token['token_type']} {new_token['access_token']}"

        if http_method.lower() == "delete":
            for _ in range(2):        # 2 attempts: initial + after refresh
                response = requests.get(url=url, params=kwargs["params"], headers=kwargs["headers"])

                if response.status_code != 401:
                    return response

                # 401 -> refresh token and retry
                new_token = self._refresh_token()
                kwargs["headers"]["Authorization"] = f"{new_token['token_type']} {new_token['access_token']}"
            

        return response   # return last response anyway
    
    # ===== Public API =====

    def get_returns(
            self,
            date_from: str = str(date.today() - timedelta(5)),
            date_to: str = str(date.today()),
            page_size: int = 30,
            current_page: int = 0,
            fields: str = "BASIC,CIS_BOSS_BASIC,FULL",
            sort: str = "date:asc",
            content_type: str = "application/json",
            country: str = "KZ",
            channel: str = "WEB"
    ):
        """
        Retrieve a list of returns from OCC.

        The method:
          - loads (or refreshes) token,
          - builds request url, params, body, and headers,
          - sends request with retry logic,
          - raises an error for any non-200 result,
          - returns parsed JSON response.

        Args:
            date_from (str): Start date for filtering.
            date_to (str): End date for filtering.
            page_size (int): Pagination page size.
            current_page (int): Page number.
            fields (str): OCC field set to include.
            sort (str): Sorting mode.
            content_type (str): Request Content-Type.
            country (str): Market ISO code.
            channel (str): Sales channel.

        Returns:
            dict: Parsed JSON with returns list data.
        """

        url = os.getenv("RETURNS_LIST_URL")
        params = self._build_params(fields=fields, sort=sort, pageSize=page_size, currentPage=current_page)
        body = self._build_body(county=country, channel=channel, dateFrom=date_from, dateTo=date_to)

        # Load token once
        token_data = self._load_token()
        headers = self._build_headers(Authorization=f"{token_data['token_type']} {token_data['access_token']}", Content_Type=content_type)

        response = self._send_request(url, http_method="post", params=params, headers=headers, body=body)
        response.raise_for_status()

        return response.json()
    
    def create_comment(self, return_num, comment):
        """
        Create a comment for a specific return in OCC.

        The method:
        - loads (or refreshes) token,
        - builds request url, body, and headers,
        - sends POST request to create a comment,
        - raises an error for any non-200 result,
        - returns parsed JSON response.

        Args:
            return_num (str): Return number to which the comment will be added.
            comment (str): Comment text to create.
            *args: Additional positional arguments (not used).
            **kwargs: Additional keyword arguments (not used).

        Returns:
            dict: Parsed JSON with created comment data.
        """

        url = os.getenv("CREATE_COMMENT_URL").format(return_num=return_num)

        params = {}
        body = self._build_body(comment=comment)

        # Load token
        token_data = self._load_token()
        headers = self._build_headers(Authorization=f"{token_data['token_type']} {token_data['access_token']}")

        response = self._send_request(url, http_method="post", headers=headers, params=params, body=body)
        response.raise_for_status()

        return response.json()

    def delete_comment(self, return_num, comment_num) -> None:
        """
        Delete a comment from a specific return in OCC.

        The method:
        - loads (or refreshes) token,
        - builds request url and headers,
        - sends DELETE request to remove the comment,
        - raises an error for any non-200 result.

        Args:
            return_num (str): Return number containing the comment.
            comment_num (str): Comment identifier to delete.
            *args: Additional positional arguments (not used).
            **kwargs: Additional keyword arguments (not used).

        Returns:
            None: No content is returned on successful deletion.
        """

        url = os.getenv("DELETE_COMMENT_URL").format(return_num=return_num, comment_num=comment_num)

        params = {}

        # Load token
        token_data = self._load_token()
        headers = self._build_headers(Authorization=f"{token_data['token_type']} {token_data['access_token']}")
        
        response = self._send_request(url, http_method="delete", headers=headers, params=params)


if __name__ == "__main__":
    Returns = OccReturns()
    # access_token = Returns.refresh_token()["access_token"]
    # print(Returns.get_returns(date_from="2025-11-02", date_to="2025-11-05", ))
    
    # return_data = Returns.create_comment(84630001, ".")
    
    # for i in range(len(return_data["cisComments"])):
    #     if return_data["cisComments"][i]["text"] == ".":
    #         comment_num = return_data["cisComments"][i]["code"]

    # Returns.delete_comment(84630001, comment_num)

    # print(return_data)