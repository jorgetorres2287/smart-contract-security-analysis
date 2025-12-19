#!/usr/bin/env python3
"""
Robust Slither integration with automatic handling of:
- Etherscan Standard JSON embedded in .sol files
- Pragma-based solc version selection
- Multi-file projects with dependencies
- Docker execution for old Solidity versions on Mac
"""

import re
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

from analyzer.tools.base import BaseTool
from analyzer.core.contract import Language, Contract
from analyzer.config import Config
from analyzer.utils.logger import setup_logger
from analyzer.utils.solidity_prep import (
    is_standard_json_file,
    extract_standard_json_to_tmp,
    gather_pragmas,
    guess_solc_version,
    solc_use,
    auto_detect_remaps,
    ensure_docker_ready,
    translate_remaps_for_docker,
    get_docker_mount_root,
)

class Slither(BaseTool):
    
    def __init__(self, timeout: int = 600, extra_remaps: Optional[List[str]] = None, 
                 use_docker: Optional[bool] = None):
        super().__init__(timeout)
        self.logger = setup_logger('slither')
        self._extra_remaps = extra_remaps or []
        
        # Auto-detect Docker usage if not specified
        self.use_docker = use_docker if use_docker is not None else Config.USE_DOCKER
        
        # Ensure Docker is ready if we're going to use it
        if self.use_docker:
            try:
                ensure_docker_ready(Config.DOCKER_IMAGE)
                self.logger.info(f"Docker mode enabled (image: {Config.DOCKER_IMAGE})")
            except RuntimeError as e:
                self.logger.warning(f"Docker not available: {e}")
                self.logger.warning("Falling back to local Slither execution")
                self.use_docker = False
    
    @property
    def name(self) -> str:
        return "slither"
    
    @property
    def supported_languages(self) -> List[Language]:
        """Slither ONLY supports Solidity"""
        return [Language.SOLIDITY]
    
    def run(self, contract: Contract) -> Tuple[bool, str, str]:
        """
        Run Slither with robust preprocessing:
        1. Detect and extract JSON-in-.sol files
        2. Auto-detect import remaps for extracted projects
        3. Select appropriate solc version based on pragmas
        4. Run Slither analysis (Docker or local) with remaps and return results
        """
        try:
            target_path = Path(contract.path)
            project = target_path
            auto_remaps = []
            
            # Check if this is a Standard JSON blob disguised as .sol
            if target_path.is_file() and is_standard_json_file(target_path):
                self.logger.info(f"Detected Standard JSON-in-.sol for {contract.name}; extracting sources...")
                extracted_dir = extract_standard_json_to_tmp(target_path, use_docker=self.use_docker)
                self.logger.info(f"Extracted to temp directory: {extracted_dir}")
                
                # Auto-detect remaps needed for this extracted project
                auto_remaps = auto_detect_remaps(extracted_dir)
                if auto_remaps:
                    self.logger.info(f"Auto-detected {len(auto_remaps)} remap(s): {', '.join([r.split('=')[0] for r in auto_remaps])}")
                
                # Find the main contract file to analyze
                # Strategy: Pick the concrete implementation contract
                project = None
                all_sol_files = list(extracted_dir.rglob('*.sol'))
                
                if all_sol_files:
                    # Read files to detect abstract contracts
                    concrete_contracts = []
                    for f in all_sol_files:
                        try:
                            content = f.read_text(encoding='utf-8', errors='ignore')
                            # Skip abstract contracts, interfaces, libraries
                            if 'abstract contract' in content or 'interface ' in content or 'library ' in content:
                                continue
                            # Must have 'contract' keyword (not just import/comment)
                            if re.search(r'\bcontract\s+\w+', content):
                                concrete_contracts.append(f)
                        except:
                            continue
                    
                    # Filter out helper/utility files from concrete contracts
                    excluded_patterns = ['Helper', 'Util', 'Library', 'Interface', 'Error', 'Storage']
                    filtered = [
                        f for f in concrete_contracts
                        if not any(pattern.lower() in f.stem.lower() for pattern in excluded_patterns)
                    ]
                    
                    # Use filtered list if not empty, otherwise use all concrete contracts
                    candidates = filtered if filtered else concrete_contracts
                    
                    # If still have candidates, prefer files matching original contract name
                    if candidates:
                        original_name = contract.name.lower().replace('_', '').replace('-', '')
                        # Try to find a file that matches part of the original name
                        # Score each candidate by match quality (longer match = better)
                        scored_candidates = []
                        for f in candidates:
                            file_name = f.stem.lower().replace('_', '').replace('-', '')
                            # Calculate match score: longer common substring = higher score
                            if file_name in original_name:
                                score = len(file_name)
                            elif original_name in file_name:
                                score = len(original_name)
                            else:
                                # Check for partial matches (at least 4 chars)
                                common_len = 0
                                for i in range(min(len(file_name), len(original_name))):
                                    if file_name[i] == original_name[i]:
                                        common_len += 1
                                    else:
                                        break
                                score = common_len if common_len >= 4 else 0
                            if score > 0:
                                scored_candidates.append((f, score))
                        
                        if scored_candidates:
                            # Pick the highest scored file, breaking ties by file size
                            project = max(scored_candidates, key=lambda x: (x[1], x[0].stat().st_size))[0]
                        else:
                            # Pick the largest overall
                            project = max(candidates, key=lambda f: f.stat().st_size)
                        
                        self.logger.info(f"Using main contract: {project.name} ({project.stat().st_size} bytes)")
                    else:
                        # Fallback to any .sol file
                        project = max(all_sol_files, key=lambda f: f.stat().st_size)
                        self.logger.warning(f"No concrete contracts found; using: {project.name}")
                
                # Fallback: use entire extracted directory
                if project is None:
                    project = extracted_dir
                    self.logger.warning(f"No .sol files found; analyzing directory")
            else:
                project = target_path
            
            # Gather all .sol files in scope
            files = [project] if project.is_file() else list(project.rglob('*.sol'))
            
            # Analyze pragmas and select appropriate compiler
            pragmas = gather_pragmas(files)
            version = guess_solc_version(pragmas, files)
            self.logger.info(f"Selecting solc {version} for {contract.name}")
            
            # Combine auto-detected remaps with user-provided remaps
            all_remaps = auto_remaps + self._extra_remaps
            
            # Execute via Docker or local
            if self.use_docker:
                return self._run_docker(project, version, all_remaps)
            else:
                return self._run_local(project, version, all_remaps)
            
        except subprocess.TimeoutExpired:
            return (False, "", f"Slither timed out after {self.timeout}s")
        except Exception as e:
            self.logger.error(f"Slither execution failed: {e}")
            return (False, "", f"Slither execution failed: {e}")
    
    def _run_local(self, project: Path, version: str, remaps: List[str]) -> Tuple[bool, str, str]:
        """
        Run Slither locally (original implementation).
        
        Args:
            project: Path to contract file or project directory
            version: Solc version to use
            remaps: List of import remaps
        
        Returns:
            Tuple of (success, stdout, stderr)
        """
        # Switch to appropriate solc version
        solc_use(version)
        
        # Build Slither command
        cmd = ['slither', str(project), '--json', '-']
        
        if remaps:
            cmd.extend(['--solc-remaps', ' '.join(remaps)])
            self.logger.debug(f"Using remaps: {remaps}")
        
        self.logger.debug(f"Executing (local): {' '.join(cmd)}")
        
        # Run Slither
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout
        )
        
        success = result.returncode == 0
        return (success, result.stdout, result.stderr)
    
    def _run_docker(self, project: Path, version: str, remaps: List[str]) -> Tuple[bool, str, str]:
        """
        Run Slither inside Docker container.
        
        Args:
            project: Path to contract file or project directory
            version: Solc version to use
            remaps: List of import remaps (host paths)
        
        Returns:
            Tuple of (success, stdout, stderr)
        """
        # Determine mount point
        mount_root = get_docker_mount_root(project)
        abs_mount_root = mount_root.resolve()
        
        # Translate remaps to container paths
        docker_remaps = translate_remaps_for_docker(remaps, abs_mount_root)
        
        # Determine working directory in container
        if project.is_file():
            # Mount parent, work on the file
            rel_path = project.relative_to(abs_mount_root)
            work_dir = "/share"
            target = str(rel_path)
        else:
            # Mount and work on the directory
            work_dir = "/share"
            target = "."
        
        # Build remap arguments
        remap_args = ""
        if docker_remaps:
            remap_args = f"--solc-remaps '{' '.join(docker_remaps)}'"
            self.logger.debug(f"Using Docker remaps: {docker_remaps}")
        
        # Build Docker command with auto-install and use of solc version
        # Suppress solc-select messages to keep JSON output clean
        bash_script = (
            f"(solc-select use {version} >&2 || "
            f"(solc-select install {version} >&2 && solc-select use {version} >&2)) && "
            f"slither {target} --json - {remap_args}"
        )
        
        docker_cmd = [
            "docker", "run",
            "--rm",  # Remove container after exit
            "-v", f"{abs_mount_root}:/share",  # Mount project
            "-w", work_dir,  # Set working directory
            "--user", "root",  # Run as root to avoid permission issues
            Config.DOCKER_IMAGE,
            "/bin/bash", "-c",
            bash_script
        ]
        
        self.logger.debug(f"Executing (docker): docker run ... {bash_script}")
        
        try:
            # Run Slither in Docker
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            success = result.returncode == 0
            return (success, result.stdout, result.stderr)
            
        except subprocess.TimeoutExpired:
            return (False, "", f"Docker Slither timed out after {self.timeout}s")
