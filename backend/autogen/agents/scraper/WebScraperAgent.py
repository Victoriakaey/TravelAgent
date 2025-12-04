import os
import json
import logging
from pydantic import BaseModel
from typing import Sequence, AsyncGenerator
from autogen_agentchat.base import Response
from autogen_agentchat.agents import AssistantAgent
from autogen_core import CancellationToken, ComponentModel, Component
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_agentchat.messages import BaseChatMessage, TextMessage, BaseAgentEvent

from .WebScraperTool import WebScraperTool 
from ._utils import web_scraper_agent_description
from .helpers._nlp_filter_tool import NLPFilterTool
from .helpers._llm_filter_tool import LLMFilterTool

from autogen.agents.source import get_dummy_scraped_content
from autogen.services import TimingTracker, RedisStorage, LocalStateService

logger = logging.getLogger(__name__)
DEFAULT_MODEL_CLIENT: ComponentModel = OllamaChatCompletionClient(model="qwen2.5")

class WebScraperAgentConfig(BaseModel):
    name: str
    description: str = web_scraper_agent_description

class WebScraperAgent(AssistantAgent, Component[WebScraperAgentConfig]):

    def __init__(
            self, 
            user_profile: dict, 
            user_travel_details: dict, 
            session_id: str,
            redis_store: RedisStorage, # | None = None,
            timer_client: TimingTracker,
            time_log_filename: str,
            log_path: str,
            fallback: bool = False, 
            filter_method: str = "nlp", # or "llm"
            test_mode: bool = False,
            model_client: ComponentModel = DEFAULT_MODEL_CLIENT, 
            name: str = "WebScraperAgent"
        ):

        super().__init__(name=name, model_client=model_client)
        self.user_profile = user_profile
        self.user_travel_details = user_travel_details
        self.user_id = user_profile['user_id']

        self.scraper = WebScraperTool(user_profile=user_profile, user_travel_details=user_travel_details, log_path=log_path)
        self.llm_filter_agent = LLMFilterTool(user_profile=user_profile, user_travel_details=user_travel_details) 
        self.nlp_filter_agent = NLPFilterTool(user_profile=user_profile)

        self._type_of_agent = "WebScrapeService"
        self._session_id = session_id
        self._redis_store = redis_store
        self._local_state_service = LocalStateService(redis_store=self._redis_store)

        self.timer = timer_client
        self.time_log_filename = time_log_filename

        self.number_of_rounds = 0
        self.list_of_scraping_history = []
        
        self._fallback = fallback
        self._filter_method = filter_method
        self._test_mode = test_mode
        self.total_kept_items = 0
        self.total_dropped_items = 0

        self.max_tries = 3
        self.min_filtered_items = 5


    def get_number_of_rounds(self) -> int:
        return self.number_of_rounds
    
    def get_list_of_scraping_history(self) -> list:
        return self.list_of_scraping_history

    async def run_web_scrape(self, content: str, additional_instruction: str = "", cancellation_token: CancellationToken | None = None) -> dict:
        timer_tag = f"webscraper:{self.number_of_rounds}_web_scraping"
        self.timer.start(timer_tag)
        logger.info(f"[WebScraperAgent] Received messages for web scraping...")

        messages = [TextMessage(
            content=content + additional_instruction,
            role="system",
            source="CriticAgent"
        )]

        response = await self.scraper.on_messages(messages, cancellation_token=cancellation_token)
        # logger.verbose(f"[WebScraperAgent] Messages for scraping: {messages}")
        content = response.chat_message.content

        if not content or not content.strip().startswith("["):
            raise ValueError(f"[WebScraperAgent] Expected JSON list but got: {repr(content)}")
        # Defensive check: Ensure content is not empty or None
        if not content or not content.strip():
            raise ValueError("[WebScraperAgent] Error: Received empty or blank response content from scraper.")

        try:
            scraped_content = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"[WebScraperAgent] JSON parsing failed. Content received:")
            # logger.info(content)
            raise ValueError(f"[WebScraperAgent] Failed to parse scraped content as JSON: {e}")

        logger.info(f"[WebScraperAgent] Saving scraped content to local state service\n")
        await self._local_state_service.set_scraped_content(agent_name=self.name, session_id=self._session_id, content=scraped_content)

        self.timer.stop(timer_tag)
        logger.info(f"[WebScraperAgent] Initial Web scraping completed in {self.timer.execution_times.get(timer_tag, 0)} seconds.\n")

        # self.scraped_chunks_history.append(scraped_content)
        return scraped_content

    async def run_filter(self, scraped_content: str) -> list:
        timer_tag = f"webscraper:{self.number_of_rounds}_running_filter"
        self.timer.start(timer_tag)
        filtered_item = []

        if self._filter_method == "llm":
            logger.info(f"[WebScraperAgent] Running LLM-based filtering on scraped content...")
            filtered_scraped_content = self.llm_filter_scraped_content(scraped_content=scraped_content)
        else:
            logger.info(f"[WebScraperAgent] - Running {self._filter_method.upper()}-based filtering on scraped content...")
            filtered_scraped_content = self.nlp_filter_scraped_content(scraped_content=scraped_content)


        logger.info(f"[WebScraperAgent] Saving filtered content to local state service\n")
        filtered_clean_content = f"Total Number of Filtered Chunks: {len(filtered_scraped_content)}\n\n"

        for i, item in enumerate(filtered_scraped_content):
            d = {}
            filtered_content = item[0]
            filtered_results = item[1]
            d['chunk_index'] = i+1
            d['title'] = filtered_content.get('title', '')
            d['url'] = filtered_content.get('url', '')
            d['clean_content'] = filtered_content.get('clean_content', '')
            d['filter_logs'] = filtered_results
            filtered_item.append(d)

        # logger.verbose(f"[WebScraperAgent] Filtered content: {filtered_item}")

        await self._local_state_service.set_filtered_chunks(agent_name=self.name, session_id=self._session_id, chunks=filtered_item) # TODO: change to filtered_item here, but it's a list so need to change the set_filtered_chunks function too

        # self.filtered_chunks_history.append(filtered_clean_content)
        self.timer.stop(timer_tag)
        logger.info(f"[WebScraperAgent] Filtering completed in {self.timer.execution_times.get(timer_tag, 0)} seconds.\n")

        return filtered_item

    async def on_messages(self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken | None = None) -> Response:
        logger.info(f"[WebScraperAgent] test_mode: {self._test_mode}, filter_method: {self._filter_method}, fallback: {self._fallback}")
        last_msg = messages[-1] if messages else None
        content = last_msg.content if last_msg else ""

        dummy_content = None
        scraped_content = None

        if self._test_mode:
            logger.info(f"[WebScraperAgent] Test mode enabled: Using dummy scraped content.")
            dummy_content = get_dummy_scraped_content()
            logger.verbose(f"[WebScraperAgent] Dummy scraped content: {dummy_content}")
            filtered_content = await self.run_filter(dummy_content)
            logger.verbose(f"[WebScraperAgent] Filtered content: {filtered_content}")
        else:
            scraped_content = await self.run_web_scrape(content, cancellation_token=cancellation_token)
            # logger.verbose(f"[WebScraperAgent] Scraped content: {scraped_content}")
            filtered_content = await self.run_filter(scraped_content)
            # logger.verbose(f"[WebScraperAgent] Filtered content: {filtered_content}")

        max_tries = self.max_tries
        min_filtered_items = self.min_filtered_items

        additional_instruction = (
            f"\nThe filtered output has only {len(filtered_content)} items, below the target of {min_filtered_items}. "
            "Please re-scrape with greater breadth and depth. Prioritize diversity, reliability, and strong relevance to the user profile and user travel details."
        )

        if self._fallback and len(filtered_content) < min_filtered_items:
            for attempt in range(max_tries):
                logger.warning(f"[WebScraperAgent] Fallback mode: Filtered items {len(filtered_content)} is less than {min_filtered_items}. Re-running web scraping (attempt {attempt+1})...")
                scraped_content = await self.run_web_scrape(content, additional_instruction, cancellation_token=cancellation_token)
                # logger.verbose(f"[WebScraperAgent] Scraped content: {scraped_content}")
                filtered_content = await self.run_filter(scraped_content)
                # logger.verbose(f"[WebScraperAgent] Filtered content: {filtered_content}")

                if len(filtered_content) >= min_filtered_items:
                    logger.info(f"[WebScraperAgent] Fallback mode: Successfully obtained {len(filtered_content)} filtered items after re-scraping.\n")
                    break
                else:
                    logger.warning(f"[WebScraperAgent] Fallback mode: Still only {len(filtered_content)} filtered items after re-scraping.\n")
            if len(filtered_content) < min_filtered_items:
                logger.error(f"[WebScraperAgent] Fallback mode: Failed to obtain sufficient filtered items after {max_tries} attempts. Proceeding with {len(filtered_content)} items.\n")

        scraping_history = {
            "round": self.number_of_rounds,
            "length_of_scraped_items": len(scraped_content) if scraped_content else 0,
            "length_of_filtered_items": len(filtered_content),
            "total_kept_items": self.total_kept_items,
            "total_dropped_items": self.total_dropped_items,
            # "messages": content,
            # "filtered_content": filtered_content
            # "raw_scraped_content": scraped_content,
        }

        self.list_of_scraping_history.append(scraping_history)

        return Response(chat_message=TextMessage(content=f"Finished scraping and filtering web searched content, and saving data to state for session `{self._session_id}`", source=self.name))

    async def on_messages_stream(self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken | None = None) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | Response, None]:
        self.number_of_rounds += 1
        timer_tag = f"webscraper:{self.number_of_rounds}_streaming"
        self.timer.start(timer_tag)
        logger.info(f"[WebScraperAgent] Starting streaming web scraping for messages for the {self.number_of_rounds}-th times...")
        result = await self.on_messages(messages, cancellation_token)
        logger.verbose(f"[WebScraperAgent] List of scraping history so far: {self.list_of_scraping_history}\n")

        self.timer.stop(timer_tag)
        logger.info(f"[WebScraperAgent] Finished streaming web scraping in {self.timer.execution_times.get(timer_tag, 0)} seconds.\n")
        self.timer.save_as_text(filename=self.time_log_filename)
        yield result

    def nlp_filter_scraped_content(self, scraped_content: dict) -> dict:
        """
        Processes the filtered content and returns it as a string.
        """
        timer_tag = f"webscraper:{self.number_of_rounds}_running_nlp_filter"
        self.timer.start(timer_tag)
        logger.info(f"[WebScraperAgent] Filtering scraped content...")
        kept_chunks = []
        keep_decision_count = 0
        dropped_decision_count = 0

        for i, content in enumerate(scraped_content):
            logger.info(f"[WebScraperAgent] Processing content {i+1}/{len(scraped_content)}...")
            query = content['query']
            metadata = content.get('metadata', {})
            clean_content = content['clean_content']
            final_decision = "unknown"
            # results = []

            if clean_content != "":
                filtered_result = self.nlp_filter_agent.filter_chunk(clean_content, query, metadata)
                logger.verbose(f"[WebScraperAgent] Filtered result for content {i+1}: {filtered_result}")
                final_decision = filtered_result['final_decision'].lower()

                logger.info(f"[WebScraperAgent] Content #{i+1} Decision: {final_decision}")

                if final_decision == "keep":
                    kept_chunks.append((content, filtered_result))
                    # logger.verbose(f"Title: {content['title']}\nURL: {content['url']}\nClean Content:\n{clean_content}\n\n")
                    keep_decision_count += 1
                else:
                    dropped_decision_count += 1

        logger.info(f"[WebScraperAgent] Total Kept: {keep_decision_count}, Dropped: {dropped_decision_count}\n")
        logger.info(f"[WebScraperAgent] Processed {len(scraped_content)} chunks of scraped content, and kept {len(kept_chunks)} relevant chunks after filtering.\n")

        self.total_kept_items = keep_decision_count
        self.total_dropped_items = dropped_decision_count

        self.timer.stop(timer_tag)
        logger.info(f"[WebScraperAgent] Finished filtering in {self.timer.execution_times.get(timer_tag, 0)} seconds.\n")
        return kept_chunks
    
    def llm_filter_scraped_content(self, scraped_content: dict) -> dict:
        timer_tag = f"webscraper:{self.number_of_rounds}_running_llm_filter"
        self.timer.start(timer_tag)
        logger.info(f"[WebScraperAgent] Filtering scraped content using LLM...")
        kept_chunks = []
        keep_decision_count = 0
        dropped_decision_count = 0

        for i, content in enumerate(scraped_content):
            logger.info(f"[WebScraperAgent] Processing content {i+1}/{len(scraped_content)}...")
            query = content['query']
            metadata = content.get('metadata', {})
            clean_content = content['clean_content']
            final_decision = "unknown"
            # results = []

            if clean_content != "":
                logger.verbose(f"[WebScraperAgent] Clean content for filtering {i+1}:\n{clean_content}\n")
                filtered_result = self.llm_filter_agent.run(clean_content)
                logger.info(f"[WebScraperAgent] Filtered result for content {i+1}: {filtered_result}")
                reasoning = self.llm_filter_agent.extract_reasoning(filtered_result)
                final_decision = self.llm_filter_agent.extract_decision(filtered_result).lower()

                logger.info(f"[WebScraperAgent] Content #{i+1} Decision: {final_decision}")

                if final_decision == "keep":
                    kept_chunks.append((content, filtered_result))
                    logger.info(f"[WebScraperAgent] Kept content {i+1} with reasoning: {reasoning}")
                    logger.verbose(f"Title: {content['title']}\nURL: {content['url']}\nClean Content:\n{clean_content}\n\n")
                    keep_decision_count += 1
                else:
                    dropped_decision_count += 1
                    logger.info(f"[WebScraperAgent] Dropped content {i+1} with reasoning: {reasoning}")

        logger.info(f"[WebScraperAgent] Total Kept: {keep_decision_count}, Dropped: {dropped_decision_count}\n")
        logger.info(f"[WebScraperAgent] Processed {len(scraped_content)} chunks of scraped content, and kept {len(kept_chunks)} relevant chunks after filtering.\n")

        self.timer.stop(timer_tag)
        logger.info(f"[WebScraperAgent] Finished filtering in {self.timer.execution_times.get(timer_tag, 0)} seconds.\n")
        return kept_chunks

    def _to_config(self):
        """Convert the agent to a configuration object."""
        return WebScraperAgentConfig(
            name=self.name,
            description=web_scraper_agent_description
        )
    
    @classmethod
    def _from_config(cls, config: WebScraperAgentConfig):
        """Create an agent from a configuration object."""
        return cls(
            user_profile={},
            user_travel_details={},
            model_client=DEFAULT_MODEL_CLIENT,
            name=config.name
        )

