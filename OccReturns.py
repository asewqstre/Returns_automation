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

    def _build_headers(self, token, content_type):
        """
        Build request headers using the loaded or refreshed token.

        Args:
            token (dict): Token object containing token_type and access_token.
            content_type (str): Content-Type of request.

        Returns:
            dict: Fully prepared request headers.
        """
        return {
            "Authorization": f"{token['token_type']} {token['access_token']}",
            "Content-Type": content_type
        }

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

    def _build_params(self, fields, sort, page_size, current_page):
        """
        Build query parameters for the returns list API.

        Returns:
            dict: Dictionary of query params.
        """
        return {
            "fields": fields,
            "sort": sort,
            "pageSize": page_size,
            "currentPage": current_page
        }

    def _build_body(self, country, channel, date_from, date_to):
        """
        Build POST request body for returns list API.

        Returns:
            dict: POST body.
        """
        return {
            "countyIsoCode": country,
            "channel": channel,
            "dateFrom": date_from,
            "dateTo": date_to
        }

    def _send_request(self, url, params, headers, body):
        """
        Execute POST request with automatic token refresh on 401 responses.

        The method:
          - performs up to 2 attempts,
          - tries request with the current token,
          - if server returns 401 Unauthorized, refreshes token and retries.

        Args:
            url (str): API endpoint.
            params (dict): URL query parameters.
            headers (dict): Request headers.
            body (dict): POST request body.

        Returns:
            Response: HTTP response object (possibly with 401 if repeated).
        """
        for _ in range(2):        # 2 attempts: initial + after refresh
            response = requests.post(url=url, params=params, headers=headers, json=body)

            if response.status_code != 401:
                return response

            # 401 -> refresh token and retry
            new_token = self._refresh_token()
            headers["Authorization"] = f"{new_token['token_type']} {new_token['access_token']}"

        return response   # return last response anyway
    
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
        params = self._build_params(fields, sort, page_size, current_page)
        body = self._build_body(country, channel, date_from, date_to)

        # Load token once
        token_data = self._load_token()
        headers = self._build_headers(token_data, content_type)

        response = self._send_request(url, params, headers, body)
        response.raise_for_status()

        return response.json()
        

if __name__ == "__main__":
    Returns = OccReturns()
    # access_token = Returns.refresh_token()["access_token"]
    print(Returns.get_returns(date_from="2025-11-02", date_to="2025-11-05", ))