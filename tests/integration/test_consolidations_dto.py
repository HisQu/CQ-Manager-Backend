from uuid import uuid4

import pytest
import sys
from types import SimpleNamespace
from pydantic import ValidationError

sys.path.append("src/app/")

from domain.consolidations.dtos import ConsolidationCreate, ConsolidationRead

GROUP_ID = uuid4()
QUESTION_ID = uuid4()


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


def test_consolidation_create_accepts_new_result_question_without_group() -> None:
    payload = ConsolidationCreate(
        ids=[QUESTION_ID],
        result_question={
            "question": "A generated result question",
        },
    )
    assert payload.result_question is not None
    assert payload.result_question.group_id is None
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

    assert payload.result_question is not None
    assert payload.result_question.group is None
    assert payload.questions[0].group is None
