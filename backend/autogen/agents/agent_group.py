import uuid
import logging
from dotenv import load_dotenv
from autogen_core import CancellationToken
from autogen_agentchat.base import Response
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import SelectorGroupChat
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination

from autogen.agents import WebScraperAgent, SearchAgent, ContentGenerationAgent, CriticAgent, TransactionAgent
from autogen.services import setup_logging,  selector_func, log_agent_message, AmadeusService, GoogleMapsService, LocalStateService, RedisStorage, TimingTracker
from autogen.prompts import selector_prompt, planning_agent_description, user_proxy_agent_description, planning_agent_prompt, planning_agent_prompt_no_critic

OUTPUT_FOLDER = "log/" 
logger = logging.getLogger(__name__)

class AgentGroup:
    def __init__(
            self, 
            case_num: int, 
            user_profile: dict, 
            user_travel_details: dict, 
            user_input_func: callable,
            plan: str = "", 
            folder: str = "",
            filter_mode: str = "nlp", 
            test_filter: bool = False, 
            test_critic: bool = False,
            critic_enabled: bool = True,
            session_id: str | None = None,
            fallback_enabled: bool = False,
        ):

        load_dotenv()

        self._type_of_agent = "UserInfoService"
        self._user_id = user_profile["user_id"]
        self._session_id = session_id or str(uuid.uuid4())

        self.folder = OUTPUT_FOLDER + folder
        self.filename_starter = self.folder + f"case_{case_num}" + f"/{user_profile['user_id']}_{self._session_id}"

        self._redis_store = RedisStorage()
        self._amadeus_service = AmadeusService()
        self._google_maps_service = GoogleMapsService()
        self._local_state_service = LocalStateService(redis_store=self._redis_store)

        self._timer_client = TimingTracker(user_id=self._user_id, output_folder="")
        self._time_log_filename = self.filename_starter + "/content_agent_timing.log"

        info_log_filename = self.filename_starter + "/info_runtime.log"
        verbose_log_filename = self.filename_starter + "/verbose_runtime.log"

        setup_logging(
            log_to_file=True,
            info_log_file= info_log_filename,  # INFO Level
            verbose_log_file= verbose_log_filename  # VERBOSE Level
        )

        logger.info(f"Running case number {case_num}")
        logger.info(f"Saving info logs to {info_log_filename}")
        logger.info(f"Saving verbose logs to {verbose_log_filename}")
        logger.info(f"Saving timing logs to {self._time_log_filename}")

        # logger.verbose(f"PlanningAgent's prompt {planning_agent_prompt}")

        logging.getLogger("urllib3").setLevel(logging.INFO)
        logging.getLogger("sentence_transformers").setLevel(logging.INFO)
        logging.getLogger("asyncio").setLevel(logging.WARNING)

        logger.info(f"\nUser Profile:\n\n{user_profile}\n")
        logger.info(f"\nUser Travel Details:\n\n{user_travel_details}\n")
        
        self._model_client_gemma_2 = OllamaChatCompletionClient(model="gemma2")
        self._model_client_deepseek_r1 = OllamaChatCompletionClient(model="deepseek-r1")
        
        self._model_client_qwen_2_5 = OllamaChatCompletionClient(model="qwen2.5")
        # https://github.com/ollama/ollama/blob/main/docs/modelfile.md#parameter
        self._model_client_qwen_2_5_with_parameters = OllamaChatCompletionClient(
            model="qwen2.5", 
            options={
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 512,
            }
        )

        # `qwen2.5:7b-instruct` (for text generation) and `snowflake-arctic-embed:335m` (for embedding)
        self.web_scraper_agent = WebScraperAgent(
            user_profile=user_profile,
            user_travel_details=user_travel_details,
            session_id=self._session_id,
            redis_store=self._redis_store,
            fallback=fallback_enabled,
            log_path=self.filename_starter,
            timer_client=self._timer_client,
            time_log_filename=self._time_log_filename,
            test_mode=test_filter,
            filter_method=filter_mode, 
        )

        self.search_agent = SearchAgent(
            timer_client=self._timer_client,
            time_log_filename=self._time_log_filename,
            amadeus_service=self._amadeus_service,
            google_maps_service=self._google_maps_service,
            session_id=self._session_id,
            redis_store=self._redis_store,
            fallback=fallback_enabled,
            model_client_stream=True,
            model_client=self._model_client_qwen_2_5,
        )

        self.content_generation_agent = ContentGenerationAgent(
            user_profile=user_profile,
            user_travel_details=user_travel_details,
            session_id=self._session_id,
            redis_store=self._redis_store,
            timer_client=self._timer_client,
            time_log_filename=self._time_log_filename,
            model_client=self._model_client_gemma_2,
        )

        self.critic_agent = CriticAgent(
            user_profile=user_profile,
            user_travel_details=user_travel_details,
            session_id=self._session_id,
            redis_store=self._redis_store,
            timer_client=self._timer_client,
            time_log_filename=self._time_log_filename,
            model_name="deepseek-r1",
            model_client=self._model_client_deepseek_r1,
            test_mode=test_critic,
            plan=plan,
        )

        self.transaction_agent = TransactionAgent(
            name="TransactionAgent",
            session_id=self._session_id,
            user_profile=user_profile,
            user_travel_details=user_travel_details,
            redis_store=self._redis_store,
            timer_client=self._timer_client,
            time_log_filename=self._time_log_filename,
            amadeus_service=self._amadeus_service,
            model_client=self._model_client_qwen_2_5,
        )

        self.planning_agent = AssistantAgent(
            "PlanningAgent",
            description=planning_agent_description,
            system_message=planning_agent_prompt if critic_enabled else planning_agent_prompt_no_critic,
            model_client=self._model_client_qwen_2_5,
        )

        self.user_proxy_agent = UserProxyAgent(
            name="UserProxyAgent",
            description=user_proxy_agent_description,
            input_func=user_input_func
        )

        self.text_mention_termination = TextMentionTermination("TERMINATE")
        self.max_messages_termination = MaxMessageTermination(max_messages=1000)
        self.termination = self.text_mention_termination | self.max_messages_termination

        if critic_enabled:
            self.participants = [
                self.planning_agent,
                self.user_proxy_agent,
                self.web_scraper_agent, 
                self.search_agent, 
                self.content_generation_agent, 
                self.critic_agent, 
                self.transaction_agent, 
            ]
        else:
            self.participants = [
                self.planning_agent,
                self.user_proxy_agent,
                self.web_scraper_agent, 
                self.search_agent, 
                self.content_generation_agent, 
                self.transaction_agent, 
            ]

        self.team = SelectorGroupChat(
            participants=self.participants,
            termination_condition=self.termination,
            selector_prompt=selector_prompt,
            model_client=self._model_client_qwen_2_5,
            selector_func=selector_func,
            max_turns=100,
            allow_repeated_speaker=False,  # Allow an agent to speak multiple turns in a row.
        )

    async def retrieve_generated_plan(self) -> str:
        timer_tag = f"main:_fetch_plan_from_redis"
        contant_generation_agent_name = "ContentGenerationAgent"
        self._timer_client.start(timer_tag)
        try:
            plan = await self._local_state_service.get_generated_plan(contant_generation_agent_name, self._session_id)
            if plan:
                self._timer_client.stop(timer_tag)
                logger.info(f"[Main] Retrieved generated plan for session {self._session_id}, and spent {self._timer_client.execution_times.get(timer_tag, 0)} seconds to ran.")
                return plan
            else:
                # logger.info(f"[Main] No generated plan found for session {self._session_id}.")
                logger.warning(f"[Main] No generated plan found in local state for session {self._session_id}.")
                self._timer_client.stop(timer_tag)
                logger.info(f"[Main] No generated plan found for session {self._session_id}, and spent {self._timer_client.execution_times.get(timer_tag, 0)} seconds to ran.")
                return ""
        except Exception as e:
            logger.error(f"[Main] Failed to get generated plan: {e}")
            self._timer_client.stop(timer_tag)
            logger.info(f"[Main] Failed to get generated plan and spent {self._timer_client.execution_times.get(timer_tag, 0)} seconds to ran.")
            return ""

    def get_all_number_of_rounds_from_agents(self) -> dict:
        number_of_rounds = {
            "web_scraper_agent_rounds": self.web_scraper_agent.get_number_of_rounds(),
            "search_agent_rounds": self.search_agent.get_number_of_rounds(),
            "content_generation_agent_rounds": self.content_generation_agent.get_number_of_rounds(),
            "critic_agent_rounds": self.critic_agent.get_number_of_rounds(),
            "transaction_agent_rounds": self.transaction_agent.get_number_of_rounds(),
        }
        return number_of_rounds
    
    def get_list_of_scraping_history(self) -> list:
        list_of_scraping_hitory = self.web_scraper_agent.get_list_of_scraping_history()
        return list_of_scraping_hitory
    
    def get_list_of_search_modes_and_errors(self) -> list:
        search_modes_and_errors = self.search_agent.get_list_of_search_modes_and_errors()
        return search_modes_and_errors
    
    def get_list_of_reasoning_and_decisions(self) -> list:
        list_of_reasoning_and_decision = self.critic_agent.get_list_of_reasoning_and_decision()
        return list_of_reasoning_and_decision

    def get_list_of_generated_records(self) -> list:
        list_of_generated_records = self.content_generation_agent.get_list_of_generated_records()
        return list_of_generated_records

    async def process_user_message(self, message: str, user_profile: dict, user_travel_details: dict) -> dict:
        path = f"{self.folder}/generated_plans.jsonl"

        await self._local_state_service.set_user_profile(self._type_of_agent, self._session_id, user_profile=user_profile)
        await self._local_state_service.set_user_travel_details(self._type_of_agent, self._session_id, travel_details=user_travel_details)
        async for m in self.team.run_stream(task=message): 
            log_agent_message(m)
        # await Console(self.team.run_stream(task=message))

        plan = await self.retrieve_generated_plan()
        await self._redis_store.aclose() # close redis after the task is done
        return plan

    async def test_web_scraper_agent(self):
        self.web_scraper_agent = self.web_scraper_agent
        
        test_message = TextMessage(
            content="WebScraperAgent: Gather content on traditional arts, local cuisine, cultural experiences, market exploration, and seafood in Tokyo.",
            source="PlanningAgent"
        )

        print("=== Running WebScraperAgent.on_messages_stream ===")
        async for event in self.web_scraper_agent.on_messages_stream([test_message], cancellation_token=CancellationToken()):
            print(event)

    async def test_search_agent(self):
        queries = [
            "SearchAgent: Search for flights from San Francisco to Tokyo, departing on October 10, 2025, and returning on October 16, 2025, prioritizing Alaska Airline.",
            "SearchAgent: Search for hotels in Tokyo, near city center, suitable for a 7-day stay, considering Hilton Hotel or Airbnb options with moderate budget.",
            "SearchAgent: Search for attractions in Tokyo aligned with traditional arts, local cuisine, cultural experiences, market exploration, and seafood interests.",
            "SearchAgent: Search for tours in Tokyo that match traditional arts, local cuisine, cultural experiences, market exploration, and seafood interests."
        ]

        for query in queries:
            test_message = TextMessage(
                content=query,
                source="PlanningAgent"
            )

            print(f"=== Running SearchAgent.on_messages_stream for query: {query} ===")
            async for event in self.search_agent.on_messages_stream([test_message], cancellation_token=CancellationToken()):
                print(event)

    async def test_content_generation_agent(self):
        test_message = TextMessage(
            content="ContentGenerationAgent: Generate a 7-day itinerary based on user preferences.",
            source="PlanningAgent"
        )

        print("=== Running ContentGenerationAgent.on_messages_stream ===")
        async for event in self.content_generation_agent.on_messages_stream([test_message], cancellation_token=CancellationToken()):
            if hasattr(event, "content"):
                print("\n=== Streamed Output ===")
                print(event.content)

    async def test_critic_agent(self):
        test_message = TextMessage(
            content="CriticAgent: Evaluate the travel plan based on the user's query and preferences.",
            source="PlanningAgent"
        )

        print("=== Running CriticAgent.on_messages_stream ===")
        async for event in self.critic_agent.on_messages_stream([test_message], cancellation_token=CancellationToken()):
            # print(event)
            if isinstance(event, Response):
                if isinstance(event.chat_message, TextMessage):
                    print("\n=== Streamed Output ===")
                    print(event.chat_message.content)

    async def test_transaction_agent(self):
        test_message = TextMessage(
            content="TransactionAgent: Book a round-trip flight from San Francisco to Tokyo, departing on October 10, 2025, and returning on October 16, 2025, prioritizing Alaska Airline.",
            source="PlanningAgent"
        )

        print("=== Running TransactionAgent.on_messages_stream ===")
        async for event in self.transaction_agent.on_messages_stream([test_message], cancellation_token=CancellationToken()):
            # print(event)
            if isinstance(event, Response):
                if isinstance(event.chat_message, TextMessage):
                    print("\n=== Streamed Output ===")
                    print(event.chat_message.content)
