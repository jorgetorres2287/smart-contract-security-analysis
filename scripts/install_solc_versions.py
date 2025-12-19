#!/usr/bin/env python3
"""
Install required Solidity compiler versions for analysis.

This script ensures all necessary solc versions are installed for analyzing
contracts from different eras and ecosystems. Must be run with the analyzer
virtual environment activated.

Usage:
    source analyzer-venv/bin/activate  # or venv/bin/activate
    python scripts/install_solc_versions.py
"""

import sys
from pathlib import Path

# Add project root to path to access installed packages
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import solcx
except ImportError:
    print("error: py-solc-x not installed")
    print("   install with: pip install py-solc-x")
    sys.exit(1)

# Comprehensive list of compiler versions needed for our dataset
VERSIONS = [
    # Historic exploit era (2016-2017)
    "0.4.26",  # DAO attack era
    "0.5.17",  # Parity Wallet era
    
    # DeFi boom era (2018-2020)
    "0.6.12",  # DeFi protocols
    "0.7.6",   # DeFi summer
    
    # Modern era (2021-2024)
    "0.8.0",   # Major changes, gas optimizations
    "0.8.4",   # Common in 2021
    "0.8.6",   # Common in 2021-2022
    "0.8.9",   # Common in 2022
    "0.8.13",  # Common in 2022-2023
    "0.8.19",  # Common in 2023
    "0.8.20",  # Common in 2023-2024
    "0.8.24",  # Recent (2024)
    "0.8.26",  # Very recent (2024) - Uniswap V4
    "0.8.27",  # Very recent (2025) - Uniswap V4
    "0.8.3"
]

def main():
    """Install required Solidity compiler versions."""
    print("installing solidity compiler versions for analysis")
    print(f"target versions: {', '.join(VERSIONS)}")
    
    # Check current installations
    try:
        installed = solcx.get_installed_solc_versions()
        print(f"currently installed: {len(installed)} versions")
        if installed:
            print(f"   {', '.join(str(v) for v in installed)}")
    except Exception as e:
        print(f"warning: could not check installed versions: {e}")
        installed = []
    
    # Install missing versions
    installed_count = 0
    for version in VERSIONS:
        try:
            # Check if version is already installed
            if version not in [str(v) for v in installed]:
                print(f"installing solc version {version}")
                solcx.install_solc(version)
                installed_count += 1
            else:
                print(f"version {version} already installed")
        except Exception as e:
            print(f"failed to install version {version}: {e}")
            continue
    
    # Final status
    try:
        final_installed = solcx.get_installed_solc_versions()
        print(f"\ninstallation complete")
        print(f"total versions installed: {len(final_installed)}")
        if installed_count > 0:
            print(f"newly installed: {installed_count} versions")
        
        # Verify we have all required versions
        missing = []
        for version in VERSIONS:
            if version not in [str(v) for v in final_installed]:
                missing.append(version)
        
        if missing:
            print(f"warning: missing versions: {', '.join(missing)}")
            return 1
        else:
            print("all required versions installed")
            return 0
            
    except Exception as e:
        print(f"error checking final installation status: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
