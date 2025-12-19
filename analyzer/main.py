#!/usr/bin/env python3
"""Smart Contract Security Analyzer CLI"""

import argparse
from pathlib import Path
from typing import List

from analyzer.core.contract import Contract
from analyzer.core.analyzer import Analyzer
from analyzer.tools.slither import Slither
from analyzer.config import Config

def parse_args():
    parser = argparse.ArgumentParser(
        description='Analyze smart contracts for security vulnerabilities'
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--contract', '-c', help='Single contract file')
    input_group.add_argument('--batch', '-b', help='Directory with contracts')
    input_group.add_argument('--category', help='Dataset category (e.g., reentrancy)')
    
    parser.add_argument('--tools', '-t', default='slither', 
                       help='Comma-separated tools or "all"')
    parser.add_argument('--timeout', type=int, default=Config.DEFAULT_TIMEOUT)
    
    return parser.parse_args()

def get_tools(tools_arg: str, timeout: int) -> List:
    """Parse tool argument"""
    tool_map = {
        'slither': Slither,
        # Add Mythril later
    }
    
    if tools_arg.lower() == 'all':
        tool_names = list(tool_map.keys())
    else:
        tool_names = [t.strip() for t in tools_arg.split(',')]
    
    tools = []
    for name in tool_names:
        if name in tool_map:
            tools.append(tool_map[name](timeout=timeout))
    
    return tools

def get_contracts(args) -> List[Contract]:
    """Get contracts from CLI args"""
    if args.contract:
        return [Contract(args.contract)]
    
    elif args.batch:
        batch_path = Path(args.batch)
        contracts = []
        for ext in ['*.sol', '*.rs']:
            contracts.extend([Contract(p) for p in batch_path.rglob(ext)])
        return contracts
    
    elif args.category:
        category_path = Path(f'dataset/solidity/exploits/{args.category}')
        return [Contract(p) for p in category_path.glob('*.sol')]
    
    return []

def main():
    args = parse_args()
    
    tools = get_tools(args.tools, args.timeout)
    if not tools:
        print("error: no valid tools specified")
        return 1
    
    contracts = get_contracts(args)
    if not contracts:
        print("error: no contracts found")
        return 1
    
    analyzer = Analyzer(tools)
    
    if len(contracts) == 1:
        results = analyzer.analyze_single(contracts[0])
    else:
        results = analyzer.analyze_batch(contracts)
    
    print(f"analysis complete. raw results saved to {Config.RAW_RESULTS_DIR}")
    return 0

if __name__ == '__main__':
    exit(main())
