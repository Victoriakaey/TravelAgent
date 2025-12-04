import json
import logging
from pydantic import BaseModel
from autogen_agentchat.base import Response
from typing import Sequence, AsyncGenerator
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_core import CancellationToken, ComponentModel, Component
from autogen_agentchat.messages import BaseChatMessage, TextMessage, BaseAgentEvent

from autogen.services._time_tracker import TimingTracker
from autogen.services.local_state_service import LocalStateService
from autogen.services.redis_store.redis_storage import RedisStorage

from ._utils import content_generation_agent_description
from .ContentGenerationTool import ContentGenerationTool
from .SearchResultToMarkdown import flights_to_markdown, hotels_to_markdown, places_to_markdown, tours_to_markdown

logger = logging.getLogger(__name__)

class ContentGenerationAgentConfig(BaseModel):
    name: str
    description: str = content_generation_agent_description

class ContentGenerationAgent(AssistantAgent, Component[ContentGenerationAgentConfig]):

    def __init__(
            self, 
            user_profile: dict, 
            user_travel_details: dict, 
            session_id: str,
            redis_store: RedisStorage,
            model_client: ComponentModel,
            timer_client: TimingTracker,
            time_log_filename: str,
            name: str = "ContentGenerationAgent"
        ):

        super().__init__(name=name, model_client=model_client)

        self._name = name
        self._session_id = session_id 
        self._redis_store = redis_store
        self._type_of_agent = "ContentGenerationService"
        self._web_agent_name = "WebScraperAgent"
        self._search_agent_name = "SearchAgent"
        self._critic_agent_name = "CriticAgent"
        self._local_state_service = LocalStateService(redis_store=self._redis_store)

        self.timer = timer_client
        self.time_log_filename = time_log_filename
        self.content_generation_tool = ContentGenerationTool(user_profile=user_profile, user_travel_details=user_travel_details)

        self.number_of_rounds = 0
        self.list_of_generated_records = []

    def get_number_of_rounds(self) -> int:
        return self.number_of_rounds
    
    def get_list_of_generated_records(self) -> list:
        return self.list_of_generated_records

    async def _get_filtered_content(self) -> str:
        timer_tag = f"content_generation:{self.number_of_rounds}_fetch_filtered_content_from_redis"
        self.timer.start(timer_tag)
        full_filtered_content = ""
        try:
            filtered_content = await self._local_state_service.get_filtered_chunks(self._web_agent_name, self._session_id)
            if filtered_content:

                for i, item in enumerate(filtered_content):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    clean_content = item.get('clean_content', 'N/A')
                    full_filtered_content += f"Chunk {i+1}:\nTitle:{title}\nURL: {url}\nClean Content:\n{clean_content}\n\n"
                self.timer.stop(timer_tag)
                logger.info(f"[ContentGenerationAgent] Retrieved full filtered content, and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
                return full_filtered_content
            else:
                # logger.info(f"[ContentGenerationAgent] No filtered content found.")
                self.timer.stop(timer_tag)
                logger.info(f"[ContentGenerationAgent] No filtered content found, and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
                return ""
            
        except Exception as e:
            logger.error(f"[ContentGenerationAgent] Failed to get filtered_content: {e}")
            self.timer.stop(timer_tag)
            logger.info(f"[ContentGenerationAgent] Failed to get filtered_content, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
            return ""

    async def _get_search_result(self, search_type: str) -> str:
        timer_tag = f"content_generation:{self.number_of_rounds}_fetch_{search_type}_search_results_from_redis"
        self.timer.start(timer_tag)
        logger.info(f"[ContentGenerationAgent] Fetching {search_type} search results for session {self._session_id}...")
        try:
            search_results = await self._local_state_service.get_search_results(self._search_agent_name, self._session_id, search_type)
            if search_results:
                logger.info(f"[ContentGenerationAgent] Retrieved {len(search_results)} search results.")
                # logger.verbose(f"[ContentGenerationAgent] Search results: {search_results}")
                top_25_search_results = search_results[:25]
                # logger.info(f"[ContentGenerationAgent] Returning top 25 search results.")
                logger.verbose(f"[ContentGenerationAgent] Top 25 search results: {top_25_search_results}")
                self.timer.stop(timer_tag)
                logger.info(f"[ContentGenerationAgent] Returned top 25 search results, and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
                return json.dumps(top_25_search_results, indent=2)
            else:
                # logger.info(f"[ContentGenerationAgent] No search results found.")
                self.timer.stop(timer_tag)
                logger.info(f"[ContentGenerationAgent] No search results found, and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
                return "[]"
        except Exception as e:
            logger.error(f"[ContentGenerationAgent] Failed to get search results: {e}")
            self.timer.stop(timer_tag)
            logger.info(f"[ContentGenerationAgent] Failed to get search results, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
            return ""
    
    async def _get_search_results(self) -> list:
        timer_tag = f"content_generation:{self.number_of_rounds}_fetch_all_search_results_from_redis"
        self.timer.start(timer_tag)
        logger.info(f"[ContentGenerationAgent] Fetching search results for session {self._session_id}...")

        flight_results = await self._get_search_result("flight")
        hotel_results = await self._get_search_result("hotel")
        tour_results = await self._get_search_result("tour")
        places_results = await self._get_search_result("places")

        combined_results = {
            "flight": json.loads(flight_results) if flight_results else [],
            "hotel": json.loads(hotel_results) if hotel_results else [],
            "tour": json.loads(tour_results) if tour_results else [],
            "places": json.loads(places_results) if places_results else []
        }

        len_flight = len(combined_results["flight"])
        len_hotel = len(combined_results["hotel"])
        len_tour = len(combined_results["tour"])
        len_places = len(combined_results["places"])

        logger.info(f"[ContentGenerationAgent] Combined search results: {combined_results}")

        self.timer.stop(timer_tag)
        logger.info(f"[ContentGenerationAgent] Fetched {len_flight} flight, {len_hotel} hotel, {len_tour} tour, and {len_places} places search results, and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return combined_results
    
    def _search_results_to_markdown_tables(self, combined_results: dict) -> str:
        timer_tag = f"content_generation:{self.number_of_rounds}_convert_search_results_to_markdown"
        self.timer.start(timer_tag)
        # logger.info(f"[ContentGenerationAgent] Converting search results to markdown tables...")
        markdown = ""

        if "flight" in combined_results:
            markdown += flights_to_markdown(combined_results["flight"]) + "\n\n"
        if "hotel" in combined_results:
            markdown += hotels_to_markdown(combined_results["hotel"]) + "\n\n"
        if "tour" in combined_results:
            markdown += tours_to_markdown(combined_results["tour"]) + "\n\n"
        if "places" in combined_results:
            markdown += places_to_markdown(combined_results["places"]) + "\n\n"

        # logger.verbose(f"[ContentGenerationAgent] Search results in markdown:\n{markdown}")
        self.timer.stop(timer_tag)
        logger.info(f"[ContentGenerationAgent] Converted search results to markdown tables, and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return markdown

    async def _get_raw_response(self) -> str:
        timer_tag = f"content_generation:{self.number_of_rounds}_fetch_critic_raw_response_from_redis"
        self.timer.start(timer_tag)
        logger.info(f"[ContentGenerationAgent] Fetching Critic raw_response for session {self._session_id}...")
        try:
            raw_response = await self._local_state_service.get_critic_raw_response(self._critic_agent_name, self._session_id)
            if raw_response:
                # logger.info(f"[ContentGenerationAgent] Retrieving Critic Raw Response.")
                logger.verbose(f"[ContentGenerationAgent] Critic Raw Response: {raw_response}")
                self.timer.stop(timer_tag)
                logger.info(f"[ContentGenerationAgent] Retrieved Critic Raw Response, and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
                return raw_response
            else:
                # logger.info(f"[ContentGenerationAgent] No Critic Raw Response found.")
                self.timer.stop(timer_tag)
                logger.info(f"[ContentGenerationAgent] No Critic Raw Response found, and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
                return ""
        except Exception as e:
            logger.error(f"[ContentGenerationAgent] Failed to get Critic Raw Response: {e}")
            self.timer.stop(timer_tag)
            logger.info(f"[ContentGenerationAgent] Failed to get Critic Raw Response, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
            return ""

    async def generate_content(self, filtered_content: str, search_result: str, additional_instruction: str) -> str:
        logger.info(f"[ContentGenerationAgent] Starting to generate travel plan...")
        generated_plan = self.content_generation_tool.run_content_generation(
            filtered_content=filtered_content,
            search_result=search_result,
            additional_instruction=additional_instruction
        )
        logger.info(f"[ContentGenerationAgent] Generated travel plan: {generated_plan}")
        return generated_plan

    async def on_messages(self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken | None = None) -> Response:
        logger.info(f"[ContentGenerationAgent] Received messages for content generation...")
        # Determine sender of the last message
        last_msg = messages[-1]
        # sender = getattr(last_msg, "sender", "")
        content = last_msg.content if hasattr(last_msg, "content") else ""

        raw_response = await self._get_raw_response()

        additional_text = (
            "CriticAgent has requested a re-write.\n"
            "You MUST carefully read the following JSON feedback and FIX EVERY ISSUE it marks as invalid.\n"
            "Do NOT change the trip year or move the trip dates away from the range defined in User Travel Details.\n"
            "Use the CriticAgent feedback ONLY to correct the previous itinerary (dates, logic, constraints), "
            "and then regenerate a clean Markdown itinerary.\n\n"
            f"Raw Response from CriticAgent:\n{raw_response}\n\n"
        )

        additional_instruction = content.replace("ContentGenerationAgent:", "").replace("contentgenerationagent:", "").strip() + "\n\n" + additional_text

        logger.verbose(f"[ContentGenerationAgent] Additional instruction from incoming message: {additional_instruction}")

        try:
            filtered_content = await self._get_filtered_content()
            search_result = await self._get_search_results()
            search_result_markdown = self._search_results_to_markdown_tables(search_result)

            logger.info(f"[ContentGenerationAgent] Starting to generate travel plan...")

            generated_plan = await self.generate_content(
                filtered_content=filtered_content,
                search_result=search_result_markdown,
                additional_instruction=additional_instruction
            )

            logger.info(f"[ContentGenerationAgent] Generated travel plan: {generated_plan} and saving plan to Redis for session {self._session_id}")
            await self._local_state_service.store_generated_plan(self._name, self._session_id, generated_plan)
            # logger.info(f"[ContentGenerationAgent] Plan successfully stored in Redis.")

            generated_plan_record = {
                "round": self.number_of_rounds,
                "critic_raw_response": raw_response,
                "message": content,
                "filtered_content": filtered_content,
                "search_result_markdown": search_result_markdown,
                "generated_plan": generated_plan,
            }

            self.list_of_generated_records.append(generated_plan_record)

            return Response(chat_message=TextMessage(content=f"Travel plan generated successfully, and saving data to state for session `{self._session_id}`", source=self.name))

        except Exception as e:
            logger.error(f"[ContentGenerationAgent] Error: {e}")
            return Response(chat_message=TextMessage(
                content=f"[ContentGenerationAgent] Failed to generate plan: {str(e)}",
                source=self.name
            ))
        
    async def on_messages_stream(self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken | None = None) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | Response, None]:
        self.number_of_rounds += 1
        timer_tag = f"content_generation:{self.number_of_rounds}_streaming_run"
        self.timer.start(timer_tag)
        logger.info(f"[ContentGenerationAgent] Starting streaming content generation for messages for the {self.number_of_rounds}-th times...")
        result = await self.on_messages(messages, cancellation_token)
        logger.verbose(f"[ContentGenerationAgent] List of generated plans so far: {self.list_of_generated_records}\n")
        self.timer.stop(timer_tag)
        logger.info(f"[ContentGenerationAgent] Finished streaming content generation for messages and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        self.timer.save_as_text(filename=self.time_log_filename)
        yield result

    def _to_config(self):
        """Convert the agent to a configuration object."""
        return ContentGenerationAgentConfig(
            name=self.name,
            description=content_generation_agent_description
        )
    
    @classmethod
    def from_config(cls, config: ContentGenerationAgentConfig):
        """Create an agent from a configuration object."""
        return cls(
            user_profile={},
            user_travel_details={},
            model_client=OllamaChatCompletionClient(model="qwen2.5"),
            name="ContentGenerationAgent"
        )
    