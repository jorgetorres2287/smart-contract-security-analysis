#!/usr/bin/env python3
"""
list of smart contracts for thesis dataset
"""

from dataclasses import dataclass
from etherscan_client import Chain

@dataclass
class Contract:
    """Smart contract metadata"""
    name: str
    address: str
    chain: Chain
    category: str
    filename: str
    amount_lost: str = None
    date: str = None
    vulnerability_type: str = None
    description: str = None

# ============================================================================
# SAFE CONTRACTS (Audited, Non-Exploited)
# ============================================================================

SAFE_CONTRACTS = [
    Contract(
        name="Uniswap V4 Pool Manager",
        address="0x000000000004444c5dc75cb358380d2e3de08a90",
        chain=Chain.ETHEREUM,
        category="safe/ethereum/defi",
        filename="uniswap_v4_poolmanager.sol",
        date="2025-01-31",
        description="Uniswap V4 singleton pool manager - audited"
    ),
]

# ============================================================================
# EXPLOITS - Organized by Vulnerability Type
# ============================================================================

# ----------------------------------------------------------------------------
# Reentrancy Exploits
# ----------------------------------------------------------------------------
REENTRANCY_EXPLOITS = [
    Contract(
        name="Sentiment Lending Pool (Proxy)",
        address="0x62C5aa8277E49B3EAd43dC67453EC91dC6826403",
        chain=Chain.ARBITRUM,
        category="exploits/arbitrum/reentrancy",
        filename="sentiment_pool_proxy.sol",
        date="2023-04-04",
        amount_lost="$1,000,000",
        vulnerability_type="REENTRANCY",
        description="Read-only reentrancy via Balancer exitPool() let attacker borrow against stale balances; ~$1M withdrawn (most later returned)."
    ),
]

# ----------------------------------------------------------------------------
# Access Control Exploits
# ----------------------------------------------------------------------------
ACCESS_CONTROL_EXPLOITS = [
    Contract(
        name="Parity Wallet (First Hack)",
        address="0x863df6bfa4469f3ead0be8f9f2aae51c91a907b4",
        chain=Chain.ETHEREUM,
        category="exploits/ethereum/access-control",
        filename="parity_wallet_1.sol",
        amount_lost="$30,000,000",
        date="2017-07-19",
        vulnerability_type="ACCESS_CONTROL",
        description="Unprotected initWallet function allowed attacker to become owner"
    ),
]

# ----------------------------------------------------------------------------
# Arithmetic (Integer Overflow/Underflow) Exploits
# ----------------------------------------------------------------------------
ARITHMETIC_EXPLOITS = [
    Contract(
        name="BeautyChain (BEC)",
        address="0xc5d105e63711398af9bbff092d4b6769c82f793d",
        chain=Chain.ETHEREUM,
        category="exploits/ethereum/arithmetic",
        filename="beautychain.sol",
        amount_lost="Token supply inflation",
        date="2018-04-22",
        vulnerability_type="ARITHMETIC",
        description="BatchOverflow bug - CVE-2018-10299"
    ),
]

# ----------------------------------------------------------------------------
# Bridge Exploits
# ----------------------------------------------------------------------------
BRIDGE_EXPLOITS = []

# ----------------------------------------------------------------------------
# Oracle Manipulation Exploits
# ----------------------------------------------------------------------------
ORACLE_EXPLOITS = []

# ----------------------------------------------------------------------------
# Rugpull / Liquidity Drain Exploits
# ----------------------------------------------------------------------------
RUGPULL_EXPLOITS = [
    Contract(
        name="Anubis (ANKH)",
        address="0x507586012a126421c3669A64B8393fffA9C44462",
        chain=Chain.ETHEREUM,
        category="exploits/ethereum/rugpull",
        filename="anubis_ankh.sol",
        date="2021-10-29",
        amount_lost="$60,000,000",
        vulnerability_type="LIQUIDITY_DRAIN",
        description="AnubisDAO rugpull where developers drained 13,556 ETH ($60M) from Balancer liquidity pool within 20 hours of launch. One of the largest DeFi rugpulls in history. Project launched without website, investors deposited funds for ANKH token sale, then entire pool was drained to wallet 0xb1302743acf31f567e9020810523f5030942e211. Binance launched investigation to track perpetrators."
    ),
]

# ----------------------------------------------------------------------------
# Honeypot Exploits
# ----------------------------------------------------------------------------
HONEYPOT_EXPLOITS = [
    Contract(
        name="Private_Bank Honeypot",
        address="0x95d34980095380851902ccd9a1fb4c813c2cb639",
        chain=Chain.ETHEREUM,
        category="exploits/ethereum/honeypot",
        filename="private_bank.sol",
        amount_lost="N/A (Honeypot)",
        date="2018-01-01",
        vulnerability_type="HONEYPOT",
        description="Fake reentrancy vulnerability with hidden revert in Logger"
    ),
]

# ============================================================================
# COMBINED LISTS
# ============================================================================

# Combine all exploits
ALL_EXPLOITS = (
    REENTRANCY_EXPLOITS +
    ACCESS_CONTROL_EXPLOITS +
    ARITHMETIC_EXPLOITS +
    BRIDGE_EXPLOITS +
    ORACLE_EXPLOITS +
    RUGPULL_EXPLOITS +
    HONEYPOT_EXPLOITS
)

# All contracts (safe + exploits)
ALL_CONTRACTS = SAFE_CONTRACTS + ALL_EXPLOITS

# Legacy aliases for backward compatibility
HISTORIC_EXPLOITS = ALL_EXPLOITS
RECENT_CONTRACTS = ALL_CONTRACTS

# ============================================================================
# DATASET SUMMARY
# ============================================================================

def print_dataset_summary():
    """Print summary of dataset"""
    print("\n" + "="*80)
    print("DATASET SUMMARY")
    print("="*80)
    
    print(f"\nSafe Contracts: {len(SAFE_CONTRACTS)}")
    for contract in SAFE_CONTRACTS:
        print(f"  - {contract.name}")
    
    print(f"\nExploits: {len(ALL_EXPLOITS)}")
    print(f"  - Reentrancy: {len(REENTRANCY_EXPLOITS)}")
    print(f"  - Access Control: {len(ACCESS_CONTROL_EXPLOITS)}")
    print(f"  - Arithmetic: {len(ARITHMETIC_EXPLOITS)}")
    print(f"  - Bridge: {len(BRIDGE_EXPLOITS)}")
    print(f"  - Oracle Manipulation: {len(ORACLE_EXPLOITS)}")
    print(f"  - Rugpull: {len(RUGPULL_EXPLOITS)}")
    print(f"  - Honeypot: {len(HONEYPOT_EXPLOITS)}")
    
    total = len(ALL_CONTRACTS)
    print(f"\nTotal Contracts: {total}")
    print("="*80 + "\n")

if __name__ == '__main__':
    print_dataset_summary()
