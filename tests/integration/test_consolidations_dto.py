from uuid import uuid4

import pytest
import sys
from types import SimpleNamespace
from pydantic import ValidationError

sys.path.append("src/app/")

from domain.consolidations.dtos import ConsolidationCreate, ConsolidationRead

GROUP_ID = uuid4()
QUESTION_ID = uuid4()


def test_consolidation_create_accepts_new_target_question() -> None:
    payload = ConsolidationCreate(
        source_question_ids=[QUESTION_ID],
        target_question={
            "question": "A generated target question",
            "group_id": GROUP_ID,
        },
    )
    assert payload.target_question is not None
    assert payload.target_question.id is None


def test_consolidation_create_accepts_new_target_question_without_group() -> None:
    payload = ConsolidationCreate(
        source_question_ids=[QUESTION_ID],
        target_question={
            "question": "A generated target question",
        },
    )
    assert payload.target_question is not None
    assert payload.target_question.group_id is None
    assert payload.target_question.id is None


def test_consolidation_create_accepts_existing_target_question() -> None:
    payload = ConsolidationCreate(
        source_question_ids=[QUESTION_ID],
        target_question={"id": QUESTION_ID},
    )
    assert payload.target_question.id == QUESTION_ID


def test_consolidation_create_accepts_existing_target_question_nested_id() -> None:
    payload = ConsolidationCreate(
        source_question_ids=[QUESTION_ID],
        target_question={"id": QUESTION_ID},
    )
    assert payload.target_question.id == QUESTION_ID


def test_consolidation_create_rejects_both_target_sources() -> None:
    with pytest.raises(ValidationError):
        ConsolidationCreate(
            source_question_ids=[QUESTION_ID],
            target_question={
                "id": QUESTION_ID,
                "question": "A generated target question",
                "group_id": GROUP_ID,
            },
        )


def test_consolidation_create_rejects_missing_target_source() -> None:
    with pytest.raises(ValidationError):
        ConsolidationCreate(source_question_ids=[QUESTION_ID])


def test_consolidation_read_accepts_questions_without_group() -> None:
    user = SimpleNamespace(
        id=uuid4(),
        email="engineer@example.test",
        name="Engineer",
    )
    question = SimpleNamespace(
        id=uuid4(),
        group=None,
        question="A question whose group was deleted",
        sparql_query=None,
        aggregated_rating=0,
        author=user,
    )
    consolidation = SimpleNamespace(
        id=uuid4(),
        result_question_id=question.id,
        result_question=question,
        no_questions=1,
        engineer=user,
        questions=[question],
        project=SimpleNamespace(id=uuid4(), name="Project"),
    )

    payload = ConsolidationRead.model_validate(consolidation)

    assert payload.target_question is not None
    assert payload.target_question.group is None
    assert payload.source_questions[0].group is None
