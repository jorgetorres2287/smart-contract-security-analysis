from typing import Dict, Type, Optional
from analyzer.parsers.base import BaseParser
from analyzer.parsers.slither_parser import SlitherParser

# Registry of available parsers
PARSERS: Dict[str, Type[BaseParser]] = {
    'slither': SlitherParser,
}

def get_parser(tool_name: str) -> Optional[BaseParser]:
    """Get parser instance for a tool"""
    parser_class = PARSERS.get(tool_name)
    if parser_class:
        return parser_class()
    return None



