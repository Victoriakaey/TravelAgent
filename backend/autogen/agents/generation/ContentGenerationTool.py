import json
import logging

from ._utils import content_generation_agent_prompt
from autogen.agents.source import OllamaClient, get_safe_max_characters, check_number_of_characters

logger = logging.getLogger(__name__)

class ContentGenerationTool:

    def __init__(self, user_profile: dict, user_travel_details: dict, llm_client: OllamaClient = OllamaClient(model="qwen2.5")):
        """
        Initializes the FilterTool with user profile and shared OllamaClient.
        """
        self.llm_client = llm_client
        self.prompt_template = content_generation_agent_prompt.replace(
            "{{user_profile}}", json.dumps(user_profile, indent=2)
        ).replace(
            "{{user_travel_details}}", json.dumps(user_travel_details, indent=2)
        )

    def build_prompt(self, filtered_content: str, search_result: str, additional_instruction: str = "") -> str:
        """
        Builds the content generation prompt using the given content chunk.
        """
        prompt = self.prompt_template.replace("{{filtered_content}}", filtered_content)
        final_prompt = prompt.replace("{{search_result}}", search_result)
        additional_instruction = "**Additional Information for Improvement:**\n" + additional_instruction.strip()
        return final_prompt + additional_instruction

    def run_content_generation(self, filtered_content: str, search_result: str, additional_instruction: str = "") -> str:
        """
        Submits the filter prompt using the given content chunk.
        """
        built_prompt = self.build_prompt(filtered_content, search_result, additional_instruction)
        logger.verbose(f"[ContentGenerationTool] Running content generation with prompt:\n{built_prompt}")
        logger.info(f"[ContentGenerationTool] Running content generation...")

        curr_num_chars = check_number_of_characters(built_prompt)
        safe_num_chars = get_safe_max_characters(self.llm_client.model)
        logger.info(f"[ContentGenerationTool] Prompt character count: {curr_num_chars}.")
        logger.info(f"[ContentGenerationTool] Safe character limit for model {self.llm_client.model}: {safe_num_chars}.")
        if curr_num_chars > safe_num_chars:
            logger.warning(f"[ContentGenerationTool] Prompt exceeds safe character limit for model {self.llm_client.model}.")

        return self.llm_client.run(built_prompt) or ""
    