from abc import ABC, abstractmethod

class OccReturnsBase(ABC):
    @abstractmethod
    def get_returns(
        self,
        date_from:str,
        date_to:str,
        page_size:int,
        current_page:int,
        fields:str,
        sort:str,
        content_type:str,
        country:str,
        channel:str,
        *args,
        **kwargs
        ):
        pass