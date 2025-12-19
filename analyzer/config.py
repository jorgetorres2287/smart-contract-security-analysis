from pathlib import Path
from typing import Optional
import platform
import os

class Config:
    """Global configuration"""
    
    # Solidity tools
    SLITHER_PATH: Optional[str] = None
    MYTHRIL_PATH: Optional[str] = None
    
    # Rust/Solana tools (for future)
    CARGO_PATH: Optional[str] = 'cargo'
    CLIPPY_PATH: Optional[str] = None
    
    # Settings
    DEFAULT_TIMEOUT: int = 600
    MAX_PARALLEL_PROCESSES: int = 2  # Reduced for mac performance
    
    # Docker settings
    USE_DOCKER: bool = os.environ.get('USE_DOCKER', str(platform.system() == 'Darwin')).lower() in ('true', '1', 'yes')
    DOCKER_IMAGE: str = 'ghcr.io/trailofbits/eth-security-toolbox:nightly'
    DOCKER_TIMEOUT: int = 600
    
    # Output directories (RAW vs PARSED separation)
    RESULTS_DIR: Path = Path('static_analysis_results')
    RAW_RESULTS_DIR: Path = Path('static_analysis_results/raw')
    PARSED_RESULTS_DIR: Path = Path('static_analysis_results/parsed')
    LOGS_DIR: Path = Path('analyzer/logs')
    TMP_DIR: Path = Path('tmp')  # For Docker-compatible temp files
    
    # Solc
    SOLC_VERSIONS_DIR: Path = Path.home() / '.solcx'
    AUTO_INSTALL_SOLC: bool = True
    
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories"""
        cls.RAW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.PARSED_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        cls.TMP_DIR.mkdir(parents=True, exist_ok=True)
