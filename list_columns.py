import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

def list_docs():
    api_token = os.getenv("CODA_API_TOKEN")
    url = "https://coda.io/apis/v1/docs"
    headers = {"Authorization": f"Bearer {api_token}"}
    
    print("Listing accessible Docs to verify API Token...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        docs = response.json().get("items", [])
        print("\nAccessible Docs:")
        for doc in docs:
            print(f"- {doc['name']} (ID: {doc['id']})")
        return docs
    except Exception as e:
        print(f"Token Verification Failed: {e}")
        return None

def list_columns():
    api_token = os.getenv("CODA_API_TOKEN")
    doc_id = os.getenv("CODA_DOC_ID")
    table_id = os.getenv("CODA_TABLE_ID")
    
    # Check if doc_id looks like a slug or ID
    # su7aO7Bp was used in your curl, but Test-Table-LIE_su7aO7Bp is in .env
    
    url = f"https://coda.io/apis/v1/docs/{doc_id}/tables/{table_id}/columns"
    headers = {"Authorization": f"Bearer {api_token}"}
    
    print(f"\nAttempting to fetch columns for:")
    print(f"- Doc ID: {doc_id}")
    print(f"- Table ID: {table_id}")
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        columns = response.json().get("items", [])
        print("\nSUCCESS! Existing Columns:")
        for col in columns:
            print(f"- Name: {col['name']} (ID: {col['id']})")
    except Exception as e:
        print(f"\nFAILED: {e}")
        if "404" in str(e):
            print("\nPossible reasons for 404:")
            print("1. The Doc ID is wrong.")
            print("2. The Table ID is wrong.")
            print("3. The API Token doesn't have access to this doc.")
            list_docs()

if __name__ == "__main__":
    list_columns()

if __name__ == "__main__":
    list_columns()
