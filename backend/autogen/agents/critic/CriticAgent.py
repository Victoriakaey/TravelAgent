import json
import logging
from pydantic import BaseModel
from typing import Sequence, AsyncGenerator
from autogen_agentchat.base import Response
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import BaseAgentEvent
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_core import CancellationToken, ComponentModel, Component

from .CriticTool import CriticTool
from ._utils import critic_agent_description, retry_message_str
from autogen.services import TimingTracker, LocalStateService, RedisStorage

logger = logging.getLogger(__name__)

class CriticAgentConfig(BaseModel):
    name: str
    description: str = critic_agent_description

class CriticAgent(AssistantAgent, Component[CriticAgentConfig]):

    def __init__(
            self, 
            user_profile: dict, 
            user_travel_details: dict, 
            session_id: str,
            redis_store: RedisStorage,
            model_name: str,
            model_client: ComponentModel,
            timer_client: TimingTracker,
            time_log_filename: str,
            name: str = "CriticAgent",  
            test_mode: bool = False,
            plan: str = ""
        ):

        super().__init__(name=name, model_client=model_client)

        self._name = name
        self._session_id = session_id
        self._redis_store = redis_store
        self._type_of_agent = "CriticService"
        self._content_generation_agent_name = "ContentGenerationAgent"
        self._local_state_service = LocalStateService(redis_store=self._redis_store)

        self.timer = timer_client
        self.time_log_filename = time_log_filename

        self.critic_agent = CriticTool(user_profile=user_profile, user_travel_details=user_travel_details, model_name=model_name)
        self.number_of_rounds = 0
        self.list_of_reasoning_and_decision = []

        self.travel_info = {
            "origin": user_travel_details.get("origin", ""),
            "destination": user_travel_details.get("destination", ""),
            "duration": user_travel_details.get("duration", ""),
        }

        self.suggestions_ls = []
        self.scores_ls = []
        self.decisions_ls = []
        self.reasoning_ls = []
        self.checklist_ls = []
        self.raw_responses_ls = []

        self.plan = None
        if test_mode:
            logger.info(f"[CriticAgent] Initialized in test mode.")
            logger.verbose(f"Criticing the plan: {plan}")
            self.plan = plan
        
    def get_number_of_rounds(self) -> int:
        return self.number_of_rounds
    
    def get_list_of_reasoning_and_decision(self) -> list:
        return self.list_of_reasoning_and_decision
    
    def get_scores_ls(self) -> list:
        return self.scores_ls
    
    def get_decisions_ls(self) -> list:
        return self.decisions_ls
    
    def get_suggestions_ls(self) -> list:
        return self.suggestions_ls
    
    def get_reasoning_ls(self) -> list:
        return self.reasoning_ls
    
    def get_checklist_ls(self) -> list:
        return self.checklist_ls
    
    def get_raw_responses_ls(self) -> list:
        return self.raw_responses_ls

    async def _get_itinerary_text(self) -> str:
        timer_tag = f"critic:{self.number_of_rounds}_fetch_itinerary_from_redis"
        self.timer.start(timer_tag)
        try:
            itinerary = await self._local_state_service.get_generated_plan(self._content_generation_agent_name, self._session_id)
            if itinerary:
                # logger.info(f"[CriticAgent] Retrieved generated plan for session {self._session_id}.")
                self.timer.stop(timer_tag)
                logger.info(f"[CriticAgent] Retrieved generated plan for session {self._session_id}, and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
                return itinerary
            else:
                # logger.info(f"[CriticAgent] No generated plan found for session {self._session_id}.")
                logger.warning(f"[CriticAgent] No generated plan found in local state for session {self._session_id}.")
                self.timer.stop(timer_tag)
                logger.info(f"[CriticAgent] No generated plan found for session {self._session_id}, and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
                return ""
        except Exception as e:
            logger.error(f"[CriticAgent] Failed to get generated plan: {e}")
            self.timer.stop(timer_tag)
            logger.info(f"[CriticAgent] Failed to get generated plan and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
            return ""

    async def on_messages(self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken | None = None) -> Response:
        if self.plan:
            itinerary_text = self.plan
        else:
            itinerary_text = await self._get_itinerary_text() 

        if not itinerary_text:
            logger.warning(f"[{self.name}] No itinerary text found.")
            return Response(chat_message=TextMessage(content="No itinerary text found.", source=self.name))
        
        # logger.verbose(f"[{self.name}] Starting Critic Agent with itinerary:\n{itinerary_text}")

        # Try up to N times to get a valid structured response
        max_retries = 2
        retry_message = ""

        checklist: dict = {}
        scores: dict = {}
        decision: str = "RE-WRITE"
        suggestions: str = ""
        reasoning: str = ""
        response_text: str | None = None

        for attempt in range(max_retries):
            response_text = self.critic_agent.run(itinerary_text, retry_message)
            logger.verbose(f"[{self.name}] Critic Agent response (attempt {attempt+1}):\n{response_text}")

            if self.critic_agent.verify_response_format(response_text):
                logger.verbose(f"[{self.name}] Response format is valid.")
                break
            else:
                logger.warning(f"[{self.name}] Invalid response format on attempt {attempt+1}. Retrying...") 
                retry_message = retry_message_str

        # If still invalid after retries, fall back
        if not response_text or not self.critic_agent.verify_response_format(response_text):
            logger.error(f"[{self.name}] Critic Agent failed to produce valid format after {max_retries} attempts.")
            decision = "RE-WRITE" # Fallback: force a RE-WRITE decision
        else:
            checklist = self.critic_agent.extract_checklist(response_text)
            scores = self.critic_agent.extract_scores(response_text)
            decision = self.critic_agent.extract_decision(response_text)
            suggestions = self.critic_agent.extract_suggestions(response_text)
            reasoning = self.critic_agent.extract_reasoning(response_text)

        reasoning_and_decision = {
            "round": self.number_of_rounds,
            "decision": decision,
            "scores": scores,
            "suggestions": suggestions,
            "reasoning": reasoning,
            "itinerary": itinerary_text,
            "checklist": checklist,
            "raw_response": response_text,
        }

        self.list_of_reasoning_and_decision.append(reasoning_and_decision)
        self.scores_ls.append(scores)
        self.decisions_ls.append(decision)
        self.suggestions_ls.append(suggestions)
        self.reasoning_ls.append(reasoning)
        self.checklist_ls.append(checklist)
        self.raw_responses_ls.append(response_text)

        logger.info(f"[{self.name}] Reasoning:\n{reasoning}\n")
        logger.info(f"[{self.name}] Checklist:\n{checklist}\n")
        logger.info(f"[{self.name}] Scores: {scores}\n")
        logger.info(f"[{self.name}] Suggestions: {suggestions}\n")
        logger.info(f"[{self.name}] Decision: {decision}\n")
        logger.info(f"[{self.name}] Raw Response:\n{response_text}\n")
        
        await self._local_state_service.store_critic_reasoning(self._name, self._session_id, reasoning)
        await self._local_state_service.store_critic_checklist(self._name, self._session_id, json.dumps(checklist))
        await self._local_state_service.store_critic_scores(self._name, self._session_id, json.dumps(scores))
        await self._local_state_service.store_critic_suggestions(self._name, self._session_id, json.dumps(suggestions))
        await self._local_state_service.store_critic_decision(self._name, self._session_id, decision)
        await self._local_state_service.store_critic_raw_response(self._name, self._session_id, response_text)

        return Response(chat_message=TextMessage(content=f"[CriticAgent] Critic Agent's Decision: {decision.lower()}. Saving reasoning and decision to state for session `{self._session_id}`", source=self.name))

    async def on_messages_stream(self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken | None = None) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | Response, None]:
        self.number_of_rounds += 1
        timer_tag = f"critic:{self.number_of_rounds}_critic_agent_run"
        self.timer.start(timer_tag)
        logger.info(f"[CriticAgent] Starting streaming critic for messages for the {self.number_of_rounds}-th times...")
        result = await self.on_messages(messages, cancellation_token)
        logger.verbose(f"[CriticAgent] List of reasoning and decision so far: {self.list_of_reasoning_and_decision}\n")
        self.timer.stop(timer_tag)
        logger.info(f"[CriticAgent] Finished streaming critic and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        self.timer.save_as_text(filename=self.time_log_filename)
        yield result

    def _to_config(self):
        """Convert the agent to a configuration object."""
        return CriticAgentConfig(
            name=self.name,
            description=critic_agent_description
        )

    @classmethod
    def _from_config(cls, config: CriticAgentConfig):
        """Create an agent from a configuration object."""
        return cls(
            user_profile={},
            user_travel_details={},
            session_id="",
            redis_store=RedisStorage(),
            model_client=OllamaChatCompletionClient(model="qwen2.5"),  # Use default model client
            name=config.name
        )
