import os
import requests
from dotenv import load_dotenv

load_dotenv()

class CodaClient:
    def __init__(self):
        self.api_token = os.getenv("CODA_API_TOKEN")
        self.doc_id = os.getenv("CODA_DOC_ID")
        self.table_id = os.getenv("CODA_TABLE_ID")
        
        if not all([self.api_token, self.doc_id, self.table_id]):
            # We allow initialization but methods will fail if missing
            pass

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def insert_row(self, evaluation_data):
        """
        Inserts evaluation data into the Coda table.
        Mapping evaluation fields to Coda columns (assuming column names/IDs match or require mapping).
        """
        if not all([self.api_token, self.doc_id, self.table_id]):
            raise ValueError("Coda configuration (Token, Doc ID, Table ID) is incomplete in .env.")

        url = f"https://coda.io/apis/v1/docs/{self.doc_id}/tables/{self.table_id}/rows"
        
        # Construct the row payload
        # Note: In Coda API, you usually specify columns by ID or Name. 
        # For simplicity, we'll try using names that match the JSON output.
        row_payload = {
            "rows": [
                {
                    "cells": [
                        {"column": "Business URL", "value": evaluation_data.get("url")},
                        {"column": "Business Type", "value": evaluation_data.get("business_type")},
                        {"column": "Primary Service", "value": evaluation_data.get("primary_service")},
                        {"column": "Fit Score", "value": evaluation_data.get("fit_score")},
                        {"column": "Reasoning", "value": evaluation_data.get("reasoning")},
                        {"column": "Outreach Angle", "value": evaluation_data.get("outreach_angle")}
                    ]
                }
            ]
        }

        try:
            response = requests.post(url, headers=self._get_headers(), json=row_payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to insert row into Coda: {str(e)}")

if __name__ == "__main__":
    # Test with mockup (requires .env config)
    client = CodaClient()
    mock_data = {
        "url": "https://test.com",
        "business_type": "Test Business",
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
