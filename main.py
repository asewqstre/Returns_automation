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
            date_to=datetime.datetime.now() + datetime.timedelta(days=1)
        )

        returns_list = returns.get_returns(date_from=date_range["from"], date_to=date_range["to"])
        incomplete_returns = self._search_incomplete_returns(returns_list)
        final_dict = self._simplify_returns_list(returns_list, incomplete_returns)

        url = os.getenv("POWER_AUTOMATE_URL")
        response = requests.post(url=url, json=final_dict)
        response.raise_for_status()

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
    
    def _simplify_returns_list(self, returns_list: dict, incomplete_returns: dict) -> dict:
        """
        Simplify and enrich incomplete returns data.

        The method:
          - iterates through the full OCC returns list,
          - filters returns that are present in `incomplete_returns`,
          - retrieves detailed return data via `_get_returns_data()`,
          - extracts and normalizes key fields for each return,
          - builds a flattened list of simplified return objects.

        Args:
            returns_list (dict): Parsed JSON response
                                 returned by `get_returns()`.
            incomplete_returns (list): List of return codes
                                       awaiting approval.

        Returns:
            list: List of simplified incomplete returns.
        """
        returns = returns_list["returns"] # Full returns list
        returns_data = self._get_returns_data(incomplete_returns) # Detailed returns data
            
        simplified_returns = []

        for return_item in returns:
            code = return_item.get("code", None) # Номер возврата
            if code is None:
                simplified_returns.append({"error": "Return item has no code"})

            if code not in incomplete_returns:
                continue
            return_abo = return_item.get("returnAbo", {}).get("uid", "") # Номер АБО
            comments = return_item.get("cisComments", "") # Комментарии
            comments = [{"author": comment.get("author", "").get("name", ""), "text": comment.get("text", "")} for comment in comments] # Keep only author name and text
            full_return = return_item.get("fullReturn", "") # Полный возврат
            uid = return_item.get("order", {}).get("account", {}).get("uid", "") # Номер НПА
            order_code = return_item.get("order", {}).get("code", "") # Номер заказа
            status_display = return_item.get("statusDisplay", "") # Статус возврата
            returns_request_reason = return_item.get("returnRequestReason", {}).get("name", "") # Причина возврата
            ordered_goods_type = return_item.get("orderedGoodsType", {}).get("name", "") # Способ возврата
            refund_info = return_item.get("refundInfo", [])
            return_value = return_item.get("returnValue", 0.0000) # Сумма возврата
            refund_status_display = return_item.get("refundStatusDisplay", {}).get("name", "") # Статус возврата
            return_date = return_item.get("date", "") # Дата создания возврата
            returned_goods_type = return_item.get("returnedGoodsType", {}).get("name", "")
            order_type = return_item.get("order", {}).get("orderGroupType", "")
            for return_detailed in returns_data:
                if return_detailed.get("rma", "") != code:
                    continue
                group_number = return_detailed.get("order", {}).get("groupNumber", "")
                sku_and_quantity = [str(entry.get("productSku")) + " " + str(entry.get("expectedQuantity")) for entry in return_detailed.get("entries", [])]
                initial_comment = [entry.get("cisComment", []) for entry in return_detailed.get("entries", [])]
                order_warehouse_name = return_detailed.get("entries", [])[0].get("orderEntry", {}).get("warehouseName", "")
                return_warehouse_name = return_detailed.get("warehouseName", "")
                initial_comment2 = return_detailed.get("comment", "")

            simplified_returns.append({
                "code": code,
                "group_number": group_number,
                "return_abo": return_abo,
                "comments": comments,
                "fullReturn": full_return,
                "uid": uid,
                "order_code": order_code,
                "status_display": status_display,
                "returns_request_reason": returns_request_reason,
                "ordered_goods_type": ordered_goods_type,
                "refund_info": refund_info,
                "return_value": return_value,
                "sku_and_quantity": sku_and_quantity,
                "return_warehouse_name": return_warehouse_name,
                "order_warehouse_name": order_warehouse_name,
                "initial_comment": initial_comment,
                "return_date": return_date,
                "refund_status_display": refund_status_display,
                "initial_comment2": initial_comment2,
                "order_type": order_type,
                "returned_goods_type": returned_goods_type
            })
        return simplified_returns
                

if __name__ == "__main__":
    main = Main()
    main.main()