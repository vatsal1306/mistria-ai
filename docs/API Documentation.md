# Mistria AI — API Integration Guide

> **Version:** 3.1  
> **Last Updated:** 2026-06-18  
> **Milestone:** M3  
> **Audience:** Frontend / Web App Engineers  
> **ServerLink:** http://45.248.33.161:8080/docs

---

## Table of Contents

1. [Overview](#overview)
2. [Base URLs](#base-urls)
3. [Authentication](#authentication)
4. [HTTP Endpoints](#http-endpoints)
   - [GET /info](#get-info)
   - [GET /health](#get-health)
   - [POST /users](#post-users)
   - [POST /ai-companion](#post-ai-companion)
   - [POST /ai-companion/generate](#post-ai-companiongenerate)
   - [GET /ai-companion](#get-ai-companion)
   - [GET /ai-companion/{ai_companion_id}](#get-ai-companionai_companion_id)
   - [POST /archetype/slow-burn/score](#post-archetypeslow-burnscore)
   - [GET /archetype/latest/{user_mail_id}](#get-archetypelatestuser_mail_id)
   - [POST /debug/memory/retrieve](#post-debugmemoryretrieve) [Internal]
5. [WebSocket Endpoint](#websocket-endpoint)
   - [Connection](#connection)
   - [Request Payload](#request-payload)
   - [Response Event Types](#response-event-types)
   - [End-to-End Flow](#end-to-end-flow)
   - [Error Scenarios](#error-scenarios)
   - [Engagement Scoring (Background)](#engagement-scoring-background)
6. [Engagement Scoring Webhook (Outbound)](#engagement-scoring-webhook-outbound)
7. [Allowed Values Reference](#allowed-values-reference)
8. [Error Handling Summary](#error-handling-summary)
9. [Notes for Frontend Integration](#notes-for-frontend-integration)

---

## Overview

Mistria AI exposes a FastAPI backend with:

- HTTP endpoints for user management, AI persona generation, archetype scoring, and memory debugging.
- **1 WebSocket endpoint** for real-time streamed chat with long-term memory retrieval.
- **Background engagement scoring** that evaluates recent chat history after each completed turn and notifies an external backend via webhook when the score changes.

All HTTP endpoints accept and return `application/json`. The WebSocket endpoint exchanges JSON text frames.

> **Engagement scoring is server-side only.** The frontend does not call it directly. When enabled, Mistria AI POSTs score updates to your Node.js (or other) backend after successful chat turns. See [Engagement Scoring Webhook (Outbound)](#engagement-scoring-webhook-outbound).

> **Interactive Docs:** FastAPI auto-generates interactive API documentation. Once the server is running, visit:
> - **Swagger UI:** `http://127.0.0.1:8080/docs` — try every endpoint directly in your browser
> - **ReDoc:** `http://127.0.0.1:8080/redoc` — clean read-only API reference

---

## Base URLs

| Environment | HTTP Base URL | WebSocket URL |
|---|---|---|
| Local Development | `http://127.0.0.1:8080` | `ws://127.0.0.1:8080/ws/chat` |
| Docker Compose | `http://127.0.0.1:8080` | `ws://127.0.0.1:8080/ws/chat` |
| Server Deployment | `http://<server-ip>:8080` | `ws://<server-ip>:8080/ws/chat` |

---

## Authentication

API key authentication is **disabled by default** (`MISTRIA_API_REQUIRE_API_KEY=false`).

When enabled:

- **HTTP endpoints**: No API key required (open).
- **WebSocket endpoint**: Pass the key as a query parameter:
  ```
  ws://127.0.0.1:8080/ws/chat?api_key=<your-api-key>
  ```

If the key is missing or invalid, the server sends an `error` event and closes the connection with code `1008` (Policy Violation).

---

## HTTP Endpoints

### GET /info

Returns a minimal description of the running API surface.

**Request:**
```
GET /info
```

**Response:** `200 OK`
```json
{
  "app": "Mistria AI",
  "backend": "mock",
  "websocket": "/ws/chat",
  "health": "/health"
}
```

---

### GET /health

Exposes runtime readiness and startup diagnostics. Use this for health checks and monitoring.

**Request:**
```
GET /health
```

**Response:** `200 OK` (engine ready)
```json
{
  "status": "ok",
  "app": "Mistria AI",
  "backend": "mock",
  "model_name": "dphn/Dolphin3.0-Llama3.1-8B",
  "engine_ready": true,
  "websocket_path": "/ws/chat",
  "startup_stage": "ready",
  "startup_detail": "Mock runtime is ready.",
  "startup_elapsed_seconds": 0.01,
  "startup_error": null
}
```

**Response:** `200 OK` (engine degraded / starting up)
```json
{
  "status": "degraded",
  "app": "Mistria AI",
  "backend": "vllm",
  "model_name": "dphn/Dolphin3.0-Llama3.1-8B",
  "engine_ready": false,
  "websocket_path": "/ws/chat",
  "startup_stage": "loading_model",
  "startup_detail": "Loading model weights into GPU memory.",
  "startup_elapsed_seconds": 42.5,
  "startup_error": null
}
```

| Field | Type | Description |
|---|---|---|
| `status` | `"ok"` \| `"degraded"` | `"ok"` when engine is ready, `"degraded"` otherwise |
| `engine_ready` | `boolean` | `true` when the inference backend can accept chat requests |
| `startup_stage` | `string` | Current lifecycle stage (e.g., `"initializing"`, `"loading_model"`, `"ready"`, `"failed"`) |
| `startup_detail` | `string \| null` | Human-readable description of the current stage |
| `startup_elapsed_seconds` | `float \| null` | Seconds elapsed since startup began |
| `startup_error` | `string \| null` | Error message if startup failed |

---

### POST /users

Create a new user identity. The frontend manages authentication; this endpoint only registers the user in the backend database.

**Request:**
```
POST /users
Content-Type: application/json

{
  "email": "user@example.com",
  "name": "Alex"
}
```

| Field | Type | Constraints | Required |
|---|---|---|---|
| `email` | `string` | 3–320 characters | ✅ |
| `name` | `string` | 1–255 characters | ✅ |

**Response:** `201 Created`
```json
{
  "user_id": 1,
  "email": "user@example.com",
  "name": "Alex",
  "created_at": "2026-04-18 10:30:00"
}
```

**Error:** `409 Conflict` — Email already registered
```json
{
  "detail": "An account with this email already exists."
}
```

> **Note:** Email is normalized to lowercase and trimmed before storage. Lookups are case-insensitive.

---

### Archetype Onboarding (Slow Burn vs Intense Heat)

The platform supports two distinct onboarding paths:
1. **Intense Heat**: The user skips archetype testing. They do **not** require an archetype result. The frontend proceeds directly to `POST /ai-companion`.
2. **Slow Burn**: The frontend asks a series of archetype questions, converts the selections into trait scores, and submits them to `POST /archetype/slow-burn/score`. The backend calculates and stores the archetype. **Afterward**, the user creates an AI companion persona exactly like the Intense Heat flow. Archetype scoring is additive and does not replace the AI companion persona.

> **Note**: The backend stores every completed Slow Burn submission, but the chat runtime always uses the **latest** stored result.

---

### POST /archetype/slow-burn/score

Submit a completed Slow Burn trait vector to calculate and store the user's archetype result.

**Request:**
```
POST /archetype/slow-burn/score
Content-Type: application/json

{
  "user_mail_id": "user@example.com",
  "trait_scores": {
    "power": 4,
    "pace": 2,
    "intensity": 5,
    "depth": 3,
    "soft": 1,
    "freedom": 5,
    "sharp": 4
  }
}
```

| Field | Type | Constraints | Required |
|---|---|---|---|
| `user_mail_id` | `string` | Valid email, 3–320 chars | ✅ |
| `trait_scores` | `object` | Contains exactly 7 predefined keys with float/int values | ✅ |

**Required trait keys**: `power`, `pace`, `intensity`, `depth`, `soft`, `freedom`, `sharp`

**Response:** `200 OK`
```json
{
  "primary_archetype": "rebel",
  "primary_similarity": 0.89,
  "secondary_archetype": null,
  "secondary_similarity": null,
  "blend_active": false,
  "trait_scores": {
    "power": 4,
    "pace": 2,
    "intensity": 5,
    "depth": 3,
    "soft": 1,
    "freedom": 5,
    "sharp": 4
  },
  "created_at": "2026-04-18 10:35:00"
}
```

**Errors:**
- `404 Not Found` — User not registered
- `422 Unprocessable Entity` — Invalid trait vector (missing keys, extra keys, or non-numeric values)

---

### GET /archetype/latest/{user_mail_id}

Retrieve the user's most recent Slow Burn archetype result.

**Request:**
```
GET /archetype/latest/user@example.com
```

**Response:** `200 OK`
```json
{
  "primary_archetype": "rebel",
  "primary_similarity": 0.89,
  "secondary_archetype": null,
  "secondary_similarity": null,
  "blend_active": false,
  "trait_scores": {
    "power": 4,
    "pace": 2,
    "intensity": 5,
    "depth": 3,
    "soft": 1,
    "freedom": 5,
    "sharp": 4
  },
  "created_at": "2026-04-18 10:35:00"
}
```

**Errors:**
- `404 Not Found` — User not registered
- `404 Not Found` — No archetype result exists for this user

---

### POST /ai-companion

Create a new AI companion persona for a registered user.

- If both `title` and `description` are provided, the API saves the companion exactly as provided and does not call AI generation.
- If `description` is omitted, the API generates the description from the companion attributes. If `title` is also omitted, it generates both title and description.

**Request:**
```
POST /ai-companion
Content-Type: application/json

{
  "user_mail_id": "user@example.com",
  "title": "Luna",
  "description": "A dominant Latina writer with a realistic presence and controlled, magnetic energy.",
  "gender": "Female",
  "visual_style": "Realistic",
  "companion_ethnicity": "Latina",
  "eye_color": "Gray",
  "age": 28,
  "hair_length": "Extra Long",
  "hair_style": "Pixie",
  "hair_color": "Blonde",
  "companion_personality": "Dominant",
  "companion_profession": "Writer",
  "body_type": "Natural",
  "bust": "Natural",
  "height": "Average",
  "intention": "quick"
}
```

| Field | Type | Allowed Values | Required |
|---|---|---|---|
| `user_mail_id` | `string` | Valid email, 3–320 chars | ✅ |
| `title` | `string \| null` | 1–120 chars (auto-generated if omitted) | ❌ |
| `description` | `string \| null` | Free text; if provided with `title`, AI generation is skipped | ❌ |
| `gender` | `string` | `"Female"`, `"Male"`, `"Other"` | ✅ |
| `visual_style` | `string` | Free text | ✅ |
| `companion_ethnicity` | `string` | See [Allowed Values](#allowed-values-reference) | ✅ |
| `eye_color` | `string` | Free text | ✅ |
| `age` | `integer` | 18–120 | ✅ |
| `hair_length` | `string` | Free text | ✅ |
| `hair_style` | `string` | Free text | ✅ |
| `hair_color` | `string` | Free text | ✅ |
| `companion_personality` | `string` | See [Allowed Values](#allowed-values-reference) | ✅ |
| `companion_profession` | `string` | Free text | ✅ |
| `body_type` | `string` | Free text | ✅ |
| `bust` | `string` | `"Small"`, `"Natural"`, `"Large"`, `"Extra Large"` | ✅ |
| `height` | `string` | `"Short"`, `"Average"`, `"Tall"`, `"Very Tall"` | ✅ |
| `intention` | `string` | Free text | ✅ |

> **Admin flow note:** This endpoint supports both manual creation and AI-assisted creation. For manual assignment from the admin UI, send both `title` and `description`. For AI-assisted creation, omit `description` and optionally omit `title`.

**Response:** `201 Created`
```json
{
  "ai_companion_id": 1,
  "title": "Luna",
  "description": "A dominant Latina writer with a realistic presence and controlled, magnetic energy."
}
```

**Error:** `404 Not Found` — User not registered
```json
{
  "detail": "User not registered."
}
```

---

### POST /ai-companion/generate

Generate AI companion metadata directly from the LLM without requiring a registered user and without saving anything to the database.

**Request:**
```
POST /ai-companion/generate
Content-Type: application/json

{
  "gender": "Female",
  "visual_style": "Realistic",
  "companion_ethnicity": "Latina",
  "eye_color": "Gray",
  "age": 28,
  "hair_length": "Extra Long",
  "hair_style": "Pixie",
  "hair_color": "Blonde",
  "companion_personality": "Dominant",
  "companion_profession": "Writer",
  "body_type": "Natural",
  "bust": "Natural",
  "height": "Average",
  "intention": "quick"
}
```

| Field | Type | Allowed Values | Required |
|---|---|---|---|
| `gender` | `string` | `"Female"`, `"Male"`, `"Other"` | ✅ |
| `visual_style` | `string` | Free text | ✅ |
| `companion_ethnicity` | `string` | See [Allowed Values](#allowed-values-reference) | ✅ |
| `eye_color` | `string` | Free text | ✅ |
| `age` | `integer` | 18–120 | ✅ |
| `hair_length` | `string` | Free text | ✅ |
| `hair_style` | `string` | Free text | ✅ |
| `hair_color` | `string` | Free text | ✅ |
| `companion_personality` | `string` | See [Allowed Values](#allowed-values-reference) | ✅ |
| `companion_profession` | `string` | Free text | ✅ |
| `body_type` | `string` | Free text | ✅ |
| `bust` | `string` | `"Small"`, `"Natural"`, `"Large"`, `"Extra Large"` | ✅ |
| `height` | `string` | `"Short"`, `"Average"`, `"Tall"`, `"Very Tall"` | ✅ |
| `intention` | `string` | Free text | ✅ |

> **Note:** This endpoint does not require `user_mail_id`, does not create an `ai_companion_id`, and does not persist any data.

**Response:** `200 OK`
```json
{
  "title": "Luna",
  "description": "A dominant Latina writer with a realistic presence and controlled, magnetic energy."
}
```

**Error:** `422 Unprocessable Entity` — Payload validation failed

---

### GET /ai-companion

List all AI companion personas created by a user.

**Request:**
```
GET /ai-companion?user_mail_id=user@example.com
```

| Query Param | Type | Constraints | Required |
|---|---|---|---|
| `user_mail_id` | `string` | 3–320 characters | ✅ |

**Response:** `200 OK`
```json
[
  {
    "id": 1,
    "user_mail_id": "user@example.com",
    "title": "Luna",
    "description": "A dominant Latina writer with a realistic presence and controlled, magnetic energy.",
    "gender": "Female",
    "visual_style": "Realistic",
    "companion_ethnicity": "Latina",
    "eye_color": "Gray",
    "age": 28,
    "hair_length": "Extra Long",
    "hair_style": "Pixie",
    "hair_color": "Blonde",
    "companion_personality": "Dominant",
    "companion_profession": "Writer",
    "body_type": "Natural",
    "bust": "Natural",
    "height": "Average",
    "intention": "quick"
  }
]
```

Returns an empty array `[]` if the user has no companions.

**Error:** `404 Not Found` — User not registered

---

### GET /ai-companion/{ai_companion_id}

Fetch a single AI companion persona by its ID.

**Request:**
```
GET /ai-companion/1
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "user_mail_id": "user@example.com",
  "title": "Luna",
  "description": "A dominant Latina writer with a realistic presence and controlled, magnetic energy.",
  "gender": "Female",
  "visual_style": "Realistic",
  "companion_ethnicity": "Latina",
  "eye_color": "Gray",
  "age": 28,
  "hair_length": "Extra Long",
  "hair_style": "Pixie",
  "hair_color": "Blonde",
  "companion_personality": "Dominant",
  "companion_profession": "Writer",
  "body_type": "Natural",
  "bust": "Natural",
  "height": "Average",
  "intention": "quick"
}
```

**Error:** `404 Not Found` — Companion not found
```json
{
  "detail": "AI companion not found."
}
```

---

### POST /debug/memory/retrieve

**[INTERNAL / DEVELOPMENT ONLY]**  
Directly query the long-term memory system to see what results would be injected into the prompt for a given user message.

**Enablement Requirements:**
- `MISTRIA_MEMORY_ENABLED=True`
- `MISTRIA_MEMORY_DEBUG_ENDPOINT_ENABLED=True`

If either flag is disabled, the endpoint returns `404 Not Found`. This endpoint should remain disabled in production environments.

**Request:**
```
POST /debug/memory/retrieve
Content-Type: application/json

{
  "user_mail_id": "user@example.com",
  "ai_companion_id": 1,
  "user_message": "What did I say about my favorite coffee?"
}
```

| Field | Type | Description | Required |
|---|---|---|---|
| `user_mail_id` | `string` | User email address | ✅ |
| `ai_companion_id` | `integer` | Companion persona ID | ✅ |
| `user_message` | `string` | The query to search memory with | ✅ |

**Response:** `200 OK`
```json
{
  "user_mail_id": "user@example.com",
  "ai_companion_id": 1,
  "memories": [
    {
      "memory_id": 105,
      "memory_type": "preference",
      "content": "User prefers black coffee over latte.",
      "canonical_key": "coffee_pref",
      "score": 0.89,
      "importance": 4,
      "source": "hybrid"
    }
  ]
}
```

---

## WebSocket Endpoint

### Connection

```
ws://127.0.0.1:8080/ws/chat
```

If API key authentication is enabled:
```
ws://127.0.0.1:8080/ws/chat?api_key=<your-api-key>
```

The connection is **long-lived**. After connecting, the server sends a `ready` event. The client can then send multiple chat requests on the same connection.

### Request Payload

Send a JSON text frame with the following structure:

```json
{
  "action": "chat",
  "user_id": "user@example.com",
  "ai_companion_id": 1,
  "user_message": "Tell me something interesting."
}
```

| Field | Type | Description | Required |
|---|---|---|---|
| `action` | `string` | Always `"chat"` | ✅ |
| `user_id` | `string` | User email address registered in the database | ✅ |
| `ai_companion_id` | `integer` | ID of the destination AI companion persona | ✅ |
| `system_prompt` | `string \| null` | Override the default system prompt | ❌ |
| `user_message` | `string` | The latest chat input from the user (min 1 char) | ✅ |

**Validation Rules:**
- The backend strictly validates identity: the user and AI companion must exist in the database, and the AI companion must be owned by that user.
- **Short-Term History**: The server automatically fetches recent conversation history from the database and trims it to the last 24 messages.
- **Long-Term Memory (LTM)**: If enabled, the server retrieves relevant facts, preferences, and emotional context from the vector store (Qdrant) before starting inference, using a hybrid search of the latest `user_message`.
- **Injection**: Both short-term history and long-term memories are injected into the system prompt before inference. This happens entirely server-side; the frontend does not need to manage or send the memory context.
- **Engagement Scoring**: After a successful turn (user message saved, assistant response streamed and saved), the server may asynchronously evaluate engagement and POST a webhook to an external backend if the score changed. This does not affect WebSocket events and requires no frontend action. See [Engagement Scoring (Background)](#engagement-scoring-background).
- Unknown fields are rejected (`extra: "forbid"`).

### Response Event Types

The server sends JSON text frames. Every event contains a `type` and `backend` field.

#### `ready`

Sent once immediately after successful connection.

```json
{
  "type": "ready",
  "backend": "mock",
  "delta": null,
  "detail": null
}
```

#### `delta`

Sent for each token/chunk of the AI's response. These arrive in rapid succession to enable real-time streaming.

```json
{
  "type": "delta",
  "backend": "mock",
  "delta": "Hello",
  "detail": null
}
```

```json
{
  "type": "delta",
  "backend": "mock",
  "delta": " there",
  "detail": null
}
```

**Frontend implementation:** Append each `delta` value to the assistant message being rendered.

#### `done`

Sent once after all `delta` events for a single response. The response is now complete.

```json
{
  "type": "done",
  "backend": "mock",
  "delta": null,
  "detail": null
}
```

**Frontend implementation:** Finalize the assistant message. The client can now send another chat request.

#### `error`

Sent when something goes wrong. The connection may or may not remain open depending on the error type.

```json
{
  "type": "error",
  "backend": "mock",
  "delta": null,
  "detail": "The last message in the request must be from the user."
}
```

| Error Scenario | `detail` Value | Connection |
|---|---|---|
| Invalid JSON payload | Pydantic validation error details | Stays open |
| Last message not from user | `"The last message in the request must be from the user."` | Stays open |
| Inference engine not ready | `"Inference runtime is not ready."` | Stays open |
| Token generation failure | `"<ErrorType>: <message>"` | Stays open |
| Invalid/missing API key | `"Missing or invalid websocket API key."` | **Closed (1008)** |
| Unhandled server error | `"Unhandled server error: <ErrorType>"` | Stays open |

### End-to-End Flow

Here is a complete example of a successful WebSocket chat session:

```
1. Client connects:     ws://127.0.0.1:8080/ws/chat

2. Server sends:        {"type":"ready","backend":"mock","delta":null,"detail":null}

3. Client sends:        {
                           "action": "chat",
                           "user_id": "user@example.com",
                           "ai_companion_id": 1,
                           "user_message": "Hey, what's your name?"
                         }

4. Server sends:        {"type":"delta","backend":"mock","delta":"Hey","detail":null}
5. Server sends:        {"type":"delta","backend":"mock","delta":" there","detail":null}
6. Server sends:        {"type":"delta","backend":"mock","delta":"!","detail":null}
7. Server sends:        {"type":"delta","backend":"mock","delta":" I'm","detail":null}
8. Server sends:        {"type":"delta","backend":"mock","delta":" Aria","detail":null}
9. Server sends:        {"type":"delta","backend":"mock","delta":".","detail":null}

10. Server sends:       {"type":"done","backend":"mock","delta":null,"detail":null}

11. [Background] If engagement scoring is enabled, Mistria AI evaluates recent chat history
    and may POST an engagement webhook to the external backend (see below).

12. Client can now send another chat request on the same connection.
```

### Error Scenarios

**Scenario 1: Invalid payload (validation error)**
```
Client sends:           {"action": "chat", "user_id": "", "ai_companion_id": 1, "user_message": ""}

Server responds:        {
                          "type": "error",
                          "backend": "mock",
                          "delta": null,
                          "detail": "[{\"type\":\"string_too_short\", ...}]"
                        }

Connection:             Remains open. Client can retry.
```

**Scenario 2: Authentication failure (when API key is required)**
```
Client connects:        ws://127.0.0.1:8080/ws/chat?api_key=wrong-key

Server responds:        {
                          "type": "error",
                          "backend": "mock",
                          "delta": null,
                          "detail": "Missing or invalid websocket API key."
                        }

Connection:             Closed by server with code 1008.
```

**Scenario 3: Engine not ready**
```
Client sends:           {"action":"chat","user_id":"u1","ai_companion_id":1,"user_message":"hi"}

Server responds:        {
                          "type": "error",
                          "backend": "vllm",
                          "delta": null,
                          "detail": "Inference runtime is not ready."
                        }

Connection:             Remains open. Client should retry after checking /health.
```

### Engagement Scoring (Background)

After each **successful** WebSocket chat turn, Mistria AI may run engagement scoring in the background. This happens **after** the `done` event is sent and does not block or modify the WebSocket stream.

| Aspect | Behavior |
|---|---|
| Trigger | User message + assistant response both saved to the database |
| Blocking | Non-blocking; runs as a background task |
| Frontend impact | None — no new WebSocket events are emitted |
| Enablement | Requires `EXTERNAL_BACKEND_WEBHOOK_URL` to be set on the Mistria AI server |

**Scoring logic by inference backend:**

| `MISTRIA_INFERENCE_BACKEND` | Engagement score source |
|---|---|
| `vllm` or `ollama` | LLM evaluates the last `ENGAGEMENT_HISTORY_LIMIT` messages and returns an integer 1–100 |
| `mock` | Random integer between 1 and 100 (for local/smoke testing; LLM is not called) |

The score reflects user engagement, interest, conversational flow, and intimacy/intensity based on recent messages. In production, use `vllm` or `ollama`. Use `mock` only when you want to exercise the webhook pipeline without a real model.

---

## Engagement Scoring Webhook (Outbound)

> **Audience:** Node.js / platform backend engineers integrating with Mistria AI  
> **Direction:** Mistria AI → your backend (outbound HTTP POST)

Engagement scoring is **not** an HTTP endpoint exposed by Mistria AI. Instead, Mistria AI sends an asynchronous webhook to your backend whenever a conversation's engagement score **changes**.

### Enablement

Set these environment variables on the Mistria AI server:

| Variable | Default | Description |
|---|---|---|
| `EXTERNAL_BACKEND_WEBHOOK_URL` | *(unset — disabled)* | Full URL to POST engagement updates to. Feature is disabled when empty. |
| `ENGAGEMENT_HISTORY_LIMIT` | `10` | Number of most recent messages used as scoring context |

Example:

```bash
EXTERNAL_BACKEND_WEBHOOK_URL=https://your-node-backend.example.com/api/engagement
ENGAGEMENT_HISTORY_LIMIT=10
```

### When the webhook fires

1. A WebSocket chat turn completes successfully (assistant response saved).
2. Mistria AI fetches the last `ENGAGEMENT_HISTORY_LIMIT` messages for that conversation.
3. A score (1–100) is calculated.
4. The score is compared to the last known score for that conversation (held in memory).
5. If the score **changed** (even by 1 point), a webhook POST is sent.
6. If the score is unchanged, no webhook is sent.

**Edge cases:**

| Scenario | Behavior |
|---|---|
| Server restart | In-memory scores are cleared. The next calculation is treated as a change and triggers a webhook. |
| Invalid LLM output (`vllm`/`ollama`) | Scoring is skipped; no webhook. Logged server-side. |
| Webhook failure | Logged server-side; no retries (fire-and-forget). Chat is unaffected. |
| Empty conversation history | Scoring is skipped. |

### Webhook request

Mistria AI sends:

```
POST <EXTERNAL_BACKEND_WEBHOOK_URL>
Content-Type: application/json
```

**Payload:**

```json
{
  "user_id": "user@example.com",
  "ai_companion_id": 1,
  "engagement_score": 82
}
```

| Field | Type | Description |
|---|---|---|
| `user_id` | `string` | User email address (same value as `user_id` in the WebSocket chat payload) |
| `ai_companion_id` | `integer` | AI companion persona ID |
| `engagement_score` | `integer` | Engagement score from 1 (disengaged) to 100 (highly engaged) |

**Expected backend response:** Return any `2xx` status code. Mistria AI uses a **10 second** timeout and does **not** retry failed requests.

### Mock backend testing notes

When `MISTRIA_INFERENCE_BACKEND=mock`:

- Each scoring run produces a **random** score between 1 and 100.
- Because scores usually differ turn-to-turn, webhooks fire frequently — useful for testing your receiver.
- Chat WebSocket behavior is unchanged; only the engagement score source differs.

Example local setup:

```bash
MISTRIA_INFERENCE_BACKEND=mock
EXTERNAL_BACKEND_WEBHOOK_URL=http://127.0.0.1:3000/api/engagement
```

### Integration checklist (external backend)

1. Expose a `POST` endpoint at the URL configured in `EXTERNAL_BACKEND_WEBHOOK_URL`.
2. Accept JSON with `user_id`, `ai_companion_id`, and `engagement_score`.
3. Respond with `2xx` quickly (within 10 seconds).
4. Treat delivery as at-most-once; duplicate or missed events are possible after restarts or network failures.
5. Do not expect the frontend to relay engagement data — Mistria AI sends it directly.

---

## Allowed Values Reference

### AI Companion Persona

| Field | Allowed Values |
|---|---|
| `gender` | `"Female"`, `"Male"`, `"Other"` |
| `companion_ethnicity` | `"African Descent"`, `"South Asian"`, `"Eastern European"`, `"East Asian"`, `"Latinx"`, `"Latina"`, `"Middle Eastern"` |
| `companion_personality` | `"Flirty"`, `"Obsessed"`, `"Playful"`, `"Dominant"`, `"Mysterious"`, `"Caring"`, `"Confident"`, `"Sensual"`, `"Passionate"` |
| `bust` | `"Small"`, `"Natural"`, `"Large"`, `"Extra Large"` |
| `height` | `"Short"`, `"Average"`, `"Tall"`, `"Very Tall"` |

---

## Error Handling Summary

| HTTP Status | When | Example |
|---|---|---|
| `200 OK` | Successful read or update | GET/POST responses |
| `201 Created` | Successful resource creation | POST /users, POST /ai-companion |
| `404 Not Found` | User or companion not found | Invalid email or companion ID |
| `409 Conflict` | Duplicate resource | Email already registered |
| `422 Unprocessable Entity` | Payload validation failure | FastAPI automatic validation |
| `500 Internal Server Error` | Backend configuration error | Unsupported inference backend |

All error responses follow the format:
```json
{
  "detail": "<human-readable error message>"
}
```

For `422` validation errors, FastAPI returns:
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "String should have at least 3 characters",
      "type": "string_too_short"
    }
  ]
}
```

---

## Notes for Frontend Integration

1. **User Registration First:** A user must be created via `POST /users` before calling any companion or chat endpoint. The `user_mail_id` / `user_id` field across all endpoints refers to the registered email.

2. **Onboarding Flow:**
   - **Intense Heat:**
     ```
     POST /users  →  POST /ai-companion  →  WebSocket /ws/chat
     ```
   - **Slow Burn:**
     ```
     POST /users  →  POST /archetype/slow-burn/score  →  POST /ai-companion  →  WebSocket /ws/chat
     ```

3. **Preview Generation Flow:** If the frontend only needs a generated title and description before account creation or before saving, call:
   ```
   POST /ai-companion/generate
   ```

4. **Admin Manual Create Flow:** If an admin already has the final companion content and only wants to assign it to a registered user, call `POST /ai-companion` with `user_mail_id`, all required companion attributes, and both `title` and `description`. In that case the backend stores the provided values directly and skips AI generation.

5. **WebSocket Lifecycle:**
   - Open one connection per chat session.
   - Wait for the `ready` event before sending the first message.
   - Concatenate all `delta` values to build the assistant's response.
   - Wait for `done` before sending the next user message.
   - On `error`, display the `detail` to the user and allow retry.

6. **Conversation History & Memory:** The backend automatically manages both short-term history and long-term memory (LTM).
   - **Short-Term**: The last 24 messages are retrieved from SQLite.
   - **Long-Term**: Relevant facts and preferences are retrieved from the vector store based on semantic similarity to the `user_message`.
   - **Frontend Payload**: The client only needs to send the latest `user_message`. LTM is transparent to the frontend and does not require any additional UI logic.

7. **Engagement Scoring:** The frontend does **not** implement engagement scoring. After each successful chat turn, Mistria AI may POST score updates to an external backend configured via `EXTERNAL_BACKEND_WEBHOOK_URL`. If your product displays engagement scores, read them from your own backend — not from the Mistria AI WebSocket. See [Engagement Scoring Webhook (Outbound)](#engagement-scoring-webhook-outbound).

8. **AI Companion Field Names:** AI companion feature fields use snake_case.

9. **Email Normalization:** Emails are automatically lowercased and trimmed. `"User@Example.COM"` becomes `"user@example.com"`.

10. **Retry Strategy:** If `/health` shows `engine_ready: false`, poll every 5–10 seconds until `engine_ready: true` before attempting WebSocket chat.

11. **CORS:** The backend currently allows requests from `http://127.0.0.1:8501` and `http://localhost:8501` only. If your frontend runs on a different origin (e.g., `http://localhost:3000`), the `MISTRIA_API_CORS_ORIGINS` environment variable must be updated on the backend or you will receive CORS errors.
