from collections.abc import Iterable, Sequence
from uuid import UUID

from domain.questions.models import Question
from litestar.exceptions import HTTPException, NotFoundException
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_409_CONFLICT
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption
from sqlalchemy.sql.elements import ColumnElement

from .dtos import AnnotationSetSaveDTO, TermCreate, TermUpdate
from .models import Passage, Term
from domain.versions.models import AnnotationVersion, Version


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
    ) -> Sequence[Passage]:
        question = await session.scalar(
            select(Question)
            .where(Question.id == question_id)
            .options(
                selectinload(Question.versions).options(
                    selectinload(Version.annotation_versions).options(
                        selectinload(AnnotationVersion.annotations).options(selectinload(Passage.term))
                    )
                )
            )
        )
        if not question:
            raise NotFoundException()
        current_revision = next(
            (revision for revision in question.versions if revision.version_number == question.version_number), None
        )
        current_annotation_version = (
            max(current_revision.annotation_versions, key=lambda item: item.version_number, default=None)
            if current_revision
            else None
        )
        return current_annotation_version.annotations if current_annotation_version else []

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
        latest_annotation_versions = (
            select(
                AnnotationVersion.question_version_id.label("question_version_id"),
                func.max(AnnotationVersion.version_number).label("version_number"),
            )
            .group_by(AnnotationVersion.question_version_id)
            .subquery()
        )
        statement = select(Question).join(Version, Version.question_id == Question.id)
        statement = statement.where(Version.version_number == Question.version_number)
        statement = statement.join(
            latest_annotation_versions,
            latest_annotation_versions.c.question_version_id == Version.id,
        )
        statement = statement.join(
            AnnotationVersion,
            and_(
                AnnotationVersion.question_version_id == Version.id,
                AnnotationVersion.version_number == latest_annotation_versions.c.version_number,
            ),
        )
        statement = statement.join(Passage, Passage.annotation_version_id == AnnotationVersion.id)
        statement = statement.join(subquery, Passage.term_id == subquery.c.id)
        statement = statement.options(*options)
        statement = statement.distinct()
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
        # Keep term creation in the callers transaction. Committing here expires
        # already-loaded ORM objects (including the Question being annotated),
        # and accessing their attributes later can trigger async lazy loading.
        await session.flush()
        return model

    @staticmethod
    async def create_term(session: AsyncSession, project_id: UUID, data: TermCreate) -> Term:
        term = await AnnotationService.get_or_create_term(
            session, project_id, data.content, data.definition, data.concept_iri
        )
        if "definition" in data.model_fields_set:
            term.definition = data.definition
        if "concept_iri" in data.model_fields_set:
            term.concept_iri = data.concept_iri
        await session.commit()
        await session.refresh(term)
        return term

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
    async def save_annotation_version(
        session: AsyncSession,
        question_id: UUID,
        revision_id: UUID,
        data: AnnotationSetSaveDTO,
        editor_id: UUID,
    ) -> AnnotationVersion:
        statement = (
            select(Question)
            .where(Question.id == question_id)
            .options(
                selectinload(Question.group),
                selectinload(Question.versions).options(
                    selectinload(Version.annotation_versions).options(
                        selectinload(AnnotationVersion.annotations)
                    )
                ),
            )
        )
        if not (question := await session.scalar(statement)):
            raise NotFoundException()
        if question.deleted_at is not None:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Deleted questions are read-only.")

        # verify that since the last time the user loaded the annotations, no new annotation version has been created
        # otherwise we throw a conflict and ask the user to reload the latest annotations before saving
        revision = next((item for item in question.versions if item.id == revision_id), None)
        if revision is None:
            raise NotFoundException()
        if revision.version_number != question.version_number:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Only the latest CQ revision can be annotated.")

        project_id = question.group.project_id
        for annotation in data.annotations:
            AnnotationService.validate_span(
                revision.question_string,
                annotation.start,
                annotation.end,
                annotation.passage,
            )

        existing_versions = revision.annotation_versions
        latest = max(existing_versions, key=lambda item: item.version_number, default=None)
        if latest is None or latest.id != data.base_annotation_version_id:
            raise HTTPException(
                status_code=HTTP_409_CONFLICT,
                detail="The annotation version changed. Reload the latest annotations before saving.",
            )
        latest_number = latest.version_number
        seen_spans: set[tuple[str, int, int]] = set()
        for annotation in data.annotations:
            identity = (annotation.term, annotation.start, annotation.end)
            if identity in seen_spans:
                raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Duplicate annotation occurrence.")
            seen_spans.add(identity)
        snapshot = AnnotationVersion(
            question_version_id=revision.id,
            version_number=latest_number + 1,
            editor_id=editor_id,
            copy_status="saved",
        )
        session.add(snapshot)
        # Persist the snapshot first so it has an ID before passages are
        # created. Assigning new children through relationships to objects
        # that are not yet in the session can trigger autoflush warnings and
        # leave the children detached from this transaction.
        await session.flush()
        snapshot_id = snapshot.id

        for annotation in data.annotations:
            term = await AnnotationService.get_or_create_term(
                session,
                project_id,
                annotation.term,
                annotation.definition,
                annotation.concept_iri,
            )
            if "definition" in annotation.model_fields_set:
                term.definition = annotation.definition
            if "concept_iri" in annotation.model_fields_set:
                term.concept_iri = annotation.concept_iri
            session.add(
                Passage(
                    content=annotation.passage,
                    start=annotation.start,
                    end=annotation.end,
                    annotation_version_id=snapshot_id,
                    term_id=term.id,
                )
            )

        await session.commit()
        return await session.scalar(
            select(AnnotationVersion)
            .where(AnnotationVersion.id == snapshot_id)
            .options(
                selectinload(AnnotationVersion.editor),
                selectinload(AnnotationVersion.annotations).options(selectinload(Passage.term)),
            )
        )

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
