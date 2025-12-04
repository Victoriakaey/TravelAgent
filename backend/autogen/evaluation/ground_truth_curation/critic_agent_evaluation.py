import uuid
import asyncio
import logging
from pathlib import Path
from autogen_core import CancellationToken
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.ollama import OllamaChatCompletionClient

from .helpers import load_any
from autogen.agents import CriticAgent
from autogen.services import setup_logging, saving_object_to_jsonl, TimingTracker, LocalStateService, RedisStorage

logger = logging.getLogger(__name__)

class CriticAutoEvaluation:

    def __init__(self, user_profile: dict, user_travel_details: dict, plan: str, folder: str = "log/ground_truth_evaluation/critic-agent"):
        
        self._content_generation_agent_name = "ContentGenerationAgent"
        self._session_id = "critic_auto_evaluation_" + str(uuid.uuid4())

        self._redis_store = RedisStorage()
        self._local_state_service = LocalStateService(redis_store=self._redis_store)

        self._user_id = user_travel_details.get("user_id", "unknown_user")
    
        self.folder = folder

        file_starter =  f"{self.folder}/{user_profile['user_id']}"
        info_log_filename = file_starter + "/info_runtime.log"
        verbose_log_filename = file_starter + "/verbose_runtime.log"

        setup_logging(
            log_to_file=True,
            info_log_file= info_log_filename,  # INFO Level
            verbose_log_file= verbose_log_filename  # VERBOSE Level
        )

        logger.info(f"Saving info logs to {info_log_filename}")
        logger.info(f"Saving verbose logs to {verbose_log_filename}")

        self._timer_client = TimingTracker(user_id=self._user_id, output_folder="")
        self._time_log_filename = file_starter + "/content_agent_timing.log"

        self._model_client = OllamaChatCompletionClient(model="deepseek-r1") # qwen3

        self.critic_agent = CriticAgent(
            user_profile=user_profile,
            user_travel_details=user_travel_details,
            session_id=self._session_id,
            redis_store=self._redis_store,
            timer_client=self._timer_client,
            time_log_filename=self._time_log_filename,
            model_name="deepseek-r1",
            model_client=self._model_client,
            test_mode=True,
            plan=plan
        )

    def get_preferences_and_constraints_counts_ls(self):
        return self.critic_agent.preferences_and_constraints_counts_ls
    
    def get_suggestions_ls(self):
        return self.critic_agent.suggestions_ls

    def get_scores_ls(self):
        return self.critic_agent.scores_ls
    
    def get_decisions_ls(self):
        return self.critic_agent.decisions_ls
    
    def get_reasoning_ls(self):
        return self.critic_agent.reasoning_ls
    
    def get_checklist_ls(self):
        return self.critic_agent.checklist_ls

    def get_raw_responses_ls(self):
        return self.critic_agent.raw_responses_ls
        
    async def process_user_message(self):
        message = TextMessage(
            content="CriticAgent: Evaluate the relevance and quality of the selected resources from filtered_content and search_results based on the user's query and preferences.",
            source="PlanningAgent"
        )

        await self.critic_agent.on_messages([message], cancellation_token=CancellationToken())

        preferences_and_constraints_counts_path = f"{self.folder}/artifacts/preferences_and_constraints_counts.jsonl"
        suggestions_path = f"{self.folder}/artifacts/suggestions.jsonl"
        scores_path = f"{self.folder}/artifacts/scores.jsonl"
        decisions_path = f"{self.folder}/artifacts/decisions.jsonl"
        reasoning_path = f"{self.folder}/artifacts/reasoning.jsonl"
        checklist_path = f"{self.folder}/artifacts/checklist.jsonl"
        raw_responses_path = f"{self.folder}/artifacts/raw_responses.jsonl"

        preferences_and_constraints_counts = self.get_preferences_and_constraints_counts_ls()
        suggestions = self.get_suggestions_ls()
        scores = self.get_scores_ls()
        decisions = self.get_decisions_ls()
        reasoning = self.get_reasoning_ls()
        checklist = self.get_checklist_ls()
        raw_responses = self.get_raw_responses_ls()

        saving_object_to_jsonl(preferences_and_constraints_counts, preferences_and_constraints_counts_path)
        saving_object_to_jsonl(suggestions, suggestions_path)
        saving_object_to_jsonl(scores, scores_path)
        saving_object_to_jsonl(decisions, decisions_path)
        saving_object_to_jsonl(reasoning, reasoning_path)
        saving_object_to_jsonl(checklist, checklist_path)
        saving_object_to_jsonl(raw_responses, raw_responses_path)
    
async def run_critic_agent_evaluation(user_profile: dict, user_travel_details: dict, plan: str):
    group = CriticAutoEvaluation(
        user_profile=user_profile, 
        user_travel_details=user_travel_details,
        plan=plan,
        folder="log/ground_truth_evaluation/critic-agent-10"
    )
    await group.process_user_message()

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent

    users_path = base_dir / "data/user_cases.jsonl"
    plan_path = base_dir / "data/plans.jsonl"

    # --- Load inputs with helpful logs ---
    logger.info(f"Loading users from {users_path}")
    users = load_any(users_path)
    logger.info(f"Loaded {len(users)} users")

    logger.info(f"Loading ground-truth plans from {plan_path}")
    plans = load_any(plan_path)
    logger.info(f"Loaded {len(plans)} plans")

    # Defensive checks
    if not isinstance(users, list):
        raise TypeError(f"Expected users to be a list, got {type(users)}")
    if not isinstance(plans, list):
        raise TypeError(f"Expected plans to be a list, got {type(plans)}")

    # Length alignment check with informative message
    if len(users) != len(plans):
        logger.warning(
            f"Users/Plans length mismatch: users={len(users)} vs plans={len(plans)}. "
            "Proceeding with the minimum length."
        )

    # Iterate safely over the aligned range; keep the original semantics
    N = min(len(users), len(plans))
    for i in range(N):
        current_user = users[i]
        current_plan = plans[i]

        # Light validation to fail fast if structure drifts
        if "user_profile" not in current_user or "user_travel_details" not in current_user:
            logger.error(f"User record at index {i} missing expected keys: {list(current_user.keys())}")
            continue

        user_profile = current_user["user_profile"]
        user_travel_details = current_user["user_travel_details"]

        # run critic here
        asyncio.run(run_critic_agent_evaluation(
            user_profile=user_profile,
            user_travel_details=user_travel_details,
            plan=current_plan
        ))


# python -m autogen.evaluation.ground_truth_curation.critic_agent_evaluation