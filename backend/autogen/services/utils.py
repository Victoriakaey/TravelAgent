import re
import os
import json
import logging
from typing import Sequence, Optional
from autogen_agentchat.messages import BaseAgentEvent, BaseChatMessage, TextMessage

logger = logging.getLogger(__name__)

AGENTS = [
    "WebScraperAgent",
    "SearchAgent",
    "ContentGenerationAgent",
    "CriticAgent",
    "TransactionAgent",
    "UserProxyAgent",
    "PlanningAgent",
    "SearchAgentWithCriticOption"
]

def log_agent_message(message: BaseChatMessage) -> None:
    """Pretty-print each agent message in a readable format."""
    if not isinstance(message, TextMessage):
        return

    source = message.source or "Unknown"
    content = (message.content or "").strip()

    if not content:
        return

    logger.info("\n" + "─" * 60)
    logger.info(f"Speaker: {source}\n")
    logger.info(f"Content: {content}\n")
    logger.info("\n" + "─" * 60)

def log_selector_decision(agent_name: str) -> None:
    logger.debug(f"Selector Decision: → {agent_name}")

def no_block_user_input(_prompt: str) -> str: 
    return "Confirmed, no more preference or contraints"

def user_input_func(prompt: str = "") -> str:
    prompt_text = prompt.strip() if prompt else "Please enter your message"
    logger.debug(f"[DEBUG] Prompt received by user_input_func: {repr(prompt)}")
    return input(f"\nUser Input ({prompt_text}): \n").strip()

def route_by_agent_mention(sender, agents, message):
    if sender.name != "PlanningAgent":
        return []  # Only route if PlanningAgent is speaking

    mentioned = []
    for agent in agents:
        pattern = rf"{re.escape(agent.name)}\s*:"

        if re.search(pattern, message, re.IGNORECASE):
            mentioned.append(agent)
    
    if not mentioned:
        logger.debug(f"No agents mentioned in message: {message}")
        return [agent for agent in agents if agent.name == "UserProxyAgent"]

    logger.debug(f"[Selector] Routing to: {[a.name for a in mentioned]}")
    return mentioned  # supports multi-agent mentions now

def selector_func(messages: Sequence[BaseAgentEvent | BaseChatMessage]) -> str | None:
    if not messages:
        return "PlanningAgent"

    last = messages[-1]
    if not isinstance(last, BaseChatMessage):
        return "PlanningAgent"

    content = (last.content or "").strip()

    if content == "TERMINATE":
        return "TERMINATE"

    # Always route based on the first word (e.g., "WebScraperAgent:")
    first_token = content.split(" ", 1)[0]
    if first_token.endswith(":"):
        agent_candidate = first_token[:-1]
        if agent_candidate in AGENTS:
            return agent_candidate

    # Fallback
    return "PlanningAgent"

def normalize(obj):
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [normalize(v) for v in obj]
    elif isinstance(obj, set):
        return list(obj)
    else:
        return obj

def saving_object_to_jsonl(obj: dict, filepath: str) -> None:
    dirpath = os.path.dirname(filepath)

    # Create directory only if dirpath is not empty
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    normalized_obj = normalize(obj)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(normalized_obj, ensure_ascii=False) + "\n")
