from OccReturns import OccReturns
import requests
import datetime
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path="./secret.env")


class Main:
    """
    Orchestrator class for processing incomplete OCC returns and
    sending aggregated results to Power Automate.

    This class is responsible for:
      - building a date range for querying returns,
      - retrieving returns from OCC,
      - detecting returns waiting for approval,
      - creating and cleaning up temporary comments,
      - collecting detailed return data,
      - sending final payload to an external automation endpoint.
    """

    def main(self):
        """
        Entry point for the returns processing workflow.

        The method performs the following steps:
          - initializes OCC returns client,
          - builds a date range for the last 30 days,
          - requests returns list from OCC,
          - filters returns with status "Ожидает утверждения",
          - retrieves detailed data for incomplete returns,
          - sends aggregated data to Power Automate via webhook,
          - raises an error if the HTTP request fails.

        Environment variables required:
            POWER_AUTOMATE_URL: Webhook URL for Power Automate.

        Returns:
            None
        """

        returns = OccReturns()

        date_range = self._build_date_range(
            date_from=datetime.datetime.now() - datetime.timedelta(days=30),
            date_to=datetime.datetime.now()
        )

        returns_list = returns.get_returns(date_from=date_range["from"], date_to=date_range["to"])
        incomplete_returns = self._search_incomplete_returns(returns_list)

        returns_data_list = self._get_returns_data(incomplete_returns=incomplete_returns)

        final_dict = {"incomplete_returns": incomplete_returns, "returns_list": returns_list, "returns_data_list": returns_data_list}

        url = os.getenv("POWER_AUTOMATE_URL")
        response = requests.post(url=url, json=final_dict)
        response.raise_for_status()
        print(final_dict)
        print(response.status_code)
        with open("./output.json", "w", encoding="utf-8") as file:
            import json
            json.dump(final_dict, file, ensure_ascii=False, indent=4)

    def _get_returns_data(self, incomplete_returns: list) -> list:
        """
        Retrieve detailed data for each incomplete return and
        remove automatically created anonymous comments.

        The method:
          - iterates over incomplete return numbers,
          - creates a temporary comment for each return,
          - scans returned comments list,
          - deletes comments authored by "Anonymous",
          - collects full return data into a list.

        Args:
            incomplete_returns (list): List of return codes
                                       that are awaiting approval.

        Returns:
            list: List of detailed return data dictionaries.
        """

        returns = OccReturns()
        returns_data_list = []
        for i in range(len(incomplete_returns)):
            return_data = returns.create_comment(return_num=incomplete_returns[i], comment=".")
            return_comments = return_data["cisComments"]
            for j in range(len(return_comments)):
                comment = return_comments[j]
                if comment["author"]["name"] == "Anonymous":
                    returns.delete_comment(return_num=incomplete_returns[i], comment_num=comment["code"])
            returns_data_list.append(return_data)
        return returns_data_list

    def _build_date_range(
            self,
            date_from: datetime.datetime,
            date_to: datetime.datetime
        ) -> dict:
        """
        Build ISO-formatted date range for OCC API requests.

        The method converts datetime objects into strings
        formatted as `YYYY-MM-DDTHH:MM:SS`.

        Args:
            date_from (datetime.datetime): Start datetime.
            date_to (datetime.datetime): End datetime.

        Returns:
            dict: Dictionary with keys:
                  - "from": formatted start date,
                  - "to": formatted end date.
        """

        date_range = {
            "from": date_from.strftime("%Y-%m-%dT%H:%M:%S"),
            "to": date_to.strftime("%Y-%m-%dT%H:%M:%S")
        }
        return date_range
    
    def _search_incomplete_returns(self, returns_list: dict) -> list:
        """
        Filter returns that are awaiting approval.

        The method:
          - iterates through OCC returns list,
          - checks `statusDisplay` field,
          - selects returns with status "Ожидает утверждения",
          - collects their return codes.

        Args:
            returns_list (dict): Parsed JSON response
                                 returned by `get_returns()`.

        Returns:
            list: List of return codes that are incomplete.
        """

        incomplete_returns = []
        for return_item in returns_list["returns"]:
            if return_item["statusDisplay"] == "Ожидает утверждения":
                incomplete_returns.append(return_item["code"])
        return incomplete_returns
    

if __name__ == "__main__":
    main = Main()
    main.main()