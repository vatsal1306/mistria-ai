# Mistria AI — API Integration Guide

> **Version:** 2.0  
> **Last Updated:** 2026-04-22  
> **Milestone:** M2  
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
   - [POST /user-companion](#post-user-companion)
   - [GET /user-companion/{user_mail_id}](#get-user-companionuser_mail_id)
   - [POST /ai-companion](#post-ai-companion)
   - [GET /ai-companion](#get-ai-companion)
   - [GET /ai-companion/{ai_companion_id}](#get-ai-companionai_companion_id)
5. [WebSocket Endpoint](#websocket-endpoint)
   - [Connection](#connection)
   - [Request Payload](#request-payload)
   - [Response Event Types](#response-event-types)
   - [End-to-End Flow](#end-to-end-flow)
   - [Error Scenarios](#error-scenarios)
6. [Allowed Values Reference](#allowed-values-reference)
7. [Error Handling Summary](#error-handling-summary)
8. [Notes for Frontend Integration](#notes-for-frontend-integration)

---

## Overview

Mistria AI exposes a FastAPI backend with:

- **8 HTTP endpoints** for user management, companion preferences, and AI persona CRUD.
- **1 WebSocket endpoint** for real-time streamed chat with the AI companion.

All HTTP endpoints accept and return `application/json`. The WebSocket endpoint exchanges JSON text frames.

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

### POST /user-companion

Create or replace the saved user-level companion preferences. If preferences already exist for the user, they are overwritten (upsert behavior).

**Request:**
```
POST /user-companion
Content-Type: application/json

{
  "user_mail_id": "user@example.com",
  "intent_type": "alive",
  "dominance_mode": "ai_leads",
  "intensity_level": "break_glass",
  "silence_response": "come_looking",
  "secret_desire": "both"
}
```

| Field | Type | Allowed Values | Required |
|---|---|---|---|
| `user_mail_id` | `string` | Valid email, 3–320 chars | ✅ |
| `intent_type` | `string` | `"easy"`, `"alive"`, `"lose_myself"` | ✅ |
| `dominance_mode` | `string` | `"user_leads"`, `"ai_leads"`, `"no_rules"` | ✅ |
| `intensity_level` | `string` | `"show_me"`, `"break_glass"`, `"burn_it"` | ✅ |
| `silence_response` | `string` | `"wait"`, `"come_looking"`, `"never_leave"` | ✅ |
| `secret_desire` | `string` | `"running"`, `"searching"`, `"both"` | ✅ |

**Response:** `200 OK`
```json
{
  "user_mail_id": "user@example.com",
  "title": "Chased and Unapologetic",
  "description": "A high-intensity personality that wants pursuit, danger, and emotional surrender."
}
```

**Error:** `404 Not Found` — User email not registered
```json
{
  "detail": "User not registered."
}
```

---

### GET /user-companion/{user_mail_id}

Fetch the saved companion preferences for a user.

**Request:**
```
GET /user-companion/user@example.com
```

**Response:** `200 OK`
```json
{
  "user_mail_id": "user@example.com",
  "intent_type": "alive",
  "dominance_mode": "ai_leads",
  "intensity_level": "break_glass",
  "silence_response": "come_looking",
  "secret_desire": "both",
  "title": "Chased and Unapologetic",
  "description": "A high-intensity personality that wants pursuit, danger, and emotional surrender."
}
```

**Errors:**
- `404 Not Found` — User not registered: `{"detail": "User not registered."}`
- `404 Not Found` — Preferences not set: `{"detail": "User companion preferences not found."}`

---

### POST /ai-companion

Create a new AI companion persona for a registered user.

**Request:**
```
POST /ai-companion
Content-Type: application/json

{
  "user_mail_id": "user@example.com",
  "title": "Luna",
  "gender": "Female",
  "style": "Anime",
  "ethnicity": "East Asian",
  "eyeColor": "Green",
  "hairStyle": "Long",
  "hairColor": "Pink",
  "personality": "Playful",
  "voice": "Breathy",
  "connection": "Passionate Lover"
}
```

| Field | Type | Allowed Values | Required |
|---|---|---|---|
| `user_mail_id` | `string` | Valid email, 3–320 chars | ✅ |
| `title` | `string \| null` | 1–120 chars (auto-generated if omitted) | ❌ |
| `gender` | `string` | `"Female"`, `"Male"`, `"Other"` | ✅ |
| `style` | `string` | `"Realistic"`, `"Anime"`, `"Cartoon"`, `"Retro Noir"` | ✅ |
| `ethnicity` | `string` | See [Allowed Values](#allowed-values-reference) | ✅ |
| `eyeColor` | `string` | `"Brown"`, `"Blue"`, `"Green"`, `"Hazel"`, `"Gray"`, `"Black"` | ✅ |
| `hairStyle` | `string` | `"Short"`, `"Straight"`, `"Long"`, `"Curly"`, `"Braids"`, `"Pixie"` | ✅ |
| `hairColor` | `string` | `"Black"`, `"Brunette"`, `"Blonde"`, `"Pink"`, `"Red"`, `"White"` | ✅ |
| `personality` | `string` | See [Allowed Values](#allowed-values-reference) | ✅ |
| `voice` | `string` | `"Calm"`, `"Breathy"`, `"Confident"`, `"Playful"`, `"Deep"`, `"Soft"` | ✅ |
| `connection` | `string` | See [Allowed Values](#allowed-values-reference) | ✅ |

> **Note:** `eyeColor`, `hairStyle`, and `hairColor` use **camelCase** to match the frontend contract.

**Response:** `201 Created`
```json
{
  "ai_companion_id": 1,
  "title": "Luna",
  "description": "A playful, passionate anime companion with a flirtatious voice and intense romantic energy."
}
```

**Error:** `404 Not Found` — User not registered
```json
{
  "detail": "User not registered."
}
```

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
    "description": "A playful, passionate anime companion with a flirtatious voice and intense romantic energy.",
    "gender": "Female",
    "style": "Anime",
    "ethnicity": "East Asian",
    "eyeColor": "Green",
    "hairStyle": "Long",
    "hairColor": "Pink",
    "personality": "Playful",
    "voice": "Breathy",
    "connection": "Passionate Lover"
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
  "description": "A playful, passionate anime companion with a flirtatious voice and intense romantic energy.",
  "gender": "Female",
  "style": "Anime",
  "ethnicity": "East Asian",
  "eyeColor": "Green",
  "hairStyle": "Long",
  "hairColor": "Pink",
  "personality": "Playful",
  "voice": "Breathy",
  "connection": "Passionate Lover"
}
```

**Error:** `404 Not Found` — Companion not found
```json
{
  "detail": "AI companion not found."
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
- The backend strictly validates identity: the user, user companion preferences, and AI companion must exist in the database and be correctly owned.
- The server automatically fetches conversation history from the database and trims it to the last 24 messages before sending it to the model.
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

11. Client can now send another chat request on the same connection.
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

---

## Allowed Values Reference

### User Companion Preferences

| Field | Allowed Values |
|---|---|
| `intent_type` | `"easy"`, `"alive"`, `"lose_myself"` |
| `dominance_mode` | `"user_leads"`, `"ai_leads"`, `"no_rules"` |
| `intensity_level` | `"show_me"`, `"break_glass"`, `"burn_it"` |
| `silence_response` | `"wait"`, `"come_looking"`, `"never_leave"` |
| `secret_desire` | `"running"`, `"searching"`, `"both"` |

### AI Companion Persona

| Field | Allowed Values |
|---|---|
| `gender` | `"Female"`, `"Male"`, `"Other"` |
| `style` | `"Realistic"`, `"Anime"`, `"Cartoon"`, `"Retro Noir"` |
| `ethnicity` | `"African Descent"`, `"South Asian"`, `"Eastern European"`, `"East Asian"`, `"Latinx"`, `"Middle Eastern"` |
| `eyeColor` | `"Brown"`, `"Blue"`, `"Green"`, `"Hazel"`, `"Gray"`, `"Black"` |
| `hairStyle` | `"Short"`, `"Straight"`, `"Long"`, `"Curly"`, `"Braids"`, `"Pixie"` |
| `hairColor` | `"Black"`, `"Brunette"`, `"Blonde"`, `"Pink"`, `"Red"`, `"White"` |
| `personality` | `"Seductive"`, `"Adventurous"`, `"Confident"`, `"Ambitious"`, `"Passionate"`, `"Submissive"`, `"Dominant"`, `"Sensual"`, `"Playful"`, `"Intellectual"`, `"Caring"`, `"Mysterious"` |
| `voice` | `"Calm"`, `"Breathy"`, `"Confident"`, `"Playful"`, `"Deep"`, `"Soft"` |
| `connection` | `"New Encounter"`, `"Casual Hookup"`, `"Friends With Benefits"`, `"Secret Affair"`, `"Passionate Lover"`, `"Dominant Partner"`, `"Submissive Partner"`, `"Long-Distance Desire"`, `"Online Fantasy"` |

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
   ```
   POST /users  →  POST /user-companion  →  POST /ai-companion  →  WebSocket /ws/chat
   ```

3. **WebSocket Lifecycle:**
   - Open one connection per chat session.
   - Wait for the `ready` event before sending the first message.
   - Concatenate all `delta` values to build the assistant's response.
   - Wait for `done` before sending the next user message.
   - On `error`, display the `detail` to the user and allow retry.

4. **Conversation History:** The backend automatically manages and stores the conversation history in the database. The client only needs to send the latest `user_message`. The server retrieves the history, trims it to the last 24 messages, and appends the new message before processing.

5. **camelCase Fields:** AI companion fields `eyeColor`, `hairStyle`, and `hairColor` use camelCase in the API. All other fields use snake_case.

6. **Email Normalization:** Emails are automatically lowercased and trimmed. `"User@Example.COM"` becomes `"user@example.com"`.

7. **Retry Strategy:** If `/health` shows `engine_ready: false`, poll every 5–10 seconds until `engine_ready: true` before attempting WebSocket chat.

8. **CORS:** The backend currently allows requests from `http://127.0.0.1:8501` and `http://localhost:8501` only. If your frontend runs on a different origin (e.g., `http://localhost:3000`), the `MISTRIA_API_CORS_ORIGINS` environment variable must be updated on the backend or you will receive CORS errors.
