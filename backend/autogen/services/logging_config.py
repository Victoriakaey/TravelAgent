import time
import logging
import os

ALLOWED_INFO_MODULES = [
    "autogen.services.utils",
    "autogen.agents.scraper.WebScraperAgent",
    "autogen.agents.scraper.WebScraperTool",
    "autogen.agents.critic.CriticAgent",
    "autogen.agents.critic.CriticTool",
    "autogen.agents.search.SearchAgent",
    "autogen.agents.search.SearchAgentWithCriticOption",
    "autogen.agents.generation.ContentGenerationAgent",
    "autogen.agents.generation.ContentGenerationTool",
    "autogen.agents.generation.SearchResultToMarkdown",
    "autogen.agents.transaction.TransactionAgent",
    "autogen.agents.resource_selection.ResourceSelectionAgent",
    "autogen.agents.scraper.helpers._scrape_content_from_url",
    "autogen.agents.source._ollama_client",
    "autogen.agents.agent_group",
    "autogen.agents.agent_group.AgentGroup",
    "autogen.evaluation.ground_truth_curation.evaluation",
    "autogen.main",
    "__main__"
]

VERBOSE = 15  # Between DEBUG (10) and INFO (20)
logging.addLevelName(VERBOSE, "VERBOSE")

def verbose(self, message, *args, **kwargs):
    if self.isEnabledFor(VERBOSE):
        self._log(VERBOSE, message, args, **kwargs)

# Attach to Logger class
logging.Logger.verbose = verbose

class OnlyAutogenFilter(logging.Filter):
    """Allow only autogen-related logs for the info file."""
    def filter(self, record):
        return record.name in ALLOWED_INFO_MODULES

def _write_new_session_header(path: str):
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n")
        f.write("=" * 80 + "\n")
        f.write(f" NEW LOGGING SESSION STARTED — {time.strftime('%Y-%m-%d %H:%M:%S')} \n")
        f.write("=" * 80 + "\n\n")

def setup_logging(log_to_file=False, debug_log_file=None, info_log_file=None, verbose_log_file=None):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) # Root must be DEBUG so all handlers can filter properly
    logger.handlers.clear()

    # Prevent duplicate handlers if setup is called multiple times
    if logger.hasHandlers():
        return
    
    # Plain formatter for file logs
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(VERBOSE)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(OnlyAutogenFilter()) 
    logger.addHandler(console_handler)

    if log_to_file:

        # === DEBUG File Handler (all logs) ===
        if debug_log_file:
            os.makedirs(os.path.dirname(debug_log_file), exist_ok=True)
            debug_handler = logging.FileHandler(debug_log_file, mode="a", encoding="utf-8")
            debug_handler.setLevel(logging.DEBUG)  # Capture everything
            debug_handler.setFormatter(formatter)
            logger.addHandler(debug_handler)
            _write_new_session_header(debug_log_file)

        # === INFO File Handler (autogen only) ===
        if info_log_file:
            os.makedirs(os.path.dirname(info_log_file), exist_ok=True)
            info_handler = logging.FileHandler(info_log_file, mode="a", encoding="utf-8")
            info_handler.setLevel(logging.INFO)
            info_handler.setFormatter(formatter)
            info_handler.addFilter(OnlyAutogenFilter())  
            logger.addHandler(info_handler)
            _write_new_session_header(info_log_file)

        # === VERBOSE File Handler (autogen only) ===
        if verbose_log_file:
            os.makedirs(os.path.dirname(verbose_log_file), exist_ok=True)
            verbose_handler = logging.FileHandler(verbose_log_file, mode="a", encoding="utf-8")
            verbose_handler.setLevel(VERBOSE)
            verbose_handler.setFormatter(formatter)
            verbose_handler.addFilter(OnlyAutogenFilter())  
            logger.addHandler(verbose_handler)
            _write_new_session_header(verbose_log_file)

    return logger
