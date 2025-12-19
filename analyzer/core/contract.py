from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum
import re

class Language(Enum):
    """Supported contract languages - TYPE SAFE"""
    SOLIDITY = "solidity"
    RUST = "rust"

class Contract:
    """Lazy-loading contract with language-specific metadata"""
    
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self._source: Optional[str] = None
        self._metadata_cache: Optional[Dict[str, Any]] = None
        
        if not self.path.exists():
            raise FileNotFoundError(f"Contract not found: {self.path}")
        if self.path.suffix not in ['.sol', '.rs']:
            raise ValueError(f"Unsupported file type: {self.path}")
    
    @property
    def source(self) -> str:
        """Lazy load source code"""
        if self._source is None:
            self._source = self.path.read_text(encoding='utf-8')
        return self._source
    
    @property
    def language(self) -> Language:
        """Detect language - returns Language enum, not string"""
        if self.path.suffix == '.sol':
            return Language.SOLIDITY
        elif self.path.suffix == '.rs':
            return Language.RUST
        raise ValueError(f"Unknown language for extension: {self.path.suffix}")
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Extract language-specific metadata"""
        if self._metadata_cache is not None:
            return self._metadata_cache
        
        if self.language == Language.SOLIDITY:
            self._metadata_cache = self._extract_solidity_metadata()
        elif self.language == Language.RUST:
            self._metadata_cache = self._extract_rust_metadata()
        
        return self._metadata_cache
    
    def _extract_solidity_metadata(self) -> Dict[str, Any]:
        """Extract Solidity pragma version"""
        match = re.search(r'pragma\s+solidity\s+([^;]+);', self.source)
        pragma = match.group(1).strip() if match else None
        return {'pragma': pragma}
    
    def _extract_rust_metadata(self) -> Dict[str, Any]:
        """Extract Rust/Solana framework info"""
        is_anchor = 'use anchor_lang::prelude::*;' in self.source
        is_solana = 'use solana_program::' in self.source
        
        return {
            'framework': 'anchor' if is_anchor else ('solana' if is_solana else 'unknown'),
            'is_anchor': is_anchor,
            'is_solana': is_solana,
        }
    
    @property
    def name(self) -> str:
        return self.path.stem
    
    def to_dict(self) -> dict:
        """JSON-serializable (excludes source)"""
        return {
            'path': str(self.path),
            'name': self.name,
            'language': self.language.value,  # Enum to string for JSON
            'metadata': self.metadata,
        }
    
    def __repr__(self):
        return f"Contract(name={self.name}, language={self.language.value})"
