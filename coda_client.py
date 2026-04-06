import os
import requests
import logging
import time
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

load_dotenv()

class CodaClient:
    def __init__(self):
        self.api_token = os.getenv("CODA_API_TOKEN")
        self.doc_id = os.getenv("CODA_DOC_ID")
        self.table_id = os.getenv("CODA_TABLE_ID")
        self._columns_cache = None
        self._columns_cache_time = None
        self._columns_cache_ttl = int(os.getenv("CODA_COLUMNS_CACHE_TTL", "300"))
        
        if not all([self.api_token, self.doc_id, self.table_id]):
            # We allow initialization but methods will fail if missing
            pass

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def _get_columns(self, refresh=False):
        """Fetches the list of columns available in the table."""
        now = time.time()
        if (
            not refresh
            and self._columns_cache is not None
            and self._columns_cache_ttl > 0
            and self._columns_cache_time is not None
            and (now - self._columns_cache_time) < self._columns_cache_ttl
        ):
            return self._columns_cache

        url = f"https://coda.io/apis/v1/docs/{self.doc_id}/tables/{self.table_id}/columns"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            self._columns_cache = [col['name'] for col in response.json().get('items', [])]
            self._columns_cache_time = now
            return self._columns_cache
        except Exception as e:
            logger.error(f"Error fetching columns from Coda: {e}")
            if self._columns_cache is not None:
                return self._columns_cache
            return None

    def _should_refresh_columns(self, error):
        if not hasattr(error, "response") or error.response is None:
            return False
        if error.response.status_code not in (400, 404):
            return False
        body = (error.response.text or "").lower()
        return "column" in body and ("not found" in body or "unknown" in body or "invalid" in body)

    def _post_rows(self, row_payload):
        url = f"https://coda.io/apis/v1/docs/{self.doc_id}/tables/{self.table_id}/rows"
        response = requests.post(url, headers=self._get_headers(), json=row_payload, timeout=15)
        response.raise_for_status()
        return response.json()

    def fetch_row_by_url(self, url):
        """
        Checks if a row with the given Business URL already exists.
        Returns True if exists, False otherwise.
        """
        if not all([self.api_token, self.doc_id, self.table_id]):
            return False

        # Properly quote the URL for the query
        # Coda query format: column_name:"value"
        query = f'"{url}"'
        api_url = f"https://coda.io/apis/v1/docs/{self.doc_id}/tables/{self.table_id}/rows"
        params = {
            "query": f'Business URL:{query}',
            "limit": 1
        }

        try:
            response = requests.get(api_url, headers=self._get_headers(), params=params, timeout=10)
            response.raise_for_status()
            items = response.json().get('items', [])
            return len(items) > 0
        except Exception as e:
            logger.warning(f"Duplicate check failed (Coda API): {e}")
            return False

    def insert_row(self, evaluation_data):
        """
        Inserts evaluation data into the Coda table.
        Mapping evaluation fields to Coda columns, skipping those that don't exist in the table.
        """
        if not all([self.api_token, self.doc_id, self.table_id]):
            raise ValueError("Coda configuration (Token, Doc ID, Table ID) is incomplete in .env.")

        # Get actual columns to be safe
        existing_columns = self._get_columns()
        
        # Define the desired mapping
        desired_cells = [
            {"column": "Business URL", "value": evaluation_data.get("url")},
            {"column": "Business Name", "value": evaluation_data.get("business_name")},
            {"column": "Business Type", "value": evaluation_data.get("business_type")},
            {"column": "Primary Service", "value": evaluation_data.get("primary_service")},
            {"column": "Secondary Service", "value": evaluation_data.get("secondary_service")},
            {"column": "Fit Score", "value": evaluation_data.get("fit_score")},
            {"column": "Reasoning", "value": evaluation_data.get("reasoning")},
            {"column": "Outreach Angle", "value": evaluation_data.get("outreach_angle")}
        ]
        
        # Filter to only existing columns
        cells = desired_cells
        if existing_columns:
            cells = [cell for cell in desired_cells if cell["column"] in existing_columns]
            missing = [cell["column"] for cell in desired_cells if cell["column"] not in existing_columns]
            if missing:
                print(f"Note: Skipping columns missing in Coda table: {', '.join(missing)}")

        # Sanitize values: Coda API rejects null/None. Convert to empty string.
        for cell in cells:
            if cell["value"] is None:
                cell["value"] = ""

        row_payload = {
            "rows": [
                {
                    "cells": cells
                }
            ]
        }

        try:
            return self._post_rows(row_payload)
        except requests.exceptions.RequestException as e:
            if self._should_refresh_columns(e):
                existing_columns = self._get_columns(refresh=True)
                if existing_columns:
                    cells = [cell for cell in desired_cells if cell["column"] in existing_columns]
                else:
                    cells = desired_cells

                for cell in cells:
                    if cell["value"] is None:
                        cell["value"] = ""

                row_payload = {
                    "rows": [
                        {
                            "cells": cells
                        }
                    ]
                }

                try:
                    return self._post_rows(row_payload)
                except requests.exceptions.RequestException as e2:
                    error_detail = ""
                    if hasattr(e2, 'response') and e2.response is not None:
                        error_detail = f" | Details: {e2.response.text[:200]}"
                    raise Exception(f"Coda API Error: {str(e2)}{error_detail}")

            error_detail = ""
            if hasattr(e, 'response') and e.response is not None:
                error_detail = f" | Details: {e.response.text[:200]}"
            raise Exception(f"Coda API Error: {str(e)}{error_detail}")
        except Exception as e:
            raise Exception(f"Coda Row Insertion Failed: {str(e)}")

if __name__ == "__main__":
    # Test with mockup (requires .env config)
    client = CodaClient()
    mock_data = {
        "url": "https://test.com",
        "business_name": "Test Business Name",
        "business_type": "Test Business Type",
        "primary_service": "Test Service",
        "fit_score": 90,
        "reasoning": "Test reasoning",
        "outreach_angle": "Test hook"
    }
    print("Coda client loaded. Set .env variables to test.")
    # try:
    #     res = client.insert_row(mock_data)
    #     print("Insert successful:", res)
    # except Exception as e:
    #     print("Error:", e)
