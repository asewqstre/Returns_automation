from abc import ABC, abstractmethod


class OccReturnsBase(ABC):
    """
    Abstract base class for OCC Returns client.

    Defines the required interface and internal helpers
    for any OCC Returns implementation.
    """

    # ===== Token handling =====

    @abstractmethod
    def _load_token(self) -> dict:
        """Load access token."""
        pass

    @abstractmethod
    def _refresh_token(self) -> dict:
        """Request and return a fresh access token."""
        pass

    @abstractmethod
    def _save_token(self, token_data: dict) -> None:
        """Persist token locally."""
        pass

    # ===== Request builders =====

    @abstractmethod
    def _build_headers(self, token: dict, content_type: str):
        """Build HTTP headers."""
        pass

    @abstractmethod
    def _build_params(self, fields, sort, page_size, current_page):
        """Build query parameters."""
        pass

    @abstractmethod
    def _build_body(self, *args, **kwargs):
        """Build request body."""
        pass

    # ===== HTTP layer =====

    @abstractmethod
    def _send_request(
        self,
        url: str,
        http_method: str,
        params: dict,
        headers: dict,
        body: dict | None
    ):
        """
        Send HTTP request with retry / token refresh logic.
        """
        pass

    # ===== Public API =====

    @abstractmethod
    def get_returns(self, *args, **kwargs) -> dict:
        """Get list of returns."""
        pass

    @abstractmethod
    def create_comment(self, return_num: int, *args, **kwargs) -> dict:
        """Create comment and get return details."""
        pass

    @abstractmethod
    def delete_comment(self, return_num: int, comment_num: int, *args, **kwargs):
        """Delete comment."""
        pass