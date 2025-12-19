#!/usr/bin/env python3
"""
De.Fi Rekt Database Exporter
=============================
Fetches all exploit records from De.Fi API and exports to CSV for ecosystem analysis.

Features:
- Automatic checkpoint/resume on interruption or rate limiting
- GraphQL-specific error handling
- API call tracking (respects 1000/month quota)
- Raw data export with no preprocessing

Usage:
    python scripts/export_defi_ecosystem.py [--verbose] [--force] [--dry-run]
"""

import os
import sys
import json
import csv
import time
import pickle
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv


# ============================================================================
# Configuration
# ============================================================================

API_URL = "https://public-api.de.fi/graphql"
PAGE_SIZE = 50  # De.Fi max page size
RATE_LIMIT_DELAY = 0.7  # Seconds between API calls
REQUEST_TIMEOUT = 30  # Seconds

# Output paths
OUTPUT_DIR = Path("static_analysis_results/ecosystem_analysis")
CSV_OUTPUT = OUTPUT_DIR / "defi_rekt_raw.csv"
METADATA_OUTPUT = OUTPUT_DIR / "fetch_metadata.json"
LOG_OUTPUT = OUTPUT_DIR / "fetch_log.txt"
CHECKPOINT_FILE = OUTPUT_DIR / "fetch.checkpoint.pkl"


# ============================================================================
# GraphQL Query
# ============================================================================

REKTS_QUERY = """
query($p: Int!, $s: Int!) {
  rekts(pageNumber: $p, pageSize: $s) {
    projectName
    date
    fundsLost
    fundsReturned
    chaindIds
    category
    issueType
    description
  }
}
"""


# ============================================================================
# Checkpoint System
# ============================================================================

class FetchCheckpoint:
    """Checkpoint for resuming interrupted fetches."""

    def __init__(self):
        self.records: List[Dict] = []
        self.current_page: int = 1
        self.api_calls_made: int = 0
        self.pages_fetched: List[Dict] = []
        self.errors: List[Dict] = []
        self.start_time: str = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        # Track completion status
        self.completion_status: Optional[str] = None  # "completed", "rate_limited", "error", "interrupted"
        self.completion_reason: Optional[str] = None  # Human-readable reason

    def save(self, filepath: Path):
        """Save checkpoint to disk."""
        with open(filepath, 'wb') as f:
            pickle.dump(self, f)

    @staticmethod
    def load(filepath: Path) -> Optional['FetchCheckpoint']:
        """Load checkpoint from disk."""
        if not filepath.exists():
            return None

        try:
            with open(filepath, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"failed to load checkpoint: {e}")
            return None

    def add_page(self, page_num: int, records: List[Dict], status: str):
        """Add a page result to checkpoint."""
        self.records.extend(records)
        self.current_page = page_num + 1  # Next page to fetch
        self.api_calls_made += 1

        self.pages_fetched.append({
            "page_number": page_num,
            "records_fetched": len(records),
            "api_call_time": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "status": status
        })

    def add_error(self, page_num: int, error_msg: str, 
                  error_type: Optional[str] = None,
                  http_status: Optional[int] = None,
                  response_body: Optional[str] = None,
                  response_headers: Optional[Dict] = None):
        """Record an error with full details."""
        error_record = {
            "page_number": page_num,
            "error": error_msg,
            "error_type": error_type,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
        
        if http_status:
            error_record["http_status"] = http_status
        
        if response_body:
            error_record["response_body"] = response_body[:500]  # First 500 chars
        
        if response_headers:
            # Capture relevant headers (especially Retry-After for rate limits)
            relevant_headers = {}
            if 'Retry-After' in response_headers:
                relevant_headers['Retry-After'] = response_headers['Retry-After']
            if 'X-RateLimit-Remaining' in response_headers:
                relevant_headers['X-RateLimit-Remaining'] = response_headers['X-RateLimit-Remaining']
            if 'X-RateLimit-Reset' in response_headers:
                relevant_headers['X-RateLimit-Reset'] = response_headers['X-RateLimit-Reset']
            if relevant_headers:
                error_record["response_headers"] = relevant_headers
        
        self.errors.append(error_record)


# ============================================================================
# API Client
# ============================================================================

class DeFiAPIClient:
    """Client for De.Fi GraphQL API."""

    def __init__(self, api_key: str, timeout: int = REQUEST_TIMEOUT):
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }

    def fetch_rekts_page(self, page: int, page_size: int = PAGE_SIZE) -> Tuple[bool, Optional[List[Dict]], Optional[str], Optional[Dict]]:
        """
        Fetch a single page of rekts data.

        Returns:
            (success, data, error_message, error_details)
            error_details: {"type": str, "http_status": int, "response_body": str, "headers": dict}
        """
        variables = {"p": page, "s": page_size}
        payload = {
            "query": REKTS_QUERY,
            "variables": variables
        }

        try:
            response = requests.post(
                API_URL,
                json=payload,
                headers=self.headers,
                timeout=self.timeout
            )

            # Check HTTP status
            if response.status_code == 401:
                return (False, None, "Invalid API key (401 Unauthorized)", {
                    "type": "auth_error",
                    "http_status": 401,
                    "response_body": response.text[:500],
                    "headers": dict(response.headers)
                })

            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After', 'unknown')
                return (False, None, f"Rate limit exceeded (429 Too Many Requests) - Retry-After: {retry_after}", {
                    "type": "rate_limit",
                    "http_status": 429,
                    "response_body": response.text[:500],
                    "headers": {
                        "Retry-After": retry_after,
                        **{k: v for k, v in response.headers.items() if 'rate' in k.lower()}
                    }
                })

            if response.status_code != 200:
                return (False, None, f"HTTP {response.status_code}: {response.text[:200]}", {
                    "type": "http_error",
                    "http_status": response.status_code,
                    "response_body": response.text[:500],
                    "headers": dict(response.headers)
                })

            # Parse JSON
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                return (False, None, f"Invalid JSON response: {str(e)}", {
                    "type": "json_error",
                    "http_status": 200,
                    "response_body": response.text[:500],
                    "headers": dict(response.headers)
                })

            # Check for GraphQL errors
            if "errors" in data:
                error_msgs = [err.get("message", str(err)) for err in data["errors"]]
                return (False, None, f"GraphQL errors: {', '.join(error_msgs)}", {
                    "type": "graphql_error",
                    "http_status": 200,  # HTTP was OK but GraphQL had errors
                    "response_body": json.dumps(data.get("errors", []))[:500],
                    "headers": dict(response.headers)
                })

            # Check for data field
            if "data" not in data:
                return (False, None, "Response missing 'data' field", {
                    "type": "api_error",
                    "http_status": 200,
                    "response_body": json.dumps(data)[:500],
                    "headers": dict(response.headers)
                })

            if data["data"] is None:
                return (False, None, "API returned null data", {
                    "type": "api_error",
                    "http_status": 200,
                    "response_body": json.dumps(data)[:500],
                    "headers": dict(response.headers)
                })

            # Extract rekts
            if "rekts" not in data["data"]:
                return (False, None, "Response missing 'rekts' field in data", {
                    "type": "api_error",
                    "http_status": 200,
                    "response_body": json.dumps(data)[:500],
                    "headers": dict(response.headers)
                })

            records = data["data"]["rekts"]

            # Validate records is a list
            if not isinstance(records, list):
                return (False, None, f"Expected list of records, got {type(records)}", {
                    "type": "api_error",
                    "http_status": 200,
                    "response_body": json.dumps(data)[:500],
                    "headers": dict(response.headers)
                })

            return (True, records, None, None)

        except requests.exceptions.Timeout:
            return (False, None, f"Request timeout after {self.timeout}s", {
                "type": "timeout",
                "http_status": None,
                "response_body": None,
                "headers": None
            })

        except requests.exceptions.ConnectionError:
            return (False, None, "Connection failed - check your internet connection", {
                "type": "connection_error",
                "http_status": None,
                "response_body": None,
                "headers": None
            })

        except requests.exceptions.RequestException as e:
            return (False, None, f"Request error: {str(e)}", {
                "type": "request_error",
                "http_status": None,
                "response_body": None,
                "headers": None
            })

        except Exception as e:
            return (False, None, f"Unexpected error: {str(e)}", {
                "type": "unexpected_error",
                "http_status": None,
                "response_body": None,
                "headers": None
            })

    @staticmethod
    def rate_limit(delay: float = RATE_LIMIT_DELAY):
        """Rate limiting between requests."""
        time.sleep(delay)


# ============================================================================
# Exporter
# ============================================================================

class DeFiExporter:
    """Orchestrates fetching and exporting De.Fi data."""

    def __init__(self, client: DeFiAPIClient, verbose: bool = False):
        self.client = client
        self.verbose = verbose
        self.checkpoint: FetchCheckpoint = FetchCheckpoint()

    def log(self, message: str, file_only: bool = False):
        """Log to console and file."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"{timestamp} - {message}\n"

        # Always log to file
        with open(LOG_OUTPUT, 'a', encoding='utf-8') as f:
            f.write(log_msg)

        # Console output
        if not file_only:
            print(message)

    def fetch_all_records(self, resume: bool = True) -> bool:
        """
        Fetch all records from De.Fi API with checkpoint/resume support.

        Returns:
            True if successful, False if failed
        """
        # Try to resume from checkpoint
        if resume and CHECKPOINT_FILE.exists():
            loaded = FetchCheckpoint.load(CHECKPOINT_FILE)
            if loaded:
                self.checkpoint = loaded
                self.log(f"resuming from checkpoint: page {self.checkpoint.current_page}, {len(self.checkpoint.records)} records")

        page = self.checkpoint.current_page

        self.log(f"fetching de.fi rekt database (starting at page {page})")

        while True:
            # Fetch page
            success, records, error, error_details = self.client.fetch_rekts_page(page, PAGE_SIZE)

            if not success:
                self.log(f"page {page} failed: {error}")
                
                # Enhanced error tracking with details
                error_type = error_details.get("type", "unknown") if error_details else "unknown"
                self.checkpoint.add_error(
                    page, 
                    error,
                    error_type=error_type,
                    http_status=error_details.get("http_status") if error_details else None,
                    response_body=error_details.get("response_body") if error_details else None,
                    response_headers=error_details.get("headers") if error_details else None
                )
                self.checkpoint.save(CHECKPOINT_FILE)

                # Set completion status based on error type
                if error_type == "rate_limit":
                    retry_after = error_details.get("headers", {}).get("Retry-After", "unknown") if error_details else "unknown"
                    self.checkpoint.completion_status = "rate_limited"
                    self.checkpoint.completion_reason = f"Rate limited at page {page}. Retry-After: {retry_after}"
                    self.checkpoint.save(CHECKPOINT_FILE)
                    self.log("rate limited - checkpoint saved, run script again to resume")
                    return False

                # For other errors, stop
                self.checkpoint.completion_status = "error"
                self.checkpoint.completion_reason = f"Fatal error at page {page}: {error}"
                self.checkpoint.save(CHECKPOINT_FILE)
                self.log("fatal error - stopping fetch")
                return False

            # Empty results = end of data
            if not records:
                self.checkpoint.completion_status = "completed"
                self.checkpoint.completion_reason = f"All pages fetched successfully. Empty page {page} indicates end of data."
                self.checkpoint.save(CHECKPOINT_FILE)
                self.log(f"page {page}: no more records (end of data)")
                break

            # Add to checkpoint
            self.checkpoint.add_page(page, records, "success")

            # Progress output
            quota_pct = (self.checkpoint.api_calls_made / 1000) * 100
            self.log(
                f"page {page}: +{len(records)} records | "
                f"total: {len(self.checkpoint.records)} | "
                f"api calls: {self.checkpoint.api_calls_made}/1000 ({quota_pct:.1f}%)"
            )

            if self.verbose:
                self.log(f"   Sample record: {records[0].get('projectName', 'N/A')}", file_only=True)

            # Save checkpoint after each page
            self.checkpoint.save(CHECKPOINT_FILE)

            # Check if last page (fewer records than page size)
            if len(records) < PAGE_SIZE:
                self.checkpoint.completion_status = "completed"
                self.checkpoint.completion_reason = f"All pages fetched successfully. Last page {page} had {len(records)} records (< {PAGE_SIZE})."
                self.checkpoint.save(CHECKPOINT_FILE)
                self.log(f"last page reached ({len(records)} < {PAGE_SIZE})")
                break

            # Rate limiting before next page
            page += 1
            self.client.rate_limit()

        # Success path
        self.checkpoint.completion_status = "completed"
        self.checkpoint.completion_reason = f"Successfully fetched all {len(self.checkpoint.records)} records across {len(self.checkpoint.pages_fetched)} pages."
        self.checkpoint.save(CHECKPOINT_FILE)
        self.log(f"\nfetch complete - total records: {len(self.checkpoint.records)}")
        return True

    def export_to_csv(self) -> bool:
        """Export records to CSV."""
        if not self.checkpoint.records:
            self.log("no records to export")
            return False

        self.log(f"\nexporting {len(self.checkpoint.records)} records to csv")

        fieldnames = [
            'projectName',
            'date',
            'fundsLost',
            'fundsReturned',
            'chainIds',
            'category',
            'issueType',
            'description'
        ]

        try:
            with open(CSV_OUTPUT, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for record in self.checkpoint.records:
                    # Convert chainIds list to JSON string
                    record_copy = record.copy()
                    record_copy['chainIds'] = json.dumps(record.get('chaindIds', []))

                    # Remove the original chaindIds field
                    record_copy.pop('chaindIds', None)

                    writer.writerow(record_copy)

            file_size_kb = CSV_OUTPUT.stat().st_size / 1024
            self.log(f"exported to: {CSV_OUTPUT}")
            self.log(f"   Size: {file_size_kb:.1f} KB")
            return True

        except Exception as e:
            self.log(f"csv export failed: {e}")
            return False

    def save_metadata(self):
        """Save fetch metadata to JSON."""
        metadata = {
            "fetch_date": self.checkpoint.start_time,
            "completion_date": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "completion_status": self.checkpoint.completion_status,
            "completion_reason": self.checkpoint.completion_reason,
            "api_calls_made": self.checkpoint.api_calls_made,
            "total_records": len(self.checkpoint.records),
            "pages_fetched": len(self.checkpoint.pages_fetched),
            "success": self.checkpoint.completion_status == "completed",
            "pages": self.checkpoint.pages_fetched,
            "errors": self.checkpoint.errors,
            "error_summary": {
                "total": len(self.checkpoint.errors),
                "by_type": {}
            },
            "rate_limit": {
                "delay_seconds": RATE_LIMIT_DELAY,
                "total_wait_time": max(0, (self.checkpoint.api_calls_made - 1)) * RATE_LIMIT_DELAY
            },
            "config": {
                "page_size": PAGE_SIZE,
                "api_url": API_URL,
                "timeout": REQUEST_TIMEOUT
            }
        }
        
        # Calculate error summary
        for error in self.checkpoint.errors:
            error_type = error.get("error_type", "unknown")
            metadata["error_summary"]["by_type"][error_type] = \
                metadata["error_summary"]["by_type"].get(error_type, 0) + 1

        with open(METADATA_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        self.log(f"metadata saved to: {METADATA_OUTPUT}")

    def print_summary(self):
        """Print final summary."""
        quota_pct = (self.checkpoint.api_calls_made / 1000) * 100
        
        status_text = {
            "completed": "completed",
            "rate_limited": "rate limited",
            "error": "error",
            "interrupted": "interrupted"
        }.get(self.checkpoint.completion_status, "unknown")

        print("\n" + "="*60)
        print("export summary")
        print("="*60)
        print(f"status:            {status_text}")
        if self.checkpoint.completion_reason:
            print(f"reason:            {self.checkpoint.completion_reason}")
        print(f"total records:     {len(self.checkpoint.records)}")
        print(f"pages fetched:     {len(self.checkpoint.pages_fetched)}")
        print(f"api calls used:    {self.checkpoint.api_calls_made}/1000 ({quota_pct:.1f}%)")
        
        total_attempts = len(self.checkpoint.pages_fetched) + len(self.checkpoint.errors)
        if total_attempts > 0:
            print(f"success rate:      {len(self.checkpoint.pages_fetched)}/{total_attempts}")
        else:
            print(f"success rate:      n/a")

        if self.checkpoint.errors:
            print(f"\nerrors: {len(self.checkpoint.errors)}")
            # Group errors by type
            errors_by_type = {}
            for error in self.checkpoint.errors:
                error_type = error.get("error_type", "unknown")
                if error_type not in errors_by_type:
                    errors_by_type[error_type] = []
                errors_by_type[error_type].append(error)
            
            for error_type, error_list in errors_by_type.items():
                print(f"   {error_type}: {len(error_list)}")
                for error in error_list[:3]:  # Show first 3 of each type
                    print(f"      - Page {error['page_number']}: {error['error']}")
                if len(error_list) > 3:
                    print(f"      ... and {len(error_list) - 3} more")

        print(f"\noutput files:")
        print(f"   csv:      {CSV_OUTPUT}")
        print(f"   metadata: {METADATA_OUTPUT}")
        print(f"   log:      {LOG_OUTPUT}")
        print("="*60)

    def cleanup_checkpoint(self):
        """Remove checkpoint file after successful completion."""
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
            self.log("checkpoint file cleaned up")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Export De.Fi Rekt Database to CSV for ecosystem analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/export_defi_ecosystem.py
  python scripts/export_defi_ecosystem.py --verbose
  python scripts/export_defi_ecosystem.py --force

Environment:
  Requires DEFI_API_KEY in .env file
        """
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose logging output'
    )

    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force re-fetch even if data exists (ignores checkpoint)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate setup without making API calls'
    )

    args = parser.parse_args()

    # Load environment variables
    print("loading environment configuration")
    load_dotenv()

    # Check API key
    api_key = os.getenv("DEFI_API_KEY")
    if not api_key:
        print("error: DEFI_API_KEY not found in environment")
        print("\nsetup instructions:")
        print("  1. copy .env.example to .env")
        print("  2. add your de.fi api key to .env")
        print("  3. run script again")
        sys.exit(1)

    print("api key loaded")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize log file
    if not args.force and LOG_OUTPUT.exists():
        # Append to existing log
        pass
    else:
        # Start fresh log
        LOG_OUTPUT.write_text(f"=== De.Fi Export Log - {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')} ===\n\n")

    # Dry run mode
    if args.dry_run:
        print("\ndry run mode - no api calls will be made")
        print(f"   api url: {API_URL}")
        print(f"   page size: {PAGE_SIZE}")
        print(f"   rate limit: {RATE_LIMIT_DELAY}s")
        print(f"   output dir: {OUTPUT_DIR}")
        print("configuration valid")
        sys.exit(0)

    # Check if we should force restart
    if args.force and CHECKPOINT_FILE.exists():
        print("force mode: removing existing checkpoint")
        CHECKPOINT_FILE.unlink()

    # Check if data already exists
    if CSV_OUTPUT.exists() and not CHECKPOINT_FILE.exists():
        print(f"\ndata already exists: {CSV_OUTPUT}")
        response = input("    re-fetch data? this will use api quota. (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("aborted")
            sys.exit(0)

    # Create client and exporter
    client = DeFiAPIClient(api_key, timeout=REQUEST_TIMEOUT)
    exporter = DeFiExporter(client, verbose=args.verbose)

    # Fetch all records
    fetch_success = exporter.fetch_all_records(resume=not args.force)

    if not fetch_success:
        print("\nfetch incomplete - checkpoint saved")
        if exporter.checkpoint.completion_status:
            print(f"   status: {exporter.checkpoint.completion_status}")
            if exporter.checkpoint.completion_reason:
                print(f"   reason: {exporter.checkpoint.completion_reason}")
        print("   run script again to resume from checkpoint")
        sys.exit(1)

    # Export to CSV
    export_success = exporter.export_to_csv()

    if not export_success:
        print("\nexport failed")
        sys.exit(1)

    # Save metadata
    exporter.save_metadata()

    # Print summary
    exporter.print_summary()

    # Clean up checkpoint
    exporter.cleanup_checkpoint()

    print("\ndone")


if __name__ == "__main__":
    main()
