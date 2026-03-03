import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class Evaluator:
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
            raise Exception(f"Failed to load services: {e}")

    def _load_prompt(self):
        """Loads the system prompt."""
        try:
            with open(self.prompt_path, 'r') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"Failed to load system prompt: {e}")

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
                
                result = json.loads(completion.choices[0].message.content)
                
                # Validation: Check if primary_service matches one in services.json
                if not services:
                    # Placeholder state: no services to validate against
                    return result

                valid_service_names = [s.get("name") for s in services if s.get("name")]
                if result.get("primary_service") not in valid_service_names:
                    raise ValueError(f"Selected service '{result.get('primary_service')}' is not in the approved list.")
                
                return result
            
            except Exception as e:
                attempts += 1
                if attempts > retry_count:
                    raise Exception(f"LLM Evaluation failed after {attempts} attempts: {e}")
                print(f"Retry {attempts}/{retry_count} due to error: {e}")

if __name__ == "__main__":
    # Test with mock data
    evaluator = Evaluator()
    mock_content = "We are a local plumbing company in Austin, Texas. We offer emergency pipe repairs, water heater installation, and drain cleaning."
    print("Evaluator logic loaded.")
    # result = evaluator.evaluate(mock_content)
    # print(json.dumps(result, indent=2))
