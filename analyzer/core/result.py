from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path
import json

@dataclass
class AnalysisResult:
    """Analysis results with optional parsed data"""
    
    contract_name: str
    contract_path: str
    tool: str
    success: bool
    execution_time: float  # seconds
    
    # Store RAW outputs for later parsing
    raw_stdout: str
    raw_stderr: str
    error_message: Optional[str] = None
    
    # Parsed results (optional)
    parsed: Optional[Dict[str, Any]] = field(default=None)
    
    def to_dict(self) -> dict:
        base = {
            'contract_name': self.contract_name,
            'contract_path': self.contract_path,
            'tool': self.tool,
            'success': self.success,
            'execution_time': self.execution_time,
            'raw_stdout': self.raw_stdout,
            'raw_stderr': self.raw_stderr,
            'error_message': self.error_message,
        }
        
        # Include parsed data if available
        if self.parsed:
            base['parsed'] = self.parsed
        
        return base
    
    def save_raw(self, output_dir: Path):
        """Save raw outputs to files for later parsing"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save stdout (usually JSON)
        if self.raw_stdout:
            stdout_file = output_dir / f"{self.contract_name}_{self.tool}.json"
            stdout_file.write_text(self.raw_stdout)
        
        # Save stderr (logs/errors)
        if self.raw_stderr:
            stderr_file = output_dir / f"{self.contract_name}_{self.tool}_errors.txt"
            stderr_file.write_text(self.raw_stderr)
    
    def save_parsed(self, output_dir: Path):
        """Save parsed results in compact JSON format"""
        if not self.parsed:
            return
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create consolidated output
        output_file = output_dir / f"{self.contract_name}_{self.tool}_parsed.json"
        
        # Compact format with thesis-relevant metadata
        output_data = {
            'contract': self.contract_name,
            'tool': self.tool,
            'execution_time': self.execution_time,
            'analysis': self.parsed
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
