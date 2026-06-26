from __future__ import annotations
from abc import ABC, abstractmethod
from src.models import CompanySnapshot

class MarketDataProvider(ABC):
    @abstractmethod
    def get_snapshot(self, ticker: str) -> CompanySnapshot:
        raise NotImplementedError
