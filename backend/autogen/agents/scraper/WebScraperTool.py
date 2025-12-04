import json
import logging
import requests
from typing import Sequence
from autogen_core import CancellationToken
from autogen_agentchat.base import Response
from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.messages import TextMessage, BaseChatMessage

from ._utils import web_scraper_prompt, web_scraper_agent_description
from .helpers._save_content_to_file import save_sources_to_file

from autogen.agents.source import generate_user_query

logger = logging.getLogger(__name__)

INSTRUCTION_TEXT = "\nAdditional Instructions:\n"
PERPLEXICA_API_URL = "http://localhost:3000/api/search"
DEFAULT_QUERY_APPENDIX = "\nCan you help me find some information about this to better plan this trip?"

class WebScraperTool(BaseChatAgent):
    def __init__(
        self,
        user_profile: dict,
        user_travel_details: dict,
        log_path: str,
        name: str = "WebScraperTool",
        focus_mode: str = "webSearch",
        optimization_mode: str = "balanced",
    ):
        super().__init__(name=name, description=web_scraper_agent_description)

        self.api_url = PERPLEXICA_API_URL
        self.focus_mode = focus_mode
        self.optimization_mode = optimization_mode
        self.user_profile = user_profile
        self.user_travel_details = user_travel_details
        self.user_id = user_profile["user_id"]
        self.user_keywords = user_profile["preferences"] + user_profile["constraints"]
        self.system_instructions = web_scraper_prompt

        self.llm_provider = "ollama"
        self.chat_model_name = "qwen2.5:7b-instruct"
        self.embedding_model_name = "snowflake-arctic-embed:latest"

        self.log_path = log_path

    def build_payload(self, query: str) -> dict:
        return {
            "chatModel": {"provider": self.llm_provider, "name": self.chat_model_name},
            "embeddingModel": {"provider": self.llm_provider, "name": self.embedding_model_name},
            "query": query,
            "optimizationMode": self.optimization_mode,
            "focusMode": self.focus_mode,
            "systemInstructions": self.system_instructions
        }

    @property
    def produced_message_types(self) -> Sequence[type[BaseChatMessage]]:
        return [TextMessage]

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass

    async def on_messages(self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken | None = None) -> Response:

        logger.info(f"[WebScraperTool] Log path set to: {self.log_path}")
        cancellation_token = cancellation_token or CancellationToken()

        message = messages[-1]
        content = message.content.strip().lower()
        msg_content = content.replace("WebScraperAgent:", "").replace("webscraperagent:", "").strip()

        if msg_content.strip() == "":
            query = generate_user_query(self.user_profile, self.user_travel_details) + DEFAULT_QUERY_APPENDIX
        else:
            query = generate_user_query(self.user_profile, self.user_travel_details) + INSTRUCTION_TEXT + msg_content + DEFAULT_QUERY_APPENDIX

        # logger.info(f"[WebScraperTool] Received message: {msg_content}")
        logger.info(f"[WebScraperTool] Generated query: {query}")
        
        payload = self.build_payload(query)

        logger.info(f"[WebScraperTool] Sending request to {self.api_url} with payload")
        try:
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            result = response.json()
            info = None

            info = await save_sources_to_file(query, result["sources"], log_path=self.log_path)
            self.latest_scraped_chunks = info
            # self.scraped_chunks_history.append(info)

            logger.info(f"[WebScraperTool] Starting to process scraped content...")
            if info:
                logger.info(f"[WebScraperTool] Successfully scraped {len(info)} chunks of information.")
                response_as_str = json.dumps(info, indent=2)
                return Response(chat_message=TextMessage(content=response_as_str, source=self.name))
            else:
                error_msg = "No relevant information found. Please try a different query."
                logger.warning(f"[WebScraperTool] {error_msg}")
                
                return Response(chat_message=TextMessage(content=json.dumps([]), source=self.name))
            
        except requests.exceptions.Timeout:
            error_msg = f"Request timed out."
            logger.error(f"[WebScraperTool] {error_msg}")
            return Response(chat_message=TextMessage(content=json.dumps([]), source=self.name))

        except requests.exceptions.RequestException as e:
            error_msg = f"Web scraping failed: {e}"
            logger.error(f"[WebScraperTool] {error_msg}")
            return Response(chat_message=TextMessage(content=json.dumps([]), source=self.name))

