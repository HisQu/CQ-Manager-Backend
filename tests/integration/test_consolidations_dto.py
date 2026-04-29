from uuid import UUID

import pytest
import sys
from pydantic import ValidationError

sys.path.append("src/app/")

from domain.consolidations.dtos import ConsolidationCreate


GROUP_ID = UUID("a825cd37-f637-4853-bc73-97a2b01f18e7")
QUESTION_ID = UUID("4f8c5f0b-5966-49d6-8d0f-a9a2e7883114")


def test_consolidation_create_accepts_new_result_question() -> None:
    payload = ConsolidationCreate(
        ids=[QUESTION_ID],
        result_question={
            "question": "A generated result question",
            "group_id": GROUP_ID,
        },
    )
    assert payload.result_question is not None
    assert payload.result_question_id is None


def test_consolidation_create_accepts_existing_result_question() -> None:
    payload = ConsolidationCreate(
        ids=[QUESTION_ID],
        result_question_id=QUESTION_ID,
    )
    assert payload.result_question is None
    assert payload.result_question_id == QUESTION_ID


def test_consolidation_create_accepts_existing_result_question_nested_id() -> None:
    payload = ConsolidationCreate(
        ids=[QUESTION_ID],
        result_question={"id": QUESTION_ID},
    )
    assert payload.result_question is None
    assert payload.result_question_id == QUESTION_ID


def test_consolidation_create_rejects_both_result_sources() -> None:
    with pytest.raises(ValidationError):
        ConsolidationCreate(
            ids=[QUESTION_ID],
            result_question={
                "question": "A generated result question",
                "group_id": GROUP_ID,
            },
            result_question_id=QUESTION_ID,
        )


def test_consolidation_create_rejects_missing_result_source() -> None:
    with pytest.raises(ValidationError):
        ConsolidationCreate(ids=[QUESTION_ID])
