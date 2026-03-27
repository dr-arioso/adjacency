"""Adjacency-owned CTO profile registrations."""

from __future__ import annotations

from typing import Any, Mapping

from turnturnturn.profile import Profile, ProfileRegistry

LEXICAL_PROFILE_ID = "lexical_v0_1"


def register() -> None:
    """Register the built-in adjacency lexical profile."""
    ProfileRegistry.register(_LexicalProfile())


class _LexicalProfile(Profile):
    """Lexical profile supporting one or more conversational turns in a single CTO."""

    def __init__(self) -> None:
        super().__init__(
            profile_id=LEXICAL_PROFILE_ID, version=1, fields={}, strict=False
        )

    def validate(self, content: Mapping[str, Any], *, strict: bool = False) -> None:
        speakers = content.get("speakers")
        turns = content.get("turns")
        if not isinstance(speakers, list) or not speakers:
            raise ValueError("lexical_v0_1 requires non-empty list field 'speakers'")
        if not isinstance(turns, list) or not turns:
            raise ValueError("lexical_v0_1 requires non-empty list field 'turns'")

        for speaker in speakers:
            if not isinstance(speaker, dict):
                raise ValueError("lexical_v0_1 speaker entries must be objects")
            session_speaker_id = speaker.get("session_speaker_id")
            display_label = speaker.get("display_label")
            external_speaker_id = speaker.get("external_speaker_id")
            if not isinstance(session_speaker_id, str) or not session_speaker_id:
                raise ValueError(
                    "lexical_v0_1 speakers require non-empty 'session_speaker_id'"
                )
            if not isinstance(display_label, str) or not display_label:
                raise ValueError(
                    "lexical_v0_1 speakers require non-empty 'display_label'"
                )
            if external_speaker_id is not None and not isinstance(
                external_speaker_id, str
            ):
                raise ValueError(
                    "lexical_v0_1 'external_speaker_id' must be a string when provided"
                )

        for turn in turns:
            if not isinstance(turn, dict):
                raise ValueError("lexical_v0_1 turn entries must be objects")
            source_turn_id = turn.get("source_turn_id")
            ordinal = turn.get("ordinal")
            utterance = turn.get("utterance")
            raw_source_tag = turn.get("raw_source_tag")
            if not isinstance(source_turn_id, str) or not source_turn_id:
                raise ValueError(
                    "lexical_v0_1 turns require non-empty 'source_turn_id'"
                )
            if not isinstance(ordinal, int) or ordinal < 1:
                raise ValueError("lexical_v0_1 turns require positive int 'ordinal'")
            if not isinstance(utterance, str):
                raise ValueError("lexical_v0_1 turns require string 'utterance'")
            if raw_source_tag is not None and not isinstance(raw_source_tag, str):
                raise ValueError(
                    "lexical_v0_1 'raw_source_tag' must be a string when provided"
                )

    def apply_defaults(
        self, content: Mapping[str, Any], session_context: dict[str, Any]
    ) -> dict[str, Any]:
        speakers = [dict(speaker) for speaker in content.get("speakers", [])]
        turns = [dict(turn) for turn in content.get("turns", [])]
        return {"speakers": speakers, "turns": turns}
