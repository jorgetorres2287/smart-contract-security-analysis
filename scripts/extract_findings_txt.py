from pathlib import Path
import json
import sys
import argparse
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
from analyzer.config import Config

def extract_all_findings(contract_name=None):
    """Extract all findings from parsed results into organized text"""
    parsed_dir = Config.PARSED_RESULTS_DIR / 'slither'
    
    if not parsed_dir.exists():
        print(f"error: {parsed_dir} not found. run analysis first.")
        return
    
    all_parsed_files = list(parsed_dir.glob('*_parsed.json'))
    
    if not all_parsed_files:
        print("no parsed results found")
        return
    
    # Filter by contract name if specified
    if contract_name:
        parsed_files = [f for f in all_parsed_files if contract_name in f.name]
        if not parsed_files:
            print(f"error: no results found for contract '{contract_name}'")
            print(f"available contracts: {[f.stem.replace('_slither_parsed', '') for f in all_parsed_files]}")
            return
    else:
        parsed_files = all_parsed_files
    
    # Organize: Contract -> Severity -> Check Type -> Findings
    organized = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    
    for parsed_file in parsed_files:
        with open(parsed_file) as f:
            data = json.load(f)
        
        contract_name = data['contract']
        findings = data.get('analysis', {}).get('findings', [])
        
        for finding in findings:
            impact = finding.get('impact', 'Unknown')
            check = finding.get('check', 'unknown')
            organized[contract_name][impact][check].append(finding)
    
    # Generate output filename
    if contract_name:
        # Use contract-specific filename
        output_file = Path(f'analysis/{contract_name}_findings.txt')
    else:
        # Use general summary filename
        output_file = Path('analysis/findings_summary.txt')
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("SECURITY FINDINGS SUMMARY\n")
        f.write("=" * 80 + "\n\n")
        
        # Summary statistics
        total_contracts = len(organized)
        total_findings = sum(
            len(findings_list)
            for contract in organized.values()
            for severity in contract.values()
            for findings_list in severity.values()
        )
        
        f.write(f"Total Contracts Analyzed: {total_contracts}\n")
        f.write(f"Total Findings: {total_findings}\n\n")
        
        # Organize by contract
        severity_order = ['High', 'Medium', 'Low', 'Informational', 'Optimization']
        
        for contract_name in sorted(organized.keys()):
            contract_data = organized[contract_name]
            
            # Contract header
            contract_total = sum(
                len(findings_list)
                for severity in contract_data.values()
                for findings_list in severity.values()
            )
            
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"CONTRACT: {contract_name}\n")
            f.write(f"Total Findings: {contract_total}\n")
            f.write("=" * 80 + "\n\n")
            
            # By severity
            for severity in severity_order:
                if severity not in contract_data:
                    continue
                
                severity_data = contract_data[severity]
                severity_count = sum(len(findings) for findings in severity_data.values())
                
                if severity_count == 0:
                    continue
                
                f.write(f"\n{'─' * 80}\n")
                f.write(f"SEVERITY: {severity} ({severity_count} findings)\n")
                f.write(f"{'─' * 80}\n\n")
                
                # By check type
                for check_type in sorted(severity_data.keys()):
                    findings_list = severity_data[check_type]
                    
                    f.write(f"  Check Type: {check_type} ({len(findings_list)} occurrence(s))\n")
                    f.write(f"  {'─' * 76}\n")
                    
                    # Individual findings
                    for i, finding in enumerate(findings_list, 1):
                        confidence = finding.get('confidence', 'Unknown')
                        description = finding.get('description', '').strip()
                        file_ref = finding.get('first_markdown_element', '')
                        
                        f.write(f"\n  [{i}] Impact: {severity} | Confidence: {confidence}\n")
                        
                        if file_ref:
                            # Extract just filename if it's a long path
                            if '/' in file_ref:
                                file_ref = file_ref.split('/')[-1]
                            f.write(f"      File: {file_ref}\n")
                        
                        f.write(f"      Description:\n")
                        # Indent description and wrap
                        desc_lines = description.split('\n')
                        for desc_line in desc_lines:
                            desc_line = desc_line.strip()
                            if desc_line:
                                # Wrap long lines
                                max_width = 70
                                words = desc_line.split()
                                current_line = []
                                current_length = 0
                                
                                for word in words:
                                    if current_length + len(word) + 1 <= max_width:
                                        current_line.append(word)
                                        current_length += len(word) + 1
                                    else:
                                        if current_line:
                                            f.write(f"        {' '.join(current_line)}\n")
                                        current_line = [word]
                                        current_length = len(word)
                                
                                if current_line:
                                    f.write(f"        {' '.join(current_line)}\n")
                            else:
                                f.write(f"        {desc_line}\n")
                        
                        f.write("\n")
                    
                    f.write("\n")
                
                f.write("\n")
        
        # Summary by severity
        f.write("\n" + "=" * 80 + "\n")
        if len(organized) > 1:
            f.write("AGGREGATE SUMMARY BY SEVERITY\n")
        else:
            f.write("SUMMARY BY SEVERITY\n")
        f.write("=" * 80 + "\n\n")
        
        severity_totals = defaultdict(int)
        for contract_data in organized.values():
            for severity in severity_order:
                if severity in contract_data:
                    count = sum(len(findings) for findings in contract_data[severity].values())
                    severity_totals[severity] += count
        
        for severity in severity_order:
            if severity in severity_totals:
                f.write(f"  {severity:15s}: {severity_totals[severity]:4d} findings\n")
        
        # Summary by check type
        f.write("\n" + "=" * 80 + "\n")
        if len(organized) > 1:
            f.write("AGGREGATE SUMMARY BY CHECK TYPE\n")
        else:
            f.write("SUMMARY BY CHECK TYPE\n")
        f.write("=" * 80 + "\n\n")
        
        check_totals = defaultdict(int)
        for contract_data in organized.values():
            for severity_data in contract_data.values():
                for check_type, findings_list in severity_data.items():
                    check_totals[check_type] += len(findings_list)
        
        sorted_checks = sorted(check_totals.items(), key=lambda x: x[1], reverse=True)
        for check_type, count in sorted_checks:
            f.write(f"  {check_type:30s}: {count:4d} findings\n")
    
    print(f"\n{'='*80}")
    print(f"findings summary extracted")
    print(f"output: {output_file}")
    print(f"total contracts: {total_contracts}")
    print(f"total findings: {total_findings}")
    print(f"{'='*80}\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Extract findings from parsed Slither results into organized text file'
    )
    parser.add_argument(
        '--contract',
        type=str,
        help='Extract findings for a specific contract (e.g., uniswap_v4_poolmanager). If not specified, processes all contracts.'
    )
    
    args = parser.parse_args()
    extract_all_findings(contract_name=args.contract)
