import json
from typing import List, Any
from autogen_ext.models.ollama._model_info import _MODEL_TOKEN_LIMITS, get_token_limit
    
def get_safe_max_characters(model: str) -> int:
    if model not in _MODEL_TOKEN_LIMITS:
        raise ValueError(f"Model '{model}' not found in token limits.")
    
    max_tokens = _MODEL_TOKEN_LIMITS[model]
    safe_max_chars = int(max_tokens * 3 * 0.7)  # ~70% of max tokens, ~3 chars per token

    return safe_max_chars

def check_number_of_characters(text: Any) -> int:
    """
    Count characters in different input types:
    - str: length directly
    - list/dict: JSON serialization (no ASCII escaping)
    - other: convert to string
    """
    if isinstance(text, str):
        return len(text)
    elif isinstance(text, (list, dict)):
        return len(json.dumps(text)) # ensure_ascii=False to avoid extra escaping
    else:
        return len(str(text))

def slice_items_to_batch(logger: Any, items: List[dict], number_of_batch: int = 5) -> list:
    if not items:
        logger.warning("[ResourceSelectionAgent] No items to slice; returning empty list.")
        return []
    
    batches = []
    len_items = len(items)

    if len_items <= number_of_batch:
        logger.info(f"[ResourceSelectionAgent] Number of items ({len_items}) less than or equal to number_of_batch ({number_of_batch}); no slicing needed.")
        return items
    else:
        item_in_each_batch = len_items // number_of_batch
        logger.info(f"Number of items: {len_items}, slicing into {number_of_batch} batches, each with ~{item_in_each_batch} items.")
        for i in range(0, len_items, item_in_each_batch):
            # logger.info(f"Slicing items from index {i} to {i + item_in_each_batch}")
            current_item = items[i:i + item_in_each_batch]
            logger.info(f"Batch {i+1}: {len(current_item)} items.")
            batches.append(current_item)
        logger.info(f"Total batches created: {len(batches)}")
    return batches

# print(get_safe_max_characters("qwen3"))
# print(get_safe_max_characters("deepseek-r1"))

# items = [{"id": i} for i in range(1, 10)]
# print(items)
# sliced_batches = slice_items_to_batch(items, number_of_batch=4)