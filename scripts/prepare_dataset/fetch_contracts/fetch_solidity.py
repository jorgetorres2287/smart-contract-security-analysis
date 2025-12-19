#!/usr/bin/env python3
"""
fetch all solidity contracts for thesis dataset
orchestrates fetching using etherscanclient and contracts_list

usage:
    python3 fetch_solidity.py --api-key YOUR_KEY
    python3 fetch_solidity.py --api-key YOUR_KEY --only-exploits
    python3 fetch_solidity.py --api-key YOUR_KEY --only-recent
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
from etherscan_client import EtherscanClient, Chain
from contracts_list import Contract, HISTORIC_EXPLOITS, RECENT_CONTRACTS, ALL_CONTRACTS

# Load environment variables from .env file
load_dotenv()

class ContractFetcher:
    """orchestrates contract fetching and manages results"""
    
    def __init__(self, client: EtherscanClient):
        self.client = client
        self.results = {
            'success': [],
            'failed': [],
            'skipped': []
        }
    
    def fetch_contract(self, contract: Contract, output_base: Path) -> bool:
        """
        fetch a single contract and save to disk
        
        args:
            contract: contract metadata
            output_base: base directory for output files
        
        returns:
            success: bool
        """
        
        # determine output path
        if contract.category.startswith('recent/'):
            output_path = output_base / 'recent' / contract.filename
        else:
            output_path = output_base / 'exploits' / contract.category / contract.filename
        
        # check if already exists
        if output_path.exists():
            print(f"  already exists, skipping")
            self.results['skipped'].append({
                'contract': contract.name,
                'address': contract.address,
                'path': str(output_path)
            })
            return True
        
        # validate address format
        if not self.client.validate_address(contract.address):
            print(f"  invalid address format: {contract.address}")
            self.results['failed'].append({
                'contract': contract.name,
                'address': contract.address,
                'category': contract.category,
                'reason': 'invalid address format'
            })
            return False
        
        # fetch from api
        success, data, error = self.client.fetch_source_code(contract.address, contract.chain)
        
        if not success:
            print(f"  failed: {error}")
            self.results['failed'].append({
                'contract': contract.name,
                'address': contract.address,
                'category': contract.category,
                'reason': error
            })
            return False
        
        # extract source code
        source_code = data.get('SourceCode', '')
        
        # create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # add smartbugs annotation header
        annotated_source = self._create_annotated_source(source_code, contract, data)
        
        # save source code
        output_path.write_text(annotated_source, encoding='utf-8')
        
        print(f"  saved to {output_path}")
        
        self.results['success'].append({
            'contract': contract.name,
            'address': contract.address,
            'category': contract.category,
            'path': str(output_path)
        })
        
        return True
    
    def _create_annotated_source(self, source_code: str, contract: Contract, data: dict) -> str:
        """add smartbugs annotation header to source code"""
        
        explorer_url = self.client.get_explorer_url(contract.address, contract.chain)
        
        header = f"""/*
 * @source: {explorer_url}
 * @author: {data.get('ContractName', 'Unknown')}
 * @vulnerable_at_lines: [MANUAL ANNOTATION REQUIRED]
 * @category: {contract.vulnerability_type or 'UNKNOWN'}
 * @exploit_amount: {contract.amount_lost or 'N/A'}
 * @date: {contract.date or 'Unknown'}
 * @blockchain: {contract.chain.value}
 * @description: {contract.description or contract.name}
 */

"""
        return header + source_code
    
    
    def fetch_all(self, contracts: List[Contract], output_base: Path):
        """
        fetch all contracts in the list
        
        args:
            contracts: list of contract objects to fetch
            output_base: base directory for output files
        """
        
        total = len(contracts)
        
    print(f"\nstarting batch fetch: {total} contracts\n")
        
        for i, contract in enumerate(contracts, 1):
            print(f"[{i}/{total}] {contract.name}")
            print(f"  address: {contract.address}")
            print(f"  chain: {contract.chain.value}")
            print(f"  category: {contract.category}")
            
            self.fetch_contract(contract, output_base)
            
            # rate limiting (except for last contract)
            if i < total:
                self.client.rate_limit()
            
            print()
        
        self._print_summary(output_base)
    
    def _print_summary(self, output_base: Path):
        """print detailed summary of results"""
        
        total = len(self.results['success']) + len(self.results['failed']) + len(self.results['skipped'])
        success_count = len(self.results['success'])
        failed_count = len(self.results['failed'])
        skipped_count = len(self.results['skipped'])
        
        print("\nfetch summary")
        
        print(f"\nsuccessfully fetched: {success_count}/{total} ({success_count/total*100:.1f}%)")
        print(f"skipped (already exist): {skipped_count}/{total} ({skipped_count/total*100:.1f}%)")
        print(f"failed: {failed_count}/{total} ({failed_count/total*100:.1f}%)")
        
        if self.results['success']:
            print(f"\nsuccessfully fetched:")
            
            # group by category
            by_category = {}
            for item in self.results['success']:
                cat = item['category']
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(item)
            
            for category, items in sorted(by_category.items()):
                print(f"\n  {category}: {len(items)} contracts")
                for item in items:
                    print(f"     {item['contract']}")
        
        if self.results['skipped']:
            print(f"\nskipped ({skipped_count} contracts already existed):")
            print("  run with fresh dataset/ folder to re-fetch")
        
        if self.results['failed']:
            print(f"\nfailed fetches:")
            
            # group failures by reason
            failure_reasons = {}
            for item in self.results['failed']:
                reason = item['reason']
                if reason not in failure_reasons:
                    failure_reasons[reason] = []
                failure_reasons[reason].append(item)
            
            for reason, items in failure_reasons.items():
                print(f"\n  reason: {reason}")
                print(f"     affected contracts ({len(items)}):")
                for item in items:
                    print(f"       - {item['contract']}")
                    print(f"         address: {item['address']}")
        
        # next steps
        print(f"\nnext steps:")
        
        if self.results['failed']:
            print("\n1. handle failed contracts:")
            print("   - unverified contracts: search github for source code")
            print("   - network errors: retry later or check api key")
            print("   - create simplified versions if source unavailable")
        
        print("\n2. add vulnerability annotations:")
        print("   - open each .sol file")
        print("   - find vulnerable lines")
        print("   - update @vulnerable_at_lines in header")
        print("   - add // <yes> <report> VULNERABILITY_TYPE markers")
        
        print("\n3. verify contracts:")
        print("   - review source code for accuracy")
        print("   - check compiler versions match")
        print("   - ensure annotations are correct")
        
        print("\n4. test with analyzer:")
        print("   python -m analyzer.main --contract ../dataset/solidity/exploits/reentrancy/dao.sol --tools slither")
        
        print()
        
        # save summary to file
        summary_path = Path('metadata/fetch_summary.json')
        summary_path.parent.mkdir(exist_ok=True)
        summary_path.write_text(json.dumps(self.results, indent=2), encoding='utf-8')
        print(f"full summary saved to: {summary_path}\n")

def main():
    parser = argparse.ArgumentParser(
        description='fetch solidity contracts from etherscan and compatible explorers'
    )
    parser.add_argument(
        '--api-key',
        default=os.getenv('ETHERSCAN_API_KEY'),
        help='etherscan api key (works for all chains via unified v2 api - get free at https://etherscan.io/myapikey). Can also be set via ETHERSCAN_API_KEY in .env file'
    )
    parser.add_argument(
        '--only-exploits',
        action='store_true',
        help='only fetch historic exploits'
    )
    parser.add_argument(
        '--only-recent',
        action='store_true',
        help='only fetch recent contracts'
    )
    parser.add_argument(
        '--output-dir',
        default='../../dataset/solidity',
        help='output directory for fetched contracts (default: ../../dataset/solidity)'
    )
    
    args = parser.parse_args()
    
    # Check if API key is provided
    if not args.api_key:
        print("error: etherscan api key required")
        print("   provide via --api-key argument or set ETHERSCAN_API_KEY in .env file")
        print("   get free api key at: https://etherscan.io/myapikey")
        return
    
    # create client with unified api key (works for all chains)
    client = EtherscanClient(args.api_key)
    fetcher = ContractFetcher(client)
    
    # set up output directory
    output_base = Path(args.output_dir).resolve()
    
    # determine which contracts to fetch
    contracts_to_fetch = []
    
    if args.only_recent:
        contracts_to_fetch = RECENT_CONTRACTS
    elif args.only_exploits:
        contracts_to_fetch = HISTORIC_EXPLOITS
    else:
        # fetch all by default (RECENT_CONTRACTS already contains all contracts)
        contracts_to_fetch = ALL_CONTRACTS
    
    if not contracts_to_fetch:
        print("no contracts selected to fetch")
        return
    
    # print what we're about to fetch
    print(f"\ncontracts to fetch:")
    print(f"   historic exploits: {len(HISTORIC_EXPLOITS)}")
    print(f"   recent contracts: {len(RECENT_CONTRACTS)}")
    print(f"   total: {len(contracts_to_fetch)}")
    
    # fetch all contracts
    fetcher.fetch_all(contracts_to_fetch, output_base)

if __name__ == '__main__':
    main()