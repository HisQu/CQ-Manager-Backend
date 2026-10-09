from typing import Iterable, Sequence
from uuid import UUID

from domain.questions.models import Question
from litestar.exceptions import HTTPException
from litestar.exceptions import NotFoundException
from litestar.status_codes import HTTP_400_BAD_REQUEST
from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption
from sqlalchemy.sql.elements import ColumnElement

from .dtos import AnnotationAddDTO, AnnotationRemove, AnnotationUpdate, TermUpdate
from .models import Passage, Term


class AnnotationService:
    @staticmethod
    async def list(
        session: AsyncSession,
        filters: Iterable[ColumnElement[bool]] | None = None,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Term]:
        options = [] if not options else options
        filters = [] if not filters else filters
        statement = select(Term).where(*filters).options(*options)
        scalars = await session.scalars(statement)
        return scalars.all()

    @staticmethod
    async def list_by_question(
        session: AsyncSession,
        question_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Passage]:
        options = [] if not options else options
        statement = select(Question).where(Question.id == question_id)
        if not await session.scalar(statement):
            raise NotFoundException()

        statement = (
            select(Passage)
            .where(Passage.question_id == question_id)
            .options(*options)
        )
        scalars = await session.scalars(statement)
        return scalars.all()

    @staticmethod
    async def list_questions_by_term(
        session: AsyncSession,
        term_id: UUID,
        project_id: UUID,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Question]:
        options = [] if not options else options
        subquery = (
            select(Term)
            .where(Term.id == term_id, Term.project_id == project_id)
            .subquery()
        )
        statement = select(Question).join(Passage, Passage.question_id == Question.id)
        statement = statement.join(subquery, Passage.term_id == subquery.c.id)
        statement = statement.options(*options)
        scalars = await session.scalars(statement)
        return scalars.all()

    @staticmethod
    async def get_or_create_term(
        session: AsyncSession,
        project_id: UUID,
        term: str,
        definition: str | None = None,
        concept_iri: str | None = None,
    ) -> Term:
        if model := await session.scalar(
            select(Term).where(Term.content == term, Term.project_id == project_id)
        ):
            return model

        model = Term(
            content=term,
            definition=definition,
            concept_iri=concept_iri,
            project_id=project_id,
        )
        session.add(model)
        await session.commit()
        await session.refresh(model)
        return model

    @staticmethod
    async def update_term(
        session: AsyncSession, project_id: UUID, term_id: UUID, data: TermUpdate
    ) -> Term:
        statement = select(Term).where(
            Term.id == term_id, Term.project_id == project_id
        )
        if not (term := await session.scalar(statement)):
            raise NotFoundException()

        if data.content is not None:
            duplicate_statement = select(Term).where(
                Term.project_id == project_id,
                Term.content == data.content,
                Term.id != term.id,
            )
            if await session.scalar(duplicate_statement):
                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail=f"A term with the content '{data.content}' already exists in this project.",
                )
            term.content = data.content

        if data.definition is not None:
            term.definition = data.definition
        if data.concept_iri is not None:
            term.concept_iri = data.concept_iri
        await session.commit()
        await session.refresh(term)
        return term

    @staticmethod
    async def update_annotation(
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
        passage_id: UUID,
        data: AnnotationUpdate,
    ) -> Passage:
        statement = (
            select(Question)
            .where(Question.id == question_id)
            .options(
                selectinload(Question.group),
                selectinload(Question.annotations).options(selectinload(Passage.term)),
            )
        )
        if not (question := await session.scalar(statement)):
            raise NotFoundException()

        if question.group.project_id != project_id:
            raise NotFoundException()

        passage = next(filter(lambda p: p.id == passage_id, question.annotations), None)
        if not passage:
            raise NotFoundException()

        AnnotationService.validate_span(
            question.question, data.start, data.end, data.passage
        )

        target_term = await session.scalar(
            select(Term).where(Term.project_id == project_id, Term.content == data.term)
        )
        if not target_term:
            target_term = Term(content=data.term, project_id=project_id)
            session.add(target_term)
            await session.flush()

        passage.content = data.passage
        passage.start = data.start
        passage.end = data.end
        passage.term = target_term
        await session.commit()
        await session.refresh(passage)
        return passage

    @staticmethod
    async def delete_term(
        session: AsyncSession, project_id: UUID, term_id: UUID
    ) -> bool:
        statement = (
            select(Term)
            .where(Term.id == term_id, Term.project_id == project_id)
            .options(selectinload(Term.passages))
        )
        if not (term := await session.scalar(statement)):
            return False

        await session.delete(term)
        await session.commit()
        return True

    @staticmethod
    async def annotate(
        session: AsyncSession,
        question_id: UUID,
        data: AnnotationAddDTO,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Passage]:
        options = [] if not options else options
        statement = (
            select(Question)
            .where(Question.id == question_id)
            .options(
                selectinload(Question.annotations).options(selectinload(Passage.term)),
                selectinload(Question.group),
                *options,
            )
        )
        if question := await session.scalar(statement):
            for annotation in data.annotations:
                AnnotationService.validate_span(
                    question.question,
                    annotation.start,
                    annotation.end,
                    annotation.passage,
                )

            for annotation in data.annotations:
                term = await AnnotationService.get_or_create_term(
                    session,
                    question.group.project_id,
                    annotation.term,
                    annotation.definition,
                    annotation.concept_iri,
                )
                existing = await session.scalar(
                    select(Passage).where(
                        Passage.question_id == question.id,
                        Passage.term_id == term.id,
                        Passage.start == annotation.start,
                        Passage.end == annotation.end,
                    )
                )
                if existing:
                    continue
                question.annotations.append(
                    Passage(
                        content=annotation.passage,
                        start=annotation.start,
                        end=annotation.end,
                        term=term,
                    )
                )
            await session.commit()
            question = await session.scalar(statement)
            assert question
            return question.annotations
        raise NotFoundException()

    @staticmethod
    async def remove_annotations(
        session: AsyncSession,
        question_id: UUID,
        data: AnnotationRemove,
        options: Iterable[ExecutableOption] | None = None,
    ) -> Sequence[Passage]:
        options = [] if not options else options
        statement = (
            select(Question)
            .where(Question.id == question_id)
            .options(selectinload(Question.annotations), selectinload(Question.group))
        )
        if question := await session.scalar(statement):
            if data.passage_ids:
                selected_ids = set(data.passage_ids)
                for annotation in list(question.annotations):
                    if annotation.id in selected_ids:
                        question.annotations.remove(annotation)
                await session.commit()

            scalars = await session.scalars(
                select(Passage)
                .where(Passage.question_id == question_id)
                .options(*options)
            )
            return scalars.all()

        raise NotFoundException()

    @staticmethod
    def validate_span(text: str, start: int, end: int, value: str) -> None:
        if not AnnotationService.span_matches(text, start, end, value):
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Annotation span must match the selected text in the question.",
            )

    @staticmethod
    def span_matches(text: str, start: int, end: int, value: str) -> bool:
        """Check offsets measured in JavaScript UTF-16 code units."""
        encoded_text = text.encode("utf-16-le", errors="surrogatepass")
        if start < 0 or end <= start or end * 2 > len(encoded_text):
            return False

        selected = encoded_text[start * 2 : end * 2].decode(
            "utf-16-le", errors="surrogatepass"
        )
        return selected == value
