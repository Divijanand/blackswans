import concurrent.futures
import json
import os
import requests

# Constants
RESULTS_FILE = "results.jsonl"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") # Make sure this is in your environment

def load_existing_results():
    """Reads the JSONL file and returns a set of already processed event IDs."""
    processed_ids = set()
    
    # If this is the first time running, the file won't exist yet
    if not os.path.exists(RESULTS_FILE):
        return processed_ids
    
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    # Assuming your events have a unique 'id' or 'event_id'
                    if 'event_id' in data:
                        processed_ids.add(data['event_id'])
                except json.JSONDecodeError:
                    continue
                    
    return processed_ids

def classify_event(event, model_id):
    """Calls OpenRouter, enforces JSON, and returns the parsed dictionary."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # This is where your classifier prompt goes. Notice the explicit JSON instruction.
    system_prompt = (
        "You are an expert wargaming classifier. "
        "Classify the following event. You MUST respond ONLY with a valid JSON object "
        "using this exact schema: {\"classification\": \"Black Swan|Gray Rhino|etc\", "
        "\"check1_verdict\": \"YES|NO\", \"check2_verdict\": \"YES|NO\", "
        "\"check3_verdict\": \"YES|NO\", \"load_bearing_assumption\": \"string\", "
        "\"reasoning\": \"string\"}"
    )
    
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Event details: {event['description']}"}
        ],
        # If the model supports it, force JSON mode via API parameters here
        "response_format": {"type": "json_object"} 
    }
    
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    response.raise_for_status() # Throw an error if the request fails (e.g., 429 Too Many Requests)
    
    raw_content = response.json()['choices'][0]['message']['content']
    
    # The crucial try/except for structured output
    try:
        parsed_json = json.loads(raw_content)
        # Attach the original event ID so we can track it
        parsed_json['event_id'] = event['event_id'] 
        return parsed_json
    except json.JSONDecodeError:
        # Fallback if the model completely fails to output JSON
        return {
            "event_id": event['event_id'],
            "error": "Failed to parse JSON",
            "raw_response": raw_content
        }

def run_classifier(events, model_id, max_workers=15):
    """Runs the classification concurrently and writes results instantly."""
    done_ids = load_existing_results()
    
    # Filter out anything we've already successfully processed
    remaining_events = [e for e in events if e['event_id'] not in done_ids]
    
    print(f"Total events: {len(events)} | Cached: {len(done_ids)} | Remaining to process: {len(remaining_events)}")

    # Fire up the concurrent threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        
        # Map the remaining events to the execution threads
        future_to_event = {executor.submit(classify_event, e, model_id): e for e in remaining_events}
        
        # As soon as ANY thread finishes, process its result
        for future in concurrent.futures.as_completed(future_to_event):
            event = future_to_event[future]
            try:
                result = future.result()
                
                # Write to the file IMMEDIATELY. Do not wait for everything to finish.
                with open(RESULTS_FILE, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(result) + '\n')
                    
                print(f"Successfully processed event {event['event_id']}")
                
            except Exception as exc:
                print(f"Event {event['event_id']} crashed the thread: {exc}")

# --- How to actually run it ---
if __name__ == "__main__":
    # Dummy data: This is where Yevhen's dataset will actually plug in
    mock_dataset = [
        {"event_id": 1, "description": "DeepSeek releases R1 model breaking frontier lab cost floors."},
        {"event_id": 2, "description": "Nvidia announces Blackwell architecture delays."}
    ]
    
    # Pick a model from your model-list.md
    target_model = "meta-llama/llama-3-8b-instruct" 
    
    # run_classifier(mock_dataset, target_model)