from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseParser(ABC):
    """Abstract base for result parsers"""
    
    @abstractmethod
    def parse(self, raw_stdout: str, raw_stderr: str) -> Dict[str, Any]:
        """
        Parse raw tool output into structured format
        
        Returns:
            dict with keys:
                - total_findings: int
                - findings_by_severity: Dict[str, int]
                - findings: List[Dict] (simplified finding objects)
                - metadata: Dict (analysis metadata)
        """
        pass
    
    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Tool this parser handles"""
        pass



