Senior Thesis - Yale B.S. Computer Science - Fall 2025

# The Accessibility Paradox in Blockchain Security

Analysis framework evaluating whether free static analysis tools adequately protect blockchain developers against real-world exploits.

## Key Findings

- **50% detection rate**: Slither detected only half of theoretically detectable vulnerabilities across 6 ground-truth contracts
- **75% tool-threat mismatch**: Honeypots and rugpulls dominate real exploits (3,946 incidents, $89.9B in losses) but fall outside static analysis scope
- **Inverted signal**: Safe production contracts generated more warnings than exploited contracts combined
 
## Usage

**Analyze contracts:**
```bash
python -m analyzer.main --contract path/to/contract.sol --tools slither
python -m analyzer.main --batch scripts/dataset/solidity/exploits/ --tools slither
```

**Parse results:**
```bash
python scripts/parse_results.py
```

**Extract findings to text:**
```bash
python scripts/extract_findings_txt.py
```

**Generate statistics:**
```bash
python scripts/analyze_parsed_results.py
```

**Fetch DeFi exploit data:**
```bash
python scripts/export_defi_ecosystem.py
```

**Install Solidity compiler versions:**
```bash
python scripts/install_solc_versions.py
```

**Analysis notebook:**
```bash
final_analysis.ipynb
```

## Output

- Raw results: `static_analysis_results/raw/slither/`
- Parsed results: `static_analysis_results/json/`
- Text summaries: `static_analysis_results/txt/`
- Statistics: `static_analysis_results/statistics/`
