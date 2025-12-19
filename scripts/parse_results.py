#!/usr/bin/env python3
"""
Batch parser for existing raw results
Usage: python scripts/parse_results.py
"""
from pathlib import Path
import json
import sys

# Add analyzer to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.parsers import get_parser
from analyzer.config import Config

def main():
    raw_dir = Config.RAW_RESULTS_DIR / 'slither'
    parsed_dir = Config.PARSED_RESULTS_DIR / 'slither'
    parsed_dir.mkdir(parents=True, exist_ok=True)
    
    parser = get_parser('slither')
    if not parser:
        print("error: no parser available for slither")
        return
    
    raw_files = list(raw_dir.glob('*_slither.json'))
    print(f"found {len(raw_files)} raw slither results\n")
    
    for raw_file in raw_files:
        print(f"processing {raw_file.name}")
        
        # Read raw output
        raw_stdout = raw_file.read_text(encoding='utf-8')
        
        # Parse
        parsed = parser.parse(raw_stdout, "")
        
        # Save parsed
        contract_name = raw_file.stem.replace('_slither', '')
        output_file = parsed_dir / f"{contract_name}_slither_parsed.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'contract': contract_name,
                'tool': 'slither',
                'analysis': parsed
            }, f, indent=2)
        
        # Print summary
        print(f"  total findings: {parsed['total_findings']}")
        if parsed['total_findings'] > 0:
            print(f"  - high: {parsed['findings_by_severity']['High']}")
            print(f"  - medium: {parsed['findings_by_severity']['Medium']}")
            print(f"  - low: {parsed['findings_by_severity']['Low']}")
            print(f"  - informational: {parsed['findings_by_severity']['Informational']}")
        
        # Show top findings by check type
        if parsed['findings_by_check']:
            top_checks = sorted(parsed['findings_by_check'].items(), 
                              key=lambda x: x[1], reverse=True)[:5]
            print(f"  top checks:")
            for check, count in top_checks:
                print(f"    - {check}: {count}")
        print()
    
    print(f"parsed results saved to {parsed_dir}")

if __name__ == '__main__':
    main()



