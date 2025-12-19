from typing import List, Dict
from pathlib import Path
import time

from analyzer.core.contract import Contract, Language
from analyzer.core.result import AnalysisResult
from analyzer.tools.base import BaseTool
from analyzer.config import Config
from analyzer.utils.logger import setup_logger
from analyzer.parsers import get_parser

class Analyzer:
    """Orchestrates analysis with language-aware tool filtering"""
    
    def __init__(self, tools: List[BaseTool]):
        self.tools = tools
        self.logger = setup_logger('analyzer')
        Config.ensure_directories()
    
    def analyze_single(self, contract: Contract) -> Dict[str, AnalysisResult]:
        """Analyze single contract with compatible tools"""
        self.logger.info(f"Analyzing {contract.name} ({contract.language.value})")
        
        results = {}
        
        for tool in self.tools:
            # CRITICAL: Skip incompatible tools
            if contract.language not in tool.supported_languages:
                self.logger.info(
                    f"Skipping {tool.name} - doesn't support {contract.language.value}"
                )
                continue
            
            if not tool.is_available():
                self.logger.warning(f"{tool.name} not available")
                continue
            
            self.logger.info(f"Running {tool.name}...")
            start = time.time()
            
            success, stdout, stderr = tool.run(contract)
            elapsed = time.time() - start
            
            result = AnalysisResult(
                contract_name=contract.name,
                contract_path=str(contract.path),
                tool=tool.name,
                success=success,
                execution_time=elapsed,
                raw_stdout=stdout,
                raw_stderr=stderr,
                error_message=None if success else "Tool execution failed"
            )
            
            # Parse results if parser available
            parser = get_parser(tool.name)
            if parser:
                self.logger.info(f"Parsing {tool.name} results...")
                result.parsed = parser.parse(stdout, stderr)
                self.logger.info(
                    f"Found {result.parsed.get('total_findings', 0)} findings"
                )
            
            self.logger.info(f"{tool.name} completed in {elapsed:.2f}s")
            
            results[tool.name] = result
            
            # Save both raw and parsed
            result.save_raw(Config.RAW_RESULTS_DIR / tool.name)
            if result.parsed:
                result.save_parsed(Config.PARSED_RESULTS_DIR / tool.name)
        
        return results
    
    def analyze_batch(self, contracts: List[Contract]) -> List[Dict[str, AnalysisResult]]:
        """Analyze multiple contracts"""
        self.logger.info(f"Starting batch analysis: {len(contracts)} contracts")
        
        all_results = []
        for i, contract in enumerate(contracts, 1):
            self.logger.info(f"Contract {i}/{len(contracts)}: {contract.name}")
            results = self.analyze_single(contract)
            all_results.append(results)
        
        self.logger.info("Batch analysis complete")
        return all_results
