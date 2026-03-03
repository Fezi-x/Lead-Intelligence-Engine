import os
import json
import logging
from groq import Groq
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

load_dotenv()

class Evaluator:
    # Class-level variables for persistent tracking across instances
    status = "System Online"
    quota_ok = True
    last_run_time = None
    total_usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0
    }

    def __init__(self, model="llama-3.3-70b-versatile"):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables.")
        self.client = Groq(api_key=self.api_key)
        self.model = model
        self.services_path = "services/services.json"
        self.prompt_path = "prompts/system_prompt.md"

    def _load_services(self):
        """Loads the services source of truth."""
        try:
            with open(self.services_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            raise Exception(f"CRITICAL: Failed to load services from {self.services_path}: {e}")

    def _load_prompt(self):
        """Loads the system prompt."""
        try:
            with open(self.prompt_path, 'r') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"CRITICAL: Failed to load system prompt from {self.prompt_path}: {e}")

    def _get_all_service_names(self, services_obj):
        """Recursively extracts all 'name' fields from the services structure."""
        names = []
        if isinstance(services_obj, dict):
            if "name" in services_obj:
                names.append(services_obj["name"])
            for value in services_obj.values():
                names.extend(self._get_all_service_names(value))
        elif isinstance(services_obj, list):
            for item in services_obj:
                names.extend(self._get_all_service_names(item))
        return names

    def evaluate(self, content, rag_context=None, retry_count=1):
        """Sends content to LLM and returns structured evaluation with retry logic."""
        services = self._load_services()
        system_prompt = self._load_prompt()
        
        # Inject context into system prompt
        formatted_system_prompt = system_prompt.replace("[SERVICES_JSON]", json.dumps(services, indent=2))
        
        # Enrich user prompt with RAG context if available
        user_content = f"Analyze this website content and provide the evaluation in JSON:\n\n{content}"
        if rag_context:
            rag_text = "\n\n".join(rag_context) if isinstance(rag_context, list) else rag_context
            user_content = f"Additional Advisory Context (RAG):\n{rag_text}\n\n---\n\n{user_content}"
                
        attempts = 0
        while attempts <= retry_count:
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": formatted_system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                
                # Attempt to parse response as JSON
                try:
                    content_str = completion.choices[0].message.content
                    # Groq sometimes adds text outside the JSON even with json_object mode
                    if "```json" in content_str:
                        content_str = content_str.split("```json")[1].split("```")[0].strip()
                    elif "{" in content_str:
                        content_str = content_str[content_str.find("{"):content_str.rfind("}")+1]
                        
                    result = json.loads(content_str)
                    
                    # Store usage metadata
                    usage = completion.usage
                    result["_usage"] = {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens
                    }
                    
                    # Track totals
                    self.total_usage["prompt_tokens"] += usage.prompt_tokens
                    self.total_usage["completion_tokens"] += usage.completion_tokens
                    self.total_usage["total_tokens"] += usage.total_tokens
                except (ValueError, json.JSONDecodeError) as je:
                    raise Exception(f"LLM returned invalid JSON: {je}. Raw snippet: {completion.choices[0].message.content[:100]}...")
                
                # Validation: Check if primary_service matches one in services.json
                if not services:
                    # Placeholder state: no services to validate against
                    return result

                valid_service_names = self._get_all_service_names(services)
                
                # Validate Primary
                if result.get("primary_service") not in valid_service_names:
                    raise ValueError(f"Selected primary service '{result.get('primary_service')}' is not in the approved list.")
                
                # Validate Secondary (if present)
                secondary = result.get("secondary_service")
                if secondary and secondary not in valid_service_names:
                    # Log but maybe don't fail hard if it's optional, 
                    # but for consistency we should enforce it.
                    raise ValueError(f"Selected secondary service '{secondary}' is not in the approved list.")
                
                # Success! Reset quota status if it was bad
                Evaluator.quota_ok = True
                Evaluator.status = "System Online"
                return result
            
            except Exception as e:
                # Update status if it's a rate limit error
                if "rate_limit" in str(e).lower() or "quota" in str(e).lower():
                    Evaluator.quota_ok = False
                    Evaluator.status = "Rate Limited / Quota Reached"
                
                attempts += 1
                if attempts > retry_count:
                    # Raise the original error but with more context if it's a Groq error
                    if "groq" in str(e).lower():
                        raise Exception(f"AI Service (Groq) Error: {str(e)}")
                    raise e
                logger.warning(f"Retry {attempts}/{retry_count} for LLM evaluation due to: {e}")
            
            finally:
                import datetime
                Evaluator.last_run_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Reset quota_ok if it was a success session (logic: if we got here and didn't raise, maybe it's fine)
                # But better: only reset if we actually RETURNED successfully.
                pass

if __name__ == "__main__":
    # Test with mock data
    evaluator = Evaluator()
    mock_content = "We are a local plumbing company in Austin, Texas. We offer emergency pipe repairs, water heater installation, and drain cleaning."
    print("Evaluator logic loaded.")
    # result = evaluator.evaluate(mock_content)
    # print(json.dumps(result, indent=2))
