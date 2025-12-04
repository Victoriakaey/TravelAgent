import os
import json

from ._scrape_content_from_url import scrape_and_filter

def ensure_directory_exists(file_path: str):
    """
    Ensures the directory for the given file path exists.
    Creates it if it does not already exist.
    """
    directory = os.path.dirname(file_path)
    if directory:  # If the file is in a directory (not the current folder)
        os.makedirs(directory, exist_ok=True)

def save_payload_to_file(payload: dict, filename: str) -> None:
    """Save the payload to a JSON file."""
    ensure_directory_exists(filename)
    with open(filename, 'w') as file:
        json.dump(payload, file, indent=4)


def save_message_to_file(message: str, filename: str) -> None:
    """Save the message to a text file."""
    ensure_directory_exists(filename)
    with open(filename, 'w') as file:
        file.write(message)

def save_everything_to_file(data: dict, filename: str) -> None:
    """Save the entire response to a JSON file."""
    ensure_directory_exists(filename)
    with open(filename, "w") as f:
        if isinstance(data, dict):
            f.write(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            f.write(str(data))
        f.write("\n\n")

def write_content_to_file(content, filename: str):
    ensure_directory_exists(filename)
    with open(filename, "w") as f:
        if isinstance(content, str):
            f.write(content)
        else:
            json.dump(content, f, indent=2)
    print(f"Content written to {filename}")

async def save_sources_to_file(query: str, sources: list, log_path: str) -> list:
    """Save the sources to a text file."""
    results = []

    for i, source in enumerate(sources):
        current_chunk = {
            "query": query,
            "title": source['metadata']['title'],
            "url": source['metadata']['url'],
            "metadata": {},
            "raw_html": "",
            "clean_content": "",
            "chunks": []
        }
       
        scraped_result = await scrape_and_filter(url=source['metadata']['url'], log_path=log_path)
        current_chunk["metadata"] = scraped_result['metadata']
        current_chunk["raw_html"] = scraped_result['raw_html']
        current_chunk["clean_content"] = scraped_result['clean_content']

        c = []
        for i, chunk in enumerate(scraped_result["chunks"]):
            c.append(chunk)

        current_chunk["chunks"].append(c)
        results.append(current_chunk)
        
    # print(f"{len(results)}")
    return results

