import re
import json
import logging

from ._utils import critic_agent_prompt
from autogen.agents.source import OllamaClient, get_safe_max_characters, check_number_of_characters

logger = logging.getLogger(__name__)

class CriticTool:

    def __init__(self, user_profile: dict, user_travel_details: dict, model_name: str = "deepseek-r1"):
        """
        Initializes the FilterTool with user profile and shared OllamaClient.
        """
        self.model = model_name
        self.llm_client = OllamaClient(model=model_name)
        self.valid_set = {"ACCEPT", "RE-WRITE"}
        self.prompt_template = critic_agent_prompt.replace(
            "{{user_profile}}", json.dumps(user_profile, indent=2)
        ).replace(
            "{{user_travel_details}}", json.dumps(user_travel_details, indent=2)
        )

    def build_prompt(self, itinerary_text: str, additional_info: str = "") -> str:
        """
        Builds the critic prompt using the given itinerary text.
        """
        prompt = self.prompt_template.replace("{{itinerary_text}}", itinerary_text)
        additional_info = additional_info.strip()
        if additional_info:
            additional_info = "\n\n**Additional Information for Improvement:**\n" + additional_info
        return prompt + additional_info

    def run(self, itinerary_text: str, additional_info: str = "") -> str:
        """
        Submits the filter prompt using the given content chunk.
        """
        prompt = self.build_prompt(itinerary_text, additional_info)
        curr_num_chars = check_number_of_characters(prompt)
        logger.info(f"[CriticTool] Prompt character count: {curr_num_chars}.")
        safe_num_chars = get_safe_max_characters(self.llm_client.model)
        logger.info(f"[CriticTool] Safe character limit for model {self.llm_client.model}: {safe_num_chars}.")
        if curr_num_chars > safe_num_chars:
            logger.warning(f"[CriticTool] Prompt exceeds safe character limit for model {self.llm_client.model}.")

        logger.verbose(f"[CriticTool] Running CriticTool with prompt:\n{prompt}\n")
        result = self.llm_client.run(prompt) or ""
        # print(f"[CriticTool] CriticTool result:\n{result}\n")
        return result

    def extract_decision(self, text: str) -> str:
        """
        Returns the final decision (ACCEPT, RE-WRITE), optionally sanitized.
        """
        return self.llm_client.extract_based_on_tags(text, "decision")

    def extract_reasoning(self, response: str) -> str:
        """
        Extracts <reasoning>...</reasoning> reasoning from the LLM output.
        """
        return self.llm_client.extract_based_on_tags(response, "reasoning")
    
    def extract_scores(self, response: str) -> str:
        """
        Extracts <scores>...</scores> from the LLM output.
        """
        return self.llm_client.extract_based_on_tags(response, "scores")
    
    def extract_suggestions(self, response: str) -> str:
        """
        Extracts <suggestion>...</suggestion> from the LLM output.
        """
        return self.llm_client.extract_based_on_tags(response, "suggestion")
    
    def extract_checklist(self, response: str) -> str:
        """
        Extracts <checklist>...</checklist> from the LLM output.
        """
        return self.llm_client.extract_based_on_tags(response, "checklist")
    
    def verify_response_format(self, response: str) -> bool:
        """
        Verify response has all four required blocks:
        <checklist>, <checklist>, <scores>, <decision>, <suggestion>.
        Content is not strictly validated, only presence of tags is required.
        """
        if not response:
            return False
        
        # Hard requirement: decision must be present and closed
        hard_tags = ["decision"]
        for tag in hard_tags:
            if f"<{tag}>" not in response or f"</{tag}>" not in response:
                logger.warning(f"[CriticTool] Missing or unclosed <{tag}> block in response.")
                return False

        # Soft: warn about missing blocks, but do not fail
        soft_tags = ["scores", "reasoning", "checklist", "suggestion"]
        for tag in soft_tags:
            if f"<{tag}>" not in response or f"</{tag}>" not in response:
                logger.warning(f"[CriticTool] Response missing or unclosed <{tag}> block.")

        return True
