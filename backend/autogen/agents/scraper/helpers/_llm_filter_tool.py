import json
import asyncio

from ._utils import filter_tool_prompt
from autogen.agents.source import OllamaClient

class LLMFilterTool:

    def __init__(self, user_profile: dict, user_travel_details: dict, llm_client: OllamaClient = OllamaClient()):
        """
        Initializes the FilterTool with user profile and shared OllamaClient.
        """
        self.llm_client = llm_client
        self.valid_set = {"KEEP", "DROP"}
        self.prompt_template = filter_tool_prompt.replace(
            "{{user_profile}}", json.dumps(user_profile, indent=2)
        ).replace(
            "{{user_travel_details}}", json.dumps(user_travel_details, indent=2)
        )

    def run(self, chunk_text: str) -> str:
        """
        Submits the filter prompt using the given content chunk.
        """
        prompt = self.prompt_template.replace("{{chunk_text}}", chunk_text)
        return self.llm_client.run(prompt) or ""

    def extract_decision(self, text: str) -> str:
        """
        Returns the final decision (KEEP or DROP), optionally sanitized.
        """
        # return self.llm_client.get_final_decision(text, filter_final_decision_determination_prompt, self.valid_set)
        decision = self.llm_client.extract_based_on_tags(text, "decision")
        if not decision: return "DROP"
        return decision

    def extract_reasoning(self, response: str) -> str:
        """
        Extracts <think>...</think> reasoning from the LLM output.
        """
        return self.llm_client.extract_based_on_tags(response, "think")

# async def run_filter_agent():
#     filter_agent = FilterTool(user_profile=user_profile)
#     # chunks = split_chunks_by_label(dummy_chunks)

#     kept_chunks = []
#     print("Running Filter Tool...")
#     print(len(chunks))
#     for chunk in chunks:
#         clean_chunk = chunk #.replace("\n", "")
#         print(f"Chunk:\n{clean_chunk}")
#         filtered_result = filter_agent.run(clean_chunk)
#         print(f"Filtered Result:\n{filtered_result}")
#         decision = filter_agent.get_final_decision(filtered_result)
#         print(f"Decision: {decision}")
#         print("============")

#     print("Kept chunks:", len(kept_chunks))
#     print("Final kept chunks:")
#     for i, chunk in enumerate(kept_chunks):
#         print(f"Chunk {i+1}:\n{chunk}\n")
    
# if __name__ == "__main__":
#     asyncio.run(run_filter_agent())