"""Anthropic Claude client for AI call scoring."""

import os
import json
import anthropic

_client = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


SCORING_PROMPT = """You are an expert sales call evaluator for a fitness/gym membership sales organization.
Analyze the following call transcript and return a JSON object with these fields:

- overall_score: integer 0-100
- talk_ratio: integer 0-100 (percentage of time the rep was talking)
- energy: integer 1-10
- objection_handling: integer 1-10
- next_steps: boolean (did the rep establish clear next steps?)
- coach_notes: string (2-3 sentences of actionable coaching advice)

Transcript:
{transcript}

Return ONLY valid JSON, no markdown fences."""


def score_call(transcript: str) -> dict:
    message = get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": SCORING_PROMPT.format(transcript=transcript)}
        ],
    )
    return json.loads(message.content[0].text)
