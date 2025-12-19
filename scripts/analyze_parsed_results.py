#!/usr/bin/env python3
"""
Analysis helper for parsed results - generates thesis-ready statistics
Usage: python scripts/analyze_parsed_results.py
"""
from pathlib import Path
import json
import sys
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
from analyzer.config import Config

def main():
    parsed_dir = Config.PARSED_RESULTS_DIR / 'slither'
    
    if not parsed_dir.exists():
        print("no parsed results found. run analysis first.")
        return
    
    parsed_files = list(parsed_dir.glob('*_parsed.json'))
    
    if not parsed_files:
        print("no parsed results found")
        return
    
    print(f"analyzing {len(parsed_files)} parsed results\n")
    print("=" * 80)
    
    # Aggregate statistics
    total_contracts = len(parsed_files)
    total_findings = 0
    severity_totals = defaultdict(int)
    check_totals = defaultdict(int)
    
    for parsed_file in parsed_files:
        with open(parsed_file) as f:
            data = json.load(f)
        
        analysis = data.get('analysis', {})
        contract_findings = analysis.get('total_findings', 0)
        total_findings += contract_findings
        
        # Aggregate by severity
        for severity, count in analysis.get('findings_by_severity', {}).items():
            severity_totals[severity] += count
        
        # Aggregate by check type
        for check, count in analysis.get('findings_by_check', {}).items():
            check_totals[check] += count
        
        # Print per-contract summary
        print(f"\ncontract: {data['contract']}")
        print(f"  total findings: {contract_findings}")
        if contract_findings > 0:
            print(f"  severity: h:{analysis['findings_by_severity']['High']} "
                  f"m:{analysis['findings_by_severity']['Medium']} "
                  f"l:{analysis['findings_by_severity']['Low']} "
                  f"i:{analysis['findings_by_severity']['Informational']}")
    
    # Overall summary
    print("\n" + "=" * 80)
    print("\naggregate statistics")
    print("=" * 80)
    print(f"total contracts analyzed: {total_contracts}")
    print(f"total findings: {total_findings}")
    print(f"average findings per contract: {total_findings/total_contracts:.1f}")
    
    print("\nfindings by severity:")
    for severity in ['High', 'Medium', 'Low', 'Informational', 'Optimization']:
        count = severity_totals.get(severity, 0)
        pct = (count / total_findings * 100) if total_findings > 0 else 0
        print(f"  {severity:15s}: {count:4d} ({pct:5.1f}%)")
    
    print(f"\ntop 15 finding types:")
    sorted_checks = sorted(check_totals.items(), key=lambda x: x[1], reverse=True)[:15]
    for check, count in sorted_checks:
        pct = (count / total_findings * 100) if total_findings > 0 else 0
        print(f"  {check:30s}: {count:4d} ({pct:5.1f}%)")
    
    # Export for thesis
    print("\n" + "=" * 80)
    print("\nexporting csv for thesis")
    print("=" * 80)
    
    csv_dir = Path('analysis/statistics')
    csv_dir.mkdir(parents=True, exist_ok=True)
    
    # Export severity distribution
    with open(csv_dir / 'severity_distribution.csv', 'w') as f:
        f.write("Severity,Count,Percentage\n")
        for severity in ['High', 'Medium', 'Low', 'Informational']:
            count = severity_totals.get(severity, 0)
            pct = (count / total_findings * 100) if total_findings > 0 else 0
            f.write(f"{severity},{count},{pct:.2f}\n")
    
    print(f"saved: {csv_dir / 'severity_distribution.csv'}")
    
    # Export finding types
    with open(csv_dir / 'finding_types.csv', 'w') as f:
        f.write("Check Type,Count,Percentage\n")
        for check, count in sorted_checks:
            pct = (count / total_findings * 100) if total_findings > 0 else 0
            f.write(f"{check},{count},{pct:.2f}\n")
    
    print(f"saved: {csv_dir / 'finding_types.csv'}")
    
    # Export per-contract summary
    with open(csv_dir / 'per_contract_summary.csv', 'w') as f:
        f.write("Contract,Total,High,Medium,Low,Informational\n")
        for parsed_file in parsed_files:
            with open(parsed_file) as pf:
                data = json.load(pf)
            analysis = data.get('analysis', {})
            sev = analysis.get('findings_by_severity', {})
            f.write(f"{data['contract']},"
                   f"{analysis.get('total_findings', 0)},"
                   f"{sev.get('High', 0)},"
                   f"{sev.get('Medium', 0)},"
                   f"{sev.get('Low', 0)},"
                   f"{sev.get('Informational', 0)}\n")
    
    print(f"saved: {csv_dir / 'per_contract_summary.csv'}")
    print("\ncsv files ready for thesis tables and charts")

if __name__ == '__main__':
    main()



