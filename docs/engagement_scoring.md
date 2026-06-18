# **Feature Implementation Document: Engagement Scoring**

## **Overview**

This document outlines the implementation plan for the Engagement Scoring feature in the Mistria AI FastAPI application. The system will asynchronously calculate a user's engagement score (1-100) based on recent chat interactions and send a webhook to an external backend server whenever the score changes.

## **Architecture & Flow**

1. **Trigger:** After a complete conversational turn (User Message \+ AI Response) is successfully processed in the main WebSocket chat loop, a background task is triggered.  
2. **Context Assembly:** The background task retrieves the N most recent messages (e.g., last 3-5 turns) for the current conversation.  
3. **LLM Evaluation:** The task constructs a specific prompt and calls the embedded LLM inference engine (vLLM/Ollama) to evaluate the engagement level. The LLM is instructed to output *only* an integer between 1 and 100\.  
4. **State Management (RAM):** The calculated score is compared against the "last known score" for that specific conversation\_id. This state is maintained in-memory (RAM) using a simple dictionary structure.  
5. **Webhook Dispatch:** If the newly calculated score is different from the last known score (even by 1 point), an asynchronous, fire-and-forget HTTP POST request is sent to the external Node.js backend.  
6. **Error Handling:** If the webhook request fails, the error is logged, but the execution continues (drop and ignore).

## **Component Breakdown & Implementation Steps**

The implementation should be modular and follow the existing architectural patterns of the repository (e.g., similar to how memory/background.py operates).

### **1\. Configuration (src/config.py)**

Add necessary configuration variables to support the external webhook and scoring parameters.

* **Changes:**  
  * Add an environment variable EXTERNAL\_BACKEND\_WEBHOOK\_URL (default to a dummy URL or None).  
  * Add ENGAGEMENT\_HISTORY\_LIMIT (integer, default 10 messages).

### **2\. State Management & Data Structures**

We need a thread-safe way to store the last known score in memory.

* **File:** Create a new file or module, e.g., src/engagement/state.py (or integrate into an existing state manager if appropriate).  
* **Structure:** A global dictionary mapping conversation\_id (string/UUID) to the last known score (integer).

```python
# Conceptual example
from typing import Dict
from uuid import UUID

# { conversation_id: last_known_score }
_last_known_scores: Dict[str, int] = {}

def get_last_score(conversation_id: str) -> int | None:
    ...
def set_last_score(conversation_id: str, score: int) -> None:
    ...
```

### **3\. Prompt Design (src/prompts.py or src/engagement/prompts.py)**

Create a strict system prompt designed to force the LLM to output only a numeric value.

* **Prompt Name:** ENGAGEMENT\_SCORING\_PROMPT  
* **Prompt Concept:**  
  "You are an expert behavioral analyst. Evaluate the following conversation between a User and an AI Companion. Score the user's engagement, interest level, conversational flow, and intimacy/intensity on a scale from 1 to 100\.  
  1 \= completely disinterested, hostile, or disengaged.  
  100 \= highly engaged, passionate, intimate, or intensely focused.  
  Output ONLY a single integer between 1 and 100\. Do not include any explanations, markdown, or text."

### **4\. Background Worker Service (src/engagement/worker.py)**

Create the core logic that handles the LLM call and webhook dispatch.

* **Dependencies:** httpx for async HTTP requests, the InferenceRuntimeFactory or equivalent for LLM calls, and the database repository to fetch chat history.  
* **Function:** async def calculate\_and\_dispatch\_score(conversation\_id: str, user\_id: str, companion\_id: str):  
  1. **Fetch History:** Retrieve the last ENGAGEMENT\_HISTORY\_LIMIT messages for the given conversation\_id from the database.  
  2. **Format Input:** Format the history into the structure expected by the LLM, prepending the ENGAGEMENT\_SCORING\_PROMPT.  
  3. **LLM Call:** Execute the LLM call. It is highly recommended to set max\_tokens=3 and a low temperature (e.g., 0.1) to ensure deterministic, numeric output.  
  4. **Parse Output:** Strip whitespace and attempt to cast the LLM's response to an integer. If parsing fails, log a warning and abort.  
  5. **Compare State:** Retrieve the last known score from the in-memory state.  
  6. **Dispatch (if changed):** If new\_score \!= last\_known\_score:  
     * Update the in-memory state with the new score.  
     * Construct the payload: {"user\_id": user\_id, "ai\_companion\_id": companion\_id, "engagement\_score": new\_score}.  
     * Use an async HTTP client (e.g., httpx.AsyncClient) to POST the payload to EXTERNAL\_BACKEND\_WEBHOOK\_URL.  
     * Wrap the HTTP call in a try...except block to catch network errors (httpx.RequestError). Log failures but do not raise exceptions that would crash the task.

### **5\. Integration into the Chat Loop (src/backend/websocket\_handler.py or src/backend/service.py)**

Trigger the background task seamlessly after a conversation turn.

* **Location:** Inside the main chat processing logic, immediately after the AI's response has been generated, streamed to the user, and saved to the database.  
* **Mechanism:** Use FastAPI's BackgroundTasks (if within an HTTP endpoint) or asyncio.create\_task() (if deep within a continuous WebSocket loop) to schedule calculate\_and\_dispatch\_score without blocking the main chat flow.

### **6\. Dependencies**

Ensure the necessary HTTP library is present.

* **Check:** Verify httpx is in pyproject.toml or requirements.txt. If not, it must be added.

## **Expected Behavior & Edge Cases for AI Coder**

1. **Non-Integer Output:** If the LLM returns "The score is 85", the parsing step *must* handle this gracefully (either via regex extraction or by failing safely and logging the error). The task must not crash.  
2. **Server Restart:** On a server restart, the in-memory dictionary is wiped. The first calculation for an active conversation will be treated as a "change" (since the previous state is None), and a webhook will be fired. This is expected and desired behavior.  
3. **Webhook Timeout:** Configure a short timeout (e.g., 5 seconds) on the httpx POST request to prevent hanging tasks if the external backend is slow or unresponsive.  
4. **Fire-and-Forget:** Do not implement retry mechanisms for the HTTP request. If it fails, it drops.

