import json
from typing import Dict, Any, List
from pathlib import Path

from analyzer.parsers.base import BaseParser

class SlitherParser(BaseParser):
    
    @property
    def tool_name(self) -> str:
        return "slither"
    
    def parse(self, raw_stdout: str, raw_stderr: str) -> Dict[str, Any]:
        """
        Parse Slither JSON output into thesis-friendly format
        
        Extracts:
        - Total findings count
        - Findings by severity (High/Medium/Low/Informational)
        - Findings by check type
        - Individual findings with essential metadata
        """
        if not raw_stdout or not raw_stdout.strip():
            return self._empty_result("No output from Slither")
        
        try:
            data = json.loads(raw_stdout)
        except json.JSONDecodeError as e:
            return self._empty_result(f"Invalid JSON: {e}")
        
        # Extract detectors array
        results = data.get('results', {})
        detectors = results.get('detectors', [])
        
        # Aggregate findings by severity
        findings_by_severity = {
            'High': [],
            'Medium': [],
            'Low': [],
            'Informational': [],
            'Optimization': []
        }
        
        # Aggregate findings by check type
        findings_by_check = {}
        
        # Parse each finding
        for detector in detectors:
            impact = detector.get('impact', 'Unknown').capitalize()
            confidence = detector.get('confidence', 'Unknown').capitalize()
            check = detector.get('check', 'unknown')
            description = detector.get('description', '').strip()
            
            # Simplify finding object (remove massive source mappings)
            simplified_finding = {
                'check': check,
                'impact': impact,
                'confidence': confidence,
                'description': description,
                'first_markdown_element': detector.get('first_markdown_element', ''),
            }
            
            # Extract line numbers if available
            elements = detector.get('elements', [])
            if elements:
                # Get line numbers from first element
                source_mapping = elements[0].get('source_mapping', {})
                lines = source_mapping.get('lines', [])
                if lines:
                    simplified_finding['lines'] = lines
            
            # Categorize by severity
            if impact in findings_by_severity:
                findings_by_severity[impact].append(simplified_finding)
            
            # Count by check type
            findings_by_check[check] = findings_by_check.get(check, 0) + 1
        
        # Calculate totals
        total_findings = sum(len(v) for v in findings_by_severity.values())
        
        return {
            'success': data.get('success', False),
            'total_findings': total_findings,
            'findings_by_severity': {
                k: len(v) for k, v in findings_by_severity.items()
            },
            'findings_by_check': findings_by_check,
            'findings': [
                *findings_by_severity['High'],
                *findings_by_severity['Medium'],
                *findings_by_severity['Low'],
                *findings_by_severity['Informational'],
                *findings_by_severity['Optimization']
            ],
            'metadata': {
                'total_contracts': len(results.get('printers', [])),
                'error': data.get('error')
            }
        }
    
    def _empty_result(self, reason: str) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            'success': False,
            'total_findings': 0,
            'findings_by_severity': {
                'High': 0, 'Medium': 0, 'Low': 0, 
                'Informational': 0, 'Optimization': 0
            },
            'findings_by_check': {},
            'findings': [],
            'metadata': {'error': reason}
        }



