"""Background worker for engagement scoring and webhook dispatch."""

from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

import httpx

from src.Logging import get_logger
from src.backend.schemas import ChatMessage, InferencePromptRequest
from src.config import Engagement
from src.engagement import parsing, prompts, state

if TYPE_CHECKING:
    from src.backend.runtime import BaseInferenceRuntime
    from src.storage.service import ChatHistoryService

logger = get_logger(__name__)

_WEBHOOK_TIMEOUT_SECONDS = 10.0
_SCORING_MAX_TOKENS = 5
_SCORING_TEMPERATURE = 0.1


class EngagementScoringWorker:
    """Schedule and run engagement scoring jobs without blocking chat streaming."""

    def __init__(
            self,
            runtime: BaseInferenceRuntime,
            history_service: ChatHistoryService,
            engagement_config: Engagement,
    ):
        """Initialize the engagement scoring worker.

        Args:
            runtime: Inference runtime used to score recent conversation history.
            history_service: Service used to fetch recent persisted messages.
            engagement_config: Engagement scoring and webhook settings.
        """
        self.runtime = runtime
        self.history_service = history_service
        self.engagement_config = engagement_config
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def is_enabled(self) -> bool:
        """Return whether engagement scoring is configured to run."""
        return bool(self.engagement_config.external_backend_webhook_url)

    def schedule(self, conversation_id: str, user_id: str, companion_id: str) -> None:
        """Schedule a non-blocking engagement scoring job.

        Args:
            conversation_id: The active conversation identifier.
            user_id: External user identifier (for example, email).
            companion_id: AI companion identifier.
        """
        if not self.is_enabled:
            return

        task = asyncio.create_task(
            self.calculate_and_dispatch_score(conversation_id, user_id, companion_id),
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self) -> None:
        """Gracefully shut down the worker, waiting briefly for pending jobs."""
        if not self._tasks:
            return

        logger.info(
            "EngagementScoringWorker shutting down. Waiting for %d pending jobs.",
            len(self._tasks),
        )
        done, pending = await asyncio.wait(self._tasks, timeout=5.0)
        if pending:
            logger.warning(
                "EngagementScoringWorker shutdown timeout. Cancelling %d tasks.",
                len(pending),
            )
            for task in pending:
                task.cancel()
            await asyncio.wait(pending, timeout=1.0)

        logger.info("EngagementScoringWorker shutdown complete.")

    async def calculate_and_dispatch_score(
            self,
            conversation_id: str,
            user_id: str,
            companion_id: str,
    ) -> None:
        """Calculate engagement score and dispatch a webhook when it changes."""
        webhook_url = self.engagement_config.external_backend_webhook_url
        if not webhook_url:
            return

        try:
            conversation_key = str(conversation_id)
            numeric_conversation_id = int(conversation_id)

            message_records = await asyncio.to_thread(
                self.history_service.list_recent_messages,
                numeric_conversation_id,
                self.engagement_config.history_limit,
            )
            if not message_records:
                logger.info(
                    "Engagement scoring skipped (no history) conversation_id=%s",
                    conversation_key,
                )
                return

            chat_messages = [
                ChatMessage(role=record.role, content=record.content)  # type: ignore[arg-type]
                for record in message_records
            ]
            inference_request = InferencePromptRequest(
                system_prompt=prompts.ENGAGEMENT_SCORING_PROMPT,
                messages=chat_messages,
                max_tokens=_SCORING_MAX_TOKENS,
                temperature=_SCORING_TEMPERATURE,
            )

            new_score = await self._evaluate_engagement_score(inference_request)
            if new_score is None:
                logger.warning(
                    "Engagement scoring aborted (invalid LLM output) conversation_id=%s",
                    conversation_key,
                )
                return

            last_known_score = state.get_last_score(conversation_key)
            if new_score == last_known_score:
                logger.debug(
                    "Engagement score unchanged conversation_id=%s score=%s",
                    conversation_key,
                    new_score,
                )
                return

            payload = {
                "user_id": user_id,
                "ai_companion_id": int(companion_id),
                "engagement_score": new_score,
            }
            dispatched = await self._dispatch_webhook(webhook_url, payload, conversation_key)
            if dispatched:
                state.set_last_score(conversation_key, new_score)
                return

            logger.warning(
                "Engagement score not persisted locally after webhook failure "
                "conversation_id=%s last_known_score=%s attempted_score=%s",
                conversation_key,
                last_known_score,
                new_score,
            )
        except Exception:
            logger.exception(
                "Engagement scoring job failed conversation_id=%s user_id=%s companion_id=%s",
                conversation_id,
                user_id,
                companion_id,
            )

    async def _evaluate_engagement_score(self, inference_request: InferencePromptRequest) -> int | None:
        """Return an engagement score from the configured inference backend."""
        if self.runtime.backend_name == "mock":
            score = random.randint(1, 100)  # nosec B311
            logger.debug("Engagement scoring using mock backend random score=%s", score)
            return score

        raw_output = await self.runtime.generate_text(inference_request)
        return parsing.parse_engagement_score(raw_output)

    async def _dispatch_webhook(
            self,
            webhook_url: str,
            payload: dict[str, object],
            conversation_id: str,
    ) -> bool:
        """POST the engagement score and return True only when the backend accepts it.

        Acceptance requires HTTP 2xx and a JSON body with ``status`` equal to
        ``success``. Failures are logged and not retried on this turn so the
        in-memory score can stay at the last delivered value.
        """
        try:
            async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT_SECONDS) as client:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()
            if not _is_successful_webhook_payload(response):
                logger.warning(
                    "Engagement webhook rejected conversation_id=%s score=%s body=%s",
                    conversation_id,
                    payload["engagement_score"],
                    _safe_response_text(response),
                )
                return False
            logger.info(
                "Engagement webhook dispatched conversation_id=%s score=%s",
                conversation_id,
                payload["engagement_score"],
            )
            return True
        except httpx.RequestError as exc:
            logger.warning(
                "Engagement webhook request failed conversation_id=%s error=%s",
                conversation_id,
                exc,
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Engagement webhook returned error status conversation_id=%s status=%s",
                conversation_id,
                exc.response.status_code,
            )
        except Exception as e:
            logger.exception(
                "Engagement webhook raised Exception, conversation_id=%s traceback=%s",
                conversation_id,
                str(e),
            )
        return False


def _is_successful_webhook_payload(response: httpx.Response) -> bool:
    """Return True when the webhook JSON body reports ``status=success``."""
    try:
        body = response.json()
    except ValueError:
        return False
    if not isinstance(body, dict):
        return False
    return str(body.get("status", "")).strip().lower() == "success"


def _safe_response_text(response: httpx.Response, *, limit: int = 200) -> str:
    """Return a truncated response body for logs."""
    text = (response.text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."
