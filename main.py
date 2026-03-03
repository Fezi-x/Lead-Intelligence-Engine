import sys
import os
import time
import json
import logging
from extractor import Extractor
from rag import RAG
from evaluator import Evaluator
from coda_client import CodaClient
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main(url):
    start_total = time.time()
    
    try:
        # 1. Extraction
        logger.info(f"Starting extraction for URL: {url}")
        extractor = Extractor()
        extracted_data = extractor.process(url)
        content = extracted_data["text"]
        logger.info(f"Extraction complete. Chars: {extracted_data['char_count']}, Latency: {extracted_data['latency_fetch']:.2f}s")
        
        # 2. RAG Retrieval
        logger.info("Retrieving RAG context...")
        rag_context = []
        try:
            rag = RAG()
            rag_context = rag.retrieve(content)
            logger.info(f"RAG complete. Items retrieved: {len(rag_context)}")
        except Exception as e:
            logger.warning(f"RAG failed (continuing without it): {e}")

        # 3. Evaluation
        logger.info("Starting LLM evaluation...")
        evaluator = Evaluator()
        result = evaluator.evaluate(content, rag_context=rag_context)
        logger.info(f"Evaluation complete. Service: {result.get('primary_service')}, Score: {result.get('fit_score')}")

        # 4. Save to Coda
        logger.info("Saving results to Coda...")
        coda = CodaClient()
        # Merge basic url info into result for Coda
        result["url"] = url
        coda_res = coda.insert_row(result)
        logger.info("Saved to Coda successfully.")

        total_latency = time.time() - start_total
        logger.info(f"Total end-to-end latency: {total_latency:.2f}s")
        
        # Performance check
        if total_latency > 20:
             logger.warning("Total latency exceeded 20s limit!")

        print("\n--- Final Evaluation ---")
        print(json.dumps(result, indent=2))
        print("------------------------")

    except Exception as e:
        logger.error(f"Process failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <url>")
        sys.exit(1)
    
    input_url = sys.argv[1]
    main(input_url)
