import logging
import re
import requests
from typing import Optional

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL_NAME = "qwen3"

## TODO: set up logging here, cuz it would get stuck in the call sometimes

class OllamaClient:
    def __init__(self, model: str = DEFAULT_MODEL_NAME, api_url: str = OLLAMA_URL):
        self._model = model
        self._api_url = api_url
        self._raw_response = None

    def run(self, prompt: str, stream: bool = False) -> Optional[str]:
        """
        Returns the raw LLM response string.
        """

        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": stream
        }

        logger.verbose(f"[OllamaClient] Sending payload to ollama client {payload}...")

        try:
            # print("Sending request to Ollama...")
            logger.info(f"[OllamaClient] Sending request to Ollama...")
            res = requests.post(self._api_url, json=payload)
            logger.info(f"[OllamaClient] Received response: {res.status_code}")
            res.raise_for_status()
            raw_response = res.json()
            self._raw_response = raw_response
            logger.verbose(f"[OllamaClient] Parsed JSON response: {raw_response}")
            output = raw_response["response"]
            logger.info(f"[OllamaClient] Finished processing with Ollama.")
            return output
        
        except Exception as e:
            logger.error(f"[OllamaClient] Ollama request failed: {str(e)}")
            return None


    @property
    def model(self) -> str:
        return self._model

    @property
    def raw_response(self) -> Optional[dict]:
        return self._raw_response
    
    @staticmethod
    def extract_based_on_tags(text: str, tag: str) -> str:
        """
        Extracts content wrapped in specified tags.
        """
        pattern = rf"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ""

    def sanitize_filter_output(self, output: str, sanitize_prompt: str) -> str:
        """
        Ensures only the final decision is returned.
        """
        print("Sanitizing filter output...")
        prompt = sanitize_prompt.replace("{{output}}", output)
        return self.run(prompt) or ""

    def get_final_decision(self, text: str, sanitize_prompt: str, valid_set: set[str]) -> str:
        """
        Returns final decision, reprocessing with sanitize_filter_output() if needed.
        """
        decision = self.extract_decision(text, valid_set)
        if decision.upper() == "INVALID":
            cleaned = self.sanitize_filter_output(text, sanitize_prompt)
            decision = self.extract_decision(cleaned, valid_set)

            if decision.upper() == "INVALID":
                return "re-write"

        return decision.lower()

    @staticmethod
    def extract_decision(text: str, valid_set: set[str]) -> str:
        lines = text.strip().splitlines()
        for line in reversed(lines):
            clean = line.replace("**", "").strip().upper()
            if clean in valid_set:
                return clean
        return "INVALID"
    
    