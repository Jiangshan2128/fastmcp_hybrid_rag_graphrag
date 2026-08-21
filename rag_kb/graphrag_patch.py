"""Monkey-patches for GraphRAG compatibility with non-OpenAI LLMs.

GraphRAG's ``community_reports_extractor`` uses ``response_format`` with a Pydantic
model as the argument, which litellm converts to ``{"type": "json_schema", "strict": true}``.
DeepSeek, GLM, and most non-OpenAI models do not support strict ``json_schema`` mode.

This module patches the callable to fall back to plain JSON parsing using
``model_validate_json``, keeping the same Pydantic model for validation.

Usage::

    from rag_kb.graphrag_patch import patch_community_reports
    patch_community_reports()  # call once before graphrag index
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── CommunityReportsExtractor patch ───────────────────────────────────


def _build_patched_call(original_call):
    """Wrap the original __call__ to handle json_schema incompatibility."""

    async def patched_call(self, input_text: str):
        from pydantic import ValidationError
        from graphrag.index.operations.summarize_communities.community_reports_extractor import (
            CommunityReportResponse,
            INPUT_TEXT_KEY,
            MAX_LENGTH_KEY,
            CommunityReportsResult,
        )

        output = None
        try:
            prompt = self._extraction_prompt.format(**{
                INPUT_TEXT_KEY: input_text,
                MAX_LENGTH_KEY: str(self._max_report_length),
            })

            # Call without response_format — prompt already asks for JSON
            response = await self._model.completion_async(messages=prompt)

            text = (response.content or "").strip()

            # Strip markdown code fences if LLM wraps JSON in ```...```
            if "```json" in text:
                text = text.split("```json", 1)[1].rsplit("```", 1)[0].strip()
            elif "```" in text:
                text = text.split("```", 1)[1].rsplit("```", 1)[0].strip()

            # Strategy 1: direct Pydantic JSON validation (strict)
            try:
                output = CommunityReportResponse.model_validate_json(text)
            except ValidationError:
                # Strategy 2: parse via stdlib json.loads + repair, then model_validate
                import json as _json
                import re

                def _try_parse(t: str) -> dict | None:
                    # 1. Extract content between first { and last }
                    start = t.find("{")
                    end = t.rfind("}")
                    if start < 0 or end <= start:
                        return None
                    t = t[start : end + 1]

                    # 2. Remove trailing commas before ] or }
                    t = re.sub(r",\s*([}\]])", r"\1", t)
                    # Remove control chars
                    t = re.sub(r"[\x00-\x1f]", "", t)

                    # 3. Try json.loads (standard)
                    try:
                        return _json.loads(t)
                    except _json.JSONDecodeError:
                        pass

                    # 4. Strip non-ASCII and retry
                    t2 = re.sub(r"[^\x20-\x7e]", "", t)
                    try:
                        return _json.loads(t2)
                    except _json.JSONDecodeError:
                        pass

                    # 5. raw_decode with progressive truncation (near end)
                    dec = _json.JSONDecoder()
                    for end in range(len(t2), start, -20):
                        try:
                            obj, pos = dec.raw_decode(t2[:end])
                            if pos > start:
                                return obj
                        except _json.JSONDecodeError:
                            continue

                    return None

                parsed = _try_parse(text)
                if parsed is not None:
                    output = CommunityReportResponse.model_validate(parsed)

        except (ValidationError, Exception) as e:
            logger.exception("error parsing community report via patched extractor")
            self._on_error(e, "", None)

        text_output = self._get_text_output(output) if output else ""
        return CommunityReportsResult(
            structured_output=output,
            output=text_output,
        )

    return patched_call


def patch_community_reports() -> bool:
    """Apply the monkey-patch to CommunityReportsExtractor.__call__.

    Returns True if the patch was applied, False if the target class
    was not found (e.g., a future GraphRAG version removed/renamed it).
    """
    try:
        from graphrag.index.operations.summarize_communities import (
            community_reports_extractor,
        )

        # Store original for potential unpatch
        cls = community_reports_extractor.CommunityReportsExtractor
        if not hasattr(cls, "_original_call"):
            cls._original_call = cls.__call__

        cls.__call__ = _build_patched_call(cls._original_call)
        logger.info(
            "Patched CommunityReportsExtractor.__call__ to avoid json_schema mode"
        )
        return True
    except ImportError:
        logger.warning(
            "Could not patch CommunityReportsExtractor — module not found"
        )
        return False
    except Exception as e:
        logger.warning("Failed to patch CommunityReportsExtractor: %s", e)
        return False
