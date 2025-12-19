#!/usr/bin/env python3
"""
Solidity preprocessing utilities for robust Slither analysis.

Handles:
- Detection and extraction of Etherscan Standard JSON embedded in .sol files
- Pragma-based solc version selection via solc-select
- Path sanitization for cross-platform compatibility
- Docker integration for analyzing old Solidity versions on Mac
"""

import json
import re
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

PRAGMA_RE = re.compile(r'^\s*pragma\s+solidity\s+([^;]+);', re.IGNORECASE | re.MULTILINE)

def _first_noncomment_char(path: Path) -> Optional[str]:
    """
    Returns the first non-comment, non-whitespace character in a Solidity file.
    Used to detect if a .sol file is actually a JSON blob.
    """
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        in_block = False
        for line in f:
            s = line.strip()
            if not s:
                continue
            
            # Handle block comments
            if in_block:
                if '*/' in s:
                    in_block = False
                    # Check remainder of line after closing */
                    after_close = s.split('*/', 1)[1].strip()
                    if after_close and not after_close.startswith('//'):
                        return after_close[:1]
                continue
            
            # Check if line starts a block comment
            if s.startswith('/*'):
                if '*/' in s:
                    # Single-line block comment
                    after_close = s.split('*/', 1)[1].strip()
                    if after_close and not after_close.startswith('//'):
                        return after_close[:1]
                else:
                    in_block = True
                continue
            
            # Skip line comments
            if s.startswith('//'):
                continue
            
            # Found first non-comment character
            return s[:1]
    return None

def is_standard_json_file(path: Path) -> bool:
    """
    Check if a .sol file is actually Etherscan Standard JSON Input format.
    Returns True if the first non-comment character is '{'.
    """
    ch = _first_noncomment_char(path)
    return ch == '{'

def _sanitize_rel(rel: str) -> str:
    """
    Sanitize a path from Standard JSON sources:
    - Strip Windows drive letters (C:/)
    - Strip leading absolute path slashes (e.g., /home/user/... or /Users/...)
    - Normalize backslashes to forward slashes
    """
    rel = rel.replace('\\', '/')
    # Remove drive letters like "C:"
    if ':' in rel[:3]:
        rel = rel.split(':', 1)[1]
    # Remove leading slashes (absolute paths)
    while rel.startswith('/'):
        rel = rel[1:]
    return rel or 'Main.sol'

def extract_standard_json_to_tmp(path: Path, use_docker: bool = False) -> Path:
    """
    Extract Etherscan Standard JSON Input to a temporary directory.
    
    Handles:
    - Comment headers before JSON
    - Double-brace wrapping ({{ ... }})
    - Absolute paths in source keys
    - Multi-file projects with dependencies
    
    Args:
        path: Path to .sol file containing Standard JSON
        use_docker: If True, creates temp dir in workspace for Docker mounting
    
    Returns: Path to temp directory containing extracted sources
    """
    full_text = path.read_text(encoding='utf-8', errors='ignore')
    
    # Find where JSON starts (after comments)
    json_start = full_text.find('{{')
    if json_start == -1:
        json_start = full_text.find('{')
    
    if json_start == -1:
        raise ValueError(f"No JSON found in {path}")
    
    text = full_text[json_start:].strip()
    
    # Etherscan sometimes wraps with double braces
    if text.startswith('{{') and text.endswith('}}'):
        text = text[1:-1]
    
    data = json.loads(text)
    sources = data.get('sources', {})
    
    if use_docker:
        # Create temp in workspace for Docker mounting
        from analyzer.config import Config
        tmpdir = Config.TMP_DIR / f"slither-extract-{uuid.uuid4().hex[:8]}"
        tmpdir.mkdir(parents=True, exist_ok=True)
    else:
        tmpdir = Path(tempfile.mkdtemp(prefix='slither-json-'))
    
    for rel, obj in sources.items():
        content = obj.get('content', '')
        out = tmpdir / _sanitize_rel(rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding='utf-8')
    
    return tmpdir

def gather_pragmas(files: Iterable[Path]) -> List[str]:
    """
    Collect all pragma solidity statements from a set of Solidity files.
    Returns list of version strings (e.g., ["^0.8.0", "0.7.6"])
    """
    vers: List[str] = []
    for fp in files:
        try:
            txt = fp.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        vers += [m.group(1).strip() for m in PRAGMA_RE.finditer(txt)]
    return vers

def guess_solc_version(pragmas: List[str], files: Iterable[Path]) -> str:
    """
    Select the best solc version based on pragmas and heuristics.
    
    Strategy (Apple Silicon Mac - requires solc >= 0.8.24):
    1. Check if pragmas allow flexible versions (^, >=, >)
    2. If flexible and compatible with 0.8.24+, use 0.8.24
    3. If exact version required, warn and use 0.8.24 (may fail)
    4. Legacy syntax detection for 0.4.9
    5. Default to 0.8.24
    """
    # Legacy heuristics: check for old Solidity syntax
    for fp in files:
        try:
            sample = fp.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        # Look for pre-0.5.0 syntax tokens
        if any(tok in sample for tok in (' throw;', 'sha3(', 'suicide(', 'function()')):
            return '0.4.9'
    
    # Check for flexible pragmas that are compatible with 0.8.24
    for pragma in pragmas:
        # Flexible version specifiers: ^0.8.x, >=0.6.x, >0.7.x
        if pragma.startswith('^'):
            # ^0.8.10 means >= 0.8.10 and < 0.9.0 → Compatible with 0.8.24
            version = pragma.lstrip('^').strip()
            parts = list(map(int, version.split('.')))
            if parts[0] == 0 and parts[1] >= 8:  # ^0.8.x
                return '0.8.24'
        elif pragma.startswith('>=') or pragma.startswith('>'):
            # >=0.6.11 means any version >= 0.6.11 → Compatible with 0.8.24
            return '0.8.24'
    
    # Check for exact versions (no prefix)
    exact = [v.strip() for v in pragmas if re.fullmatch(r'\d+\.\d+\.\d+', v)]
    if exact:
        # Exact version required - use highest but warn it might not work on Apple Silicon
        highest = sorted(exact, key=lambda x: list(map(int, x.split('.'))), reverse=True)[0]
        parts = list(map(int, highest.split('.')))
        # If exact version < 0.8.24, we'll try anyway but it will likely fail on Apple Silicon
        return highest
    
    # Safe modern default for Apple Silicon
    return '0.8.24'

def solc_use(version: str) -> None:
    """
    Switch to a specific solc version using solc-select.
    Fails silently if solc-select is not available.
    """
    try:
        subprocess.run(['solc-select', 'use', version], check=False, capture_output=True)
    except Exception:
        pass

def auto_detect_remaps(extracted_dir: Path) -> List[str]:
    """
    Auto-detect import remaps needed for an extracted Solidity project.
    
    Scans all .sol files for import statements, extracts alias patterns
    (e.g., "solmate/", "@openzeppelin/"), and maps them to extracted folders.
    
    Args:
        extracted_dir: Root of extracted project (contains src/, lib/, etc.)
    
    Returns:
        List of remap strings like ["solmate=<path>/lib/solmate", "@oz=<path>/lib/openzeppelin"]
    """
    if not extracted_dir.exists():
        return []
    
    remaps = []
    
    # ALWAYS add basic directory remaps if they exist
    # This helps Slither even when contracts use relative imports
    common_dirs = ['src', 'contracts', 'lib']
    for dirname in common_dirs:
        dirpath = extracted_dir / dirname
        if dirpath.exists() and dirpath.is_dir():
            remaps.append(f"{dirname}/={dirpath}/")
    
    # Collect all import aliases from .sol files
    import_aliases = set()
    for sol_file in extracted_dir.rglob('*.sol'):
        try:
            text = sol_file.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        
        # Match patterns: import "X/..." or import {Y} from "X/..."
        # Capture the import path between quotes
        for match in re.finditer(r'import\s+.*?"([^"]+)"', text):
            import_path = match.group(1)
            
            # Skip relative imports (./... or ../...)
            if import_path.startswith('./') or import_path.startswith('../'):
                continue
            
            # Extract the alias (first segment before /)
            if '/' in import_path:
                alias = import_path.split('/')[0]
                # Skip if already added as a common dir
                if alias not in common_dirs:
                    import_aliases.add(alias)
    
    # Map each alias to an extracted folder
    for alias in sorted(import_aliases):
        # Try common locations where dependencies might be extracted
        candidates = [
            extracted_dir / 'lib' / alias,           # Foundry-style: lib/solmate/
            extracted_dir / 'node_modules' / alias,  # npm-style: node_modules/@openzeppelin/
            extracted_dir / alias,                   # Root-level: solmate/
        ]
        
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                # Use relative path from extracted_dir for cleaner remaps
                remaps.append(f"{alias}={candidate}")
                break
    
    return remaps


# ==================== Docker Utilities ====================

def check_docker_available() -> bool:
    """
    Verify Docker is installed and running.
    
    Returns:
        True if Docker daemon is accessible, False otherwise
    """
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_docker_image_available(image_name: str) -> bool:
    """
    Check if Docker image is available locally.
    
    Args:
        image_name: Full Docker image name with tag
    
    Returns:
        True if image exists locally, False otherwise
    """
    try:
        result = subprocess.run(
            ["docker", "images", "-q", image_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def pull_docker_image_if_needed(image_name: str) -> bool:
    """
    Pull Docker image if not available locally.
    
    Args:
        image_name: Full Docker image name with tag
    
    Returns:
        True if image is available (already existed or successfully pulled), False otherwise
    """
    if check_docker_image_available(image_name):
        return True
    
    print(f"pulling docker image: {image_name}")
    try:
        result = subprocess.run(
            ["docker", "pull", image_name],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for pull
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def ensure_docker_ready(image_name: str) -> None:
    """
    Verify Docker is running and image is available.
    Raises RuntimeError if Docker is not ready.
    
    Args:
        image_name: Full Docker image name with tag
    
    Raises:
        RuntimeError: If Docker is not running or image cannot be pulled
    """
    # Check Docker daemon
    if not check_docker_available():
        raise RuntimeError(
            "Docker is not running. Please start Docker Desktop.\n"
            "Install from: https://www.docker.com/products/docker-desktop"
        )
    
    # Check/pull image
    if not pull_docker_image_if_needed(image_name):
        raise RuntimeError(f"Failed to pull Docker image: {image_name}")


def translate_remaps_for_docker(remaps: List[str], host_project_root: Path, 
                                 container_mount_point: str = "/share") -> List[str]:
    """
    Convert host-absolute remaps to Docker container paths.
    
    Example:
        /tmp/project/lib/solmate=/tmp/.../lib/solmate
        → lib/solmate=/share/lib/solmate
    
    Args:
        remaps: List of remap strings with host absolute paths
        host_project_root: Root directory on host that will be mounted
        container_mount_point: Path where host_project_root is mounted in container
    
    Returns:
        List of remaps with container paths
    """
    docker_remaps = []
    for remap in remaps:
        if '=' not in remap:
            continue
            
        alias, path = remap.split('=', 1)
        path_obj = Path(path)
        
        try:
            # Make path relative to host_project_root
            rel_path = path_obj.relative_to(host_project_root)
            # Construct container path
            docker_path = f"{container_mount_point}/{rel_path}".replace('//', '/')
            docker_remaps.append(f"{alias}={docker_path}")
        except ValueError:
            # Path is not relative to host_project_root, skip it
            continue
    
    return docker_remaps


def get_docker_mount_root(project_path: Path) -> Path:
    """
    Determine the best root directory to mount into Docker.
    
    For extracted temp projects, mount the parent of the temp directory.
    For regular projects, mount the project directory itself.
    
    Args:
        project_path: Path to the project or contract file
    
    Returns:
        Path to directory that should be mounted
    """
    if project_path.is_file():
        # Mount parent directory of the file
        return project_path.parent
    else:
        # Mount the directory itself
        return project_path

