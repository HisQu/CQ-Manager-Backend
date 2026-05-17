import re
from typing import Iterable, Sequence
from uuid import UUID

from domain.consolidations.models import Consolidation
from domain.groups.models import Group
from domain.topics.models import Topic
from litestar.exceptions import HTTPException
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.base import ExecutableOption

from .dtos import (
    QuestionAnnotation,
    QuestionAnnotationTerm,
    QuestionComment,
    QuestionConsolidationContext,
    QuestionConsolidationRole,
    QuestionDetail,
    QuestionDetailConsolidation,
    QuestionDetailConsolidationQuestion,
    QuestionDetailConsolidationQuestionGroup,
    QuestionGroup,
    QuestionOverview,
    QuestionProject,
    QuestionRating,
    QuestionTopic,
    QuestionUser,
    QuestionVersion,
    UnifiedQuestionAuthor,
    UnifiedQuestionEntryKind,
    UnifiedQuestionGroup,
    UnifiedQuestionOverview,
    UnifiedQuestionTopic,
)
from .models import Question

CQ_CATALOGUE_IDENTIFIER_PATTERN = re.compile(r"^([A-Z]+)\.(\d+)$")


def normalize_cq_catalogue_identifier(identifier: str) -> tuple[str, int]:
    normalized = identifier.strip().upper()
    match = CQ_CATALOGUE_IDENTIFIER_PATTERN.fullmatch(normalized)
    if not match:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="CQ catalogue identifier must use the format '<topic>.<index>', e.g. 'A.1'.",
        )

    topic_identifier, catalogue_index = match.groups()
    return topic_identifier, int(catalogue_index)


class QuestionService:
    @staticmethod
    def to_question_overview(question: Question) -> QuestionOverview:
        return QuestionOverview(
            id=question.id,
            question=question.question,
            comment=question.comment,
            cq_catalogue_identifier=question.cq_catalogue_identifier,
            reference=question.reference,
            anchor=question.anchor,
            example_answer=question.example_answer,
            type=question.type,
            sparql_query=question.sparql_query,
            rating=question.aggregated_rating,
            no_consolidations=question.no_consolidations,
            group=QuestionGroup(id=question.group.id, name=question.group.name) if question.group else None,
            topic=(
                QuestionTopic(
                    id=question.topic.id,
                    identifier=question.topic.identifier,
                    name=question.topic.name,
                )
                if question.topic
                else None
            ),
            author=(
                QuestionUser(
                    id=question.author.id,
                    email=question.author.email,
                    name=question.author.name,
                )
                if question.author
                else None
            ),
            consolidations=QuestionService._to_consolidation_contexts(question),
        )

    @staticmethod
    def to_question_overviews(questions: Sequence[Question]) -> list[QuestionOverview]:
        return [QuestionService.to_question_overview(question) for question in questions]

    @staticmethod
    def _to_consolidation_context(
        consolidation: Consolidation,
        role: QuestionConsolidationRole,
    ) -> QuestionConsolidationContext:
        source_question_ids = sorted(
            (source_question.id for source_question in consolidation.questions),
            key=str,
        )
        return QuestionConsolidationContext(
            id=consolidation.id,
            role=role,
            source_question_ids=source_question_ids,
            target_question_id=consolidation.result_question_id,
        )

    @staticmethod
    def _to_consolidation_contexts(
        question: Question,
    ) -> list[QuestionConsolidationContext]:
        contexts: list[QuestionConsolidationContext] = []
        seen: set[tuple[UUID, QuestionConsolidationRole]] = set()

        for consolidation in question.target_consolidations:
            key = (consolidation.id, QuestionConsolidationRole.TARGET)
            if key not in seen:
                contexts.append(
                    QuestionService._to_consolidation_context(
                        consolidation,
                        QuestionConsolidationRole.TARGET,
                    )
                )
                seen.add(key)

        for consolidation in question.consolidations:
            role = (
                QuestionConsolidationRole.TARGET
                if consolidation.result_question_id == question.id
                else QuestionConsolidationRole.SOURCE
            )
            key = (consolidation.id, role)
            if key not in seen:
                contexts.append(QuestionService._to_consolidation_context(consolidation, role))
                seen.add(key)

        return sorted(contexts, key=lambda context: (str(context.id), context.role.value))

    @staticmethod
    def _to_detail_consolidation_question(
        question: Question | None,
    ) -> QuestionDetailConsolidationQuestion | None:
        if question is None:
            return None

        return QuestionDetailConsolidationQuestion(
            id=question.id,
            group=(
                QuestionDetailConsolidationQuestionGroup(
                    id=question.group.id,
                    name=question.group.name,
                )
                if question.group
                else None
            ),
            question=question.question,
            comment=question.comment,
            cq_catalogue_identifier=question.cq_catalogue_identifier,
            reference=question.reference,
            anchor=question.anchor,
            example_answer=question.example_answer,
            type=question.type,
            sparql_query=question.sparql_query,
            aggregated_rating=question.aggregated_rating,
            author=QuestionUser(
                id=question.author.id,
                email=question.author.email,
                name=question.author.name,
            ),
        )

    @staticmethod
    def _to_detail_consolidation(consolidation: Consolidation) -> QuestionDetailConsolidation:
        return QuestionDetailConsolidation(
            id=consolidation.id,
            target_question=QuestionService._to_detail_consolidation_question(consolidation.result_question),
            no_source_questions=consolidation.no_questions,
            project=QuestionProject(
                id=consolidation.project.id,
                name=consolidation.project.name,
            ),
            engineer=QuestionUser(
                id=consolidation.engineer.id,
                email=consolidation.engineer.email,
                name=consolidation.engineer.name,
            ),
            source_questions=[
                source_question
                for source_question in (
                    QuestionService._to_detail_consolidation_question(question)
                    for question in sorted(consolidation.questions, key=lambda item: str(item.id))
                )
                if source_question is not None
            ],
        )

    @staticmethod
    def _to_detail_consolidations(question: Question) -> list[QuestionDetailConsolidation]:
        consolidations_by_id: dict[UUID, Consolidation] = {
            consolidation.id: consolidation
            for consolidation in [*question.consolidations, *question.target_consolidations]
        }
        return [
            QuestionService._to_detail_consolidation(consolidation)
            for consolidation in sorted(consolidations_by_id.values(), key=lambda item: str(item.id))
        ]

    @staticmethod
    def to_question_detail(question: Question) -> QuestionDetail:
        return QuestionDetail(
            id=question.id,
            question=question.question,
            comment=question.comment,
            cq_catalogue_identifier=question.cq_catalogue_identifier,
            reference=question.reference,
            anchor=question.anchor,
            example_answer=question.example_answer,
            type=question.type,
            sparql_query=question.sparql_query,
            group_id=question.group_id,
            version_number=question.version_number,
            ratings=[
                QuestionRating(
                    rating=rating.rating,
                    author=QuestionUser(
                        id=rating.author.id,
                        email=rating.author.email,
                        name=rating.author.name,
                    ),
                )
                for rating in question.ratings
            ],
            aggregated_rating=question.aggregated_rating,
            author=QuestionUser(
                id=question.author.id,
                email=question.author.email,
                name=question.author.name,
            ),
            editor=QuestionUser(
                id=question.editor.id,
                email=question.editor.email,
                name=question.editor.name,
            ),
            group=QuestionGroup(
                id=question.group.id,
                name=question.group.name,
                project=(
                    QuestionProject(
                        id=question.group.project.id,
                        name=question.group.project.name,
                    )
                    if question.group.project
                    else None
                ),
            ),
            topic=(
                QuestionTopic(
                    id=question.topic.id,
                    identifier=question.topic.identifier,
                    name=question.topic.name,
                )
                if question.topic
                else None
            ),
            comments=[
                QuestionComment(
                    comment=comment.comment,
                    created_at=comment.created_at,
                    author=QuestionUser(
                        id=comment.author.id,
                        email=comment.author.email,
                        name=comment.author.name,
                    ),
                )
                for comment in question.comments
            ],
            no_consolidations=question.no_consolidations,
            consolidations=QuestionService._to_detail_consolidations(question),
            versions=[
                QuestionVersion(
                    question_string=version.question_string,
                    version_number=version.version_number,
                    editor=QuestionUser(
                        id=version.editor.id,
                        email=version.editor.email,
                        name=version.editor.name,
                    ),
                )
                for version in question.versions
            ],
            annotations=[
                QuestionAnnotation(
                    id=annotation.id,
                    content=annotation.content,
                    term=QuestionAnnotationTerm(
                        id=annotation.term.id,
                        content=annotation.term.content,
                    ),
                )
                for annotation in question.annotations
            ],
        )

    @staticmethod
    def _to_unified_question_entry(
        question: Question,
        entry_kind: UnifiedQuestionEntryKind = UnifiedQuestionEntryKind.QUESTION,
        consolidation_id: UUID | None = None,
        consolidation_context: QuestionConsolidationContext | None = None,
    ) -> UnifiedQuestionOverview:
        return UnifiedQuestionOverview(
            id=question.id,
            question=question.question,
            comment=question.comment,
            cq_catalogue_identifier=question.cq_catalogue_identifier,
            reference=question.reference,
            anchor=question.anchor,
            example_answer=question.example_answer,
            type=question.type,
            sparql_query=question.sparql_query,
            rating=question.aggregated_rating,
            no_consolidations=question.no_consolidations,
            group=UnifiedQuestionGroup(id=question.group.id, name=question.group.name),
            topic=(
                UnifiedQuestionTopic(
                    id=question.topic.id,
                    identifier=question.topic.identifier,
                    name=question.topic.name,
                )
                if question.topic
                else None
            ),
            author=UnifiedQuestionAuthor(
                id=question.author.id,
                email=question.author.email,
                name=question.author.name,
            ),
            unified_entry_kind=entry_kind,
            consolidation=consolidation_context,
        )

    @staticmethod
    def _to_unified_consolidation_entry(
        consolidation: Consolidation, fallback_question: Question
    ) -> UnifiedQuestionOverview:
        consolidation_context = QuestionService._to_consolidation_context(
            consolidation,
            QuestionConsolidationRole.TARGET,
        )

        result_question = consolidation.result_question
        if result_question is None:
            return UnifiedQuestionOverview(
                id=consolidation.id,
                question=fallback_question.question,
                comment=fallback_question.comment,
                cq_catalogue_identifier=fallback_question.cq_catalogue_identifier,
                reference=fallback_question.reference,
                anchor=fallback_question.anchor,
                example_answer=fallback_question.example_answer,
                type=fallback_question.type,
                sparql_query=None,
                rating=0,
                no_consolidations=0,
                group=UnifiedQuestionGroup(id=fallback_question.group.id, name=fallback_question.group.name),
                topic=(
                    UnifiedQuestionTopic(
                        id=fallback_question.topic.id,
                        identifier=fallback_question.topic.identifier,
                        name=fallback_question.topic.name,
                    )
                    if fallback_question.topic
                    else None
                ),
                author=UnifiedQuestionAuthor(
                    id=consolidation.engineer.id,
                    email=consolidation.engineer.email,
                    name=consolidation.engineer.name,
                ),
                unified_entry_kind=UnifiedQuestionEntryKind.CONSOLIDATION_RESULT,
                consolidation=consolidation_context,
            )

        return QuestionService._to_unified_question_entry(
            result_question,
            entry_kind=UnifiedQuestionEntryKind.CONSOLIDATION_RESULT,
            consolidation_id=consolidation.id,
            consolidation_context=consolidation_context,
        )

    @staticmethod
    async def get_questions_by_group(
        session: AsyncSession,
        group_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Question]:
        options = [] if not options else options
        statement = select(Question).where(Question.group_id == group_id).options(*options)
        return (await session.scalars(statement)).all()

    @staticmethod
    async def get_questions_by_project(
        session: AsyncSession,
        project_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Question]:
        options = [] if not options else options
        statement = select(Question).join(Group).filter(Group.project_id == project_id).options(*options)
        return (await session.scalars(statement)).all()

    @staticmethod
    async def resolve_cq_catalogue_identifier(
        session: AsyncSession,
        project_id: UUID,
        catalogue_identifier: str,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Question:
        topic_identifier, catalogue_index = normalize_cq_catalogue_identifier(catalogue_identifier)
        statement = (
            select(Question)
            .join(Topic)
            .join(Group)
            .where(
                Topic.project_id == project_id,
                Topic.identifier == topic_identifier,
                Question.catalogue_index == catalogue_index,
                Group.project_id == project_id,
            )
        )
        if options:
            statement = statement.options(*options)

        question = await session.scalar(statement)
        if not question:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail="Question catalogue identifier not found for this project.",
            )
        return question

    @staticmethod
    def _unify_consolidated_questions(
        questions: Sequence[Question],
    ) -> list[UnifiedQuestionOverview]:
        unified: list[UnifiedQuestionOverview] = []
        consolidation_map: dict[UUID, Consolidation] = {
            consolidation.id: consolidation for question in questions for consolidation in question.consolidations
        }
        result_question_ids = {
            consolidation.result_question_id
            for consolidation in consolidation_map.values()
            if consolidation.result_question_id is not None
        }
        seen_consolidation_ids: set[UUID] = set()

        for question in questions:
            if question.id in result_question_ids:
                continue

            consolidation_ids = sorted(
                (consolidation.id for consolidation in question.consolidations),
                key=str,
            )

            if not consolidation_ids:
                unified.append(QuestionService._to_unified_question_entry(question))
                continue

            unconsolidated_ids = [
                consolidation_id
                for consolidation_id in consolidation_ids
                if consolidation_id not in seen_consolidation_ids
            ]
            if not unconsolidated_ids:
                continue

            # One consolidation result entry is emitted per unseen consolidation.
            for consolidation_id in unconsolidated_ids:
                consolidation = consolidation_map[consolidation_id]
                unified.append(QuestionService._to_unified_consolidation_entry(consolidation, question))
            seen_consolidation_ids.update(unconsolidated_ids)

        return unified

    @staticmethod
    async def get_unified_questions_by_group(
        session: AsyncSession,
        group_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[UnifiedQuestionOverview]:
        questions = await QuestionService.get_questions_by_group(session, group_id, options)
        return QuestionService._unify_consolidated_questions(questions)

    @staticmethod
    async def get_unified_questions_by_project(
        session: AsyncSession,
        project_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[UnifiedQuestionOverview]:
        questions = await QuestionService.get_questions_by_project(session, project_id, options)
        return QuestionService._unify_consolidated_questions(questions)
