from __future__ import annotations

import asyncio
from uuid import UUID

from domain.groups.models import Group
from domain.questions.models import Question
from domain.terms.models import Passage, Term
from domain.versions.models import AnnotationVersion, Version
from litestar.exceptions import HTTPException, NotFoundException
from litestar.status_codes import HTTP_409_CONFLICT, HTTP_503_SERVICE_UNAVAILABLE
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .dtos import AnnotationProposalRequest, AnnotationProposalResponse
from .pipeline import generate_proposals


class AnnotationProposalService:
    @staticmethod
    async def propose(
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
        data: AnnotationProposalRequest,
    ) -> AnnotationProposalResponse:
        question = await session.scalar(
            select(Question)
            .join(Group, Group.id == Question.group_id)
            .where(Question.id == question_id, Group.project_id == project_id)
            .options(selectinload(Question.versions))
        )
        if question is None:
            raise NotFoundException()
        revision = next((item for item in question.versions if item.id == data.revision_id), None)
        if revision is None:
            raise NotFoundException()
        if revision.version_number != question.version_number:
            raise HTTPException(
                status_code=HTTP_409_CONFLICT,
                detail="Only the latest CQ revision can receive annotation proposals.",
            )

        glossary = await AnnotationProposalService._load_glossary(session, project_id)
        try:
            result = await asyncio.to_thread(
                generate_proposals,
                data.text,
                glossary,
                str(question_id),
            )
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            raise HTTPException(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                detail="Annotation proposal models are unavailable. Check the backend model configuration.",
            ) from error

        return AnnotationProposalResponse(
            question_id=question_id,
            revision_id=revision.id,
            candidates=result["candidates"],
            matcher=result["matcher"],
            context_matcher=result["context_matcher"],
        )

    @staticmethod
    async def _load_glossary(session: AsyncSession, project_id: UUID) -> dict:
        terms = (
            await session.scalars(select(Term).where(Term.project_id == project_id).order_by(Term.content))
        ).all()
        glossary = {
            term.id: {
                "id": str(term.id),
                "label": term.content,
                "normalized_label": "",
                "annotations": [],
            }
            for term in terms
        }

        latest_annotation_versions = (
            select(
                AnnotationVersion.question_version_id.label("question_version_id"),
                func.max(AnnotationVersion.version_number).label("version_number"),
            )
            .group_by(AnnotationVersion.question_version_id)
            .subquery()
        )
        statement = (
            select(
                Passage.term_id,
                Passage.content,
                Passage.start,
                Passage.end,
                Question.id,
                Version.question_string,
            )
            .join(Term, Term.id == Passage.term_id)
            .join(AnnotationVersion, AnnotationVersion.id == Passage.annotation_version_id)
            .join(
                latest_annotation_versions,
                (latest_annotation_versions.c.question_version_id == AnnotationVersion.question_version_id)
                & (latest_annotation_versions.c.version_number == AnnotationVersion.version_number),
            )
            .join(Version, Version.id == AnnotationVersion.question_version_id)
            .join(Question, Question.id == Version.question_id)
            .join(Group, Group.id == Question.group_id)
            .where(
                Term.project_id == project_id,
                Group.project_id == project_id,
                Version.version_number == Question.version_number,
            )
        )
        for term_id, content, start, end, reference_question_id, question_text in (await session.execute(statement)).all():
            term = glossary.get(term_id)
            if term is not None:
                term["annotations"].append(
                    {
                        "text": content,
                        "normalized_text": "",
                        "start": start,
                        "end": end,
                        "question_id": str(reference_question_id),
                        "question": question_text,
                    }
                )

        # The matcher owns the normalization rule; this keeps ORM access independent of pipeline internals.
        from .lexical_matcher import normalize_for_match

        for term in glossary.values():
            term["normalized_label"] = normalize_for_match(term["label"])
            for annotation in term["annotations"]:
                annotation["normalized_text"] = normalize_for_match(annotation["text"])
        return {"project": str(project_id), "terms": list(glossary.values())}
