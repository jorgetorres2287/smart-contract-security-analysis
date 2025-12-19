from abc import ABC, abstractmethod
from typing import List
from analyzer.core.contract import Language, Contract

class BaseTool(ABC):
    """Abstract tool interface with language support"""
    
    def __init__(self, timeout: int = 600):
        self.timeout = timeout
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name"""
        pass
    
    @property
    @abstractmethod
    def supported_languages(self) -> List[Language]:
        """Languages this tool can analyze - CRITICAL for multi-language"""
        pass
    
    @abstractmethod
    def run(self, contract: Contract) -> tuple[bool, str, str]:
        """
        Run tool and return raw results
        Returns: (success: bool, stdout: str, stderr: str)
        NO PARSING - just raw output
        """
        pass
    
    def is_available(self) -> bool:
        """Check if tool is installed"""
        import shutil
        return shutil.which(self.name) is not None
