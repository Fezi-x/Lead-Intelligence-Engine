import time
import json
import logging
from extractor import Extractor
from rag import RAG
from evaluator import Evaluator
from coda_client import CodaClient

# Configure logging to be less noisy
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LeadEngine:
    def __init__(self):
        self.extractor = Extractor()
        self.evaluator = Evaluator()
        self.coda = CodaClient()
        self.rag = RAG()

    def process_url(self, url):
        """
        Processes a URL: extracts text, evaluates matching services, and saves to Coda.
        Returns the result dictionary or raises an exception.
        """
        start_time = time.time()
        
        try:
            # 1. Extraction
            extracted_data = self.extractor.process(url)
            if "error" in extracted_data:
                raise Exception(extracted_data["error"])
            
            content = extracted_data.get("text", "")
            if not content:
                raise Exception("No content could be extracted from the URL.")
            
            # 2. RAG Retrieval
            rag_context = []
            try:
                rag_context = self.rag.retrieve(content)
            except Exception as e:
                logger.warning(f"RAG retrieval partially failed: {e}")
                # We continue even if RAG fails

            # 3. Evaluation
            try:
                result = self.evaluator.evaluate(content, rag_context=rag_context)
                result["url"] = url
                # Move usage to metadata if present
                if "_usage" in result:
                    result["_usage"] = result.pop("_usage")
            except Exception as e:
                raise Exception(f"AI Evaluation failed: {str(e)}")

            # 4. Save to Coda
            try:
                # Check for duplicates first
                if self.coda.fetch_row_by_url(url):
                    result["_status"] = "skipped"
                    result["_message"] = "Duplicate found in CRM"
                    return result

                self.coda.insert_row(result)
            except Exception as e:
                raise Exception(f"Database/Coda sync failed: {str(e)}")

            result["_status"] = "success"
            
            latency = time.time() - start_time
            result["_latency"] = f"{latency:.2f}s"
            
            return result

        except Exception as e:
            # Log the full error but raise a cleaned up message
            logger.error(f"LeadEngine error for {url}: {e}")
            raise e

if __name__ == "__main__":
    # Quick test
    engine = LeadEngine()
    try:
        res = engine.process_url("https://example.com")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Test failed: {e}")
