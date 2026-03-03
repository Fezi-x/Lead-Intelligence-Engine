import sys
import json
import logging
from core import LeadEngine

# CLI should be minimal
logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)

def main(url):
    engine = LeadEngine()
    try:
        print(f"Analyzing {url}...")
        result = engine.process_url(url)
        
        print("\n--- Evaluation Result ---")
        clean_result = {k: v for k, v in result.items() if not k.startswith("_")}
        print(json.dumps(clean_result, indent=2))
        print("------------------------")

        if result.get("_status") == "success":
            print(f"SUCCESS: ADDED TO CRM: '{result['business_name']}' ({url})")
            print(f"Latency: {result.get('_latency')}")
            if "_usage" in result:
                u = result["_usage"]
                print(f"Usage: {u['total_tokens']} tokens (P: {u['prompt_tokens']}, C: {u['completion_tokens']})")
        else:
            reason = result.get("_message", "Unknown reason")
            print(f"SKIPPED CRM INSERTION: {url}")
            print(f"Reason: {reason}")

    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <url>")
        sys.exit(1)
    
    input_url = sys.argv[1]
    main(input_url)
