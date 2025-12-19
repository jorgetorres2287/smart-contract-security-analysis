#!/usr/bin/env python3
"""
etherscan api client for fetching smart contract source code
handles multiple chains: ethereum, bsc, polygon, arbitrum, optimism, base
"""

import requests
import json
import time
from typing import Dict, Optional, Tuple
from enum import Enum

class Chain(Enum):
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"

# unified v2 api endpoint (works for all 60+ chains)
API_ENDPOINT = "https://api.etherscan.io/v2/api"

# chain ids for v2 api (used with unified endpoint)
CHAIN_IDS = {
    Chain.ETHEREUM: "1",
    Chain.ARBITRUM: "42161",
    Chain.OPTIMISM: "10",
    Chain.BASE: "8453",
}

EXPLORER_URLS = {
    Chain.ETHEREUM: "https://etherscan.io/address/",
    Chain.ARBITRUM: "https://arbiscan.io/address/",
    Chain.OPTIMISM: "https://optimistic.etherscan.io/address/",
    Chain.BASE: "https://basescan.org/address/",
}

class EtherscanClient:
    """client for interacting with etherscan unified v2 api"""
    
    def __init__(self, api_key: str, timeout: int = 30):
        """
        initialize client with unified api key (works for all chains)
        
        args:
            api_key: single api key for all chains (get at https://etherscan.io/myapikey)
            timeout: request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
    
    def fetch_source_code(self, address: str, chain: Chain) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        fetch contract source code from blockchain explorer using unified v2 api
        
        args:
            address: contract address (0x...)
            chain: blockchain to query
        
        returns:
            (success: bool, data: dict or None, error_message: str or None)
        """
        
        chain_id = CHAIN_IDS.get(chain)
        
        if not chain_id:
            return False, None, f"no chain id configured for {chain.value}"
        
        if not self.api_key:
            return False, None, "no api key provided"
        
        # unified v2 api: single endpoint, chainid parameter selects chain
        params = {
            'chainid': chain_id,
            'module': 'contract',
            'action': 'getsourcecode',
            'address': address,
            'apikey': self.api_key
        }
        
        try:
            response = requests.get(API_ENDPOINT, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != '1':
                return False, None, f"api error: {data.get('message', 'unknown error')}"
            
            result = data['result'][0]
            source_code = result.get('SourceCode', '')
            
            if not source_code:
                return False, None, "contract not verified on explorer"
            
            # handle multi-file contracts (json format)
            if source_code.startswith('{{'):
                source_code = self._extract_main_contract(source_code, result.get('ContractName', ''))
                if not source_code:
                    return False, None, "could not extract main contract from multi-file source"
            
            # return full result data
            return True, result, None
            
        except requests.exceptions.Timeout:
            return False, None, "request timeout"
        except requests.exceptions.RequestException as e:
            return False, None, f"network error: {str(e)}"
        except Exception as e:
            return False, None, f"unexpected error: {str(e)}"
    
    def _extract_main_contract(self, source_code: str, contract_name: str) -> str:
        """
        extract main contract file from multi-file json format
        
        args:
            source_code: json string with multiple files
            contract_name: name of the contract to find
        
        returns:
            source code string or empty string if not found
        """
        try:
            # remove outer braces
            source_code = source_code[1:-1]
            sources = json.loads(source_code)
            
            if 'sources' not in sources:
                return ""
            
            # try to find the main contract file
            for file_path, file_data in sources['sources'].items():
                if contract_name in file_path or 'contract' in file_path.lower():
                    return file_data.get('content', '')
            
            # fallback: return first file
            first_file = list(sources['sources'].values())[0]
            return first_file.get('content', '')
            
        except (json.JSONDecodeError, KeyError, IndexError):
            return ""
    
    def get_explorer_url(self, address: str, chain: Chain) -> str:
        """
        get block explorer url for a contract
        
        args:
            address: contract address
            chain: blockchain
        
        returns:
            full url to block explorer
        """
        base_url = EXPLORER_URLS.get(chain, "")
        return f"{base_url}{address}"
    
    @staticmethod
    def rate_limit(delay: float = 0.3):
        """
        sleep to respect api rate limits
        most explorers allow ~5 requests/second
        
        args:
            delay: seconds to sleep (default 0.3s = ~3 req/s)
        """
        time.sleep(delay)
    
    def validate_address(self, address: str) -> bool:
        """
        validate ethereum address format
        
        args:
            address: address string to validate
        
        returns:
            true if valid ethereum address format
        """
        if not address:
            return False
        if not address.startswith('0x'):
            return False
        if len(address) != 42:
            return False
        try:
            int(address[2:], 16)
            return True
        except ValueError:
            return False