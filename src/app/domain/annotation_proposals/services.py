from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from domain.groups.models import Group
from domain.questions.models import Question
from domain.terms.models import Passage, Term
from domain.versions.models import AnnotationVersion, Version
from litestar.exceptions import HTTPException, NotFoundException
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_409_CONFLICT, HTTP_503_SERVICE_UNAVAILABLE
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.terms.dtos import AnnotationDTO

from .dtos import AnnotationProposalRequest, AnnotationProposalResponse
from .models import AnnotationProposalItem, AnnotationProposalRun
from .pipeline import generate_proposals


class AnnotationProposalService:
    @staticmethod
    async def propose(
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
        data: AnnotationProposalRequest,
        proposer_id: UUID,
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
        excluded_spans: list[tuple[int, int]] = []
        if data.exclude_annotated:
            latest_annotation_version_id = await session.scalar(
                select(AnnotationVersion.id)
                .where(AnnotationVersion.question_version_id == revision.id)
                .order_by(AnnotationVersion.version_number.desc())
                .limit(1)
            )
            if latest_annotation_version_id is not None:
                saved_passages = await session.execute(
                    select(Passage.start, Passage.end).where(
                        Passage.annotation_version_id == latest_annotation_version_id
                    )
                )
                excluded_spans = [(start, end) for start, end in saved_passages.all()]
        try:
            result = await asyncio.to_thread(
                generate_proposals,
                revision.question_string,
                glossary,
                str(question_id),
                excluded_spans=excluded_spans,
            )
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            raise HTTPException(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                detail="Annotation proposal models are unavailable. Check the backend model configuration.",
            ) from error

        if not result["candidates"]:
            return AnnotationProposalResponse(
                question_id=question_id,
                revision_id=revision.id,
                proposal_run_id=None,
                candidates=[],
                matcher=result["matcher"],
                context_matcher=result["context_matcher"],
            )

        run = AnnotationProposalRun(
            project_id=project_id,
            question_id=question_id,
            question_version_id=revision.id,
            proposer_id=proposer_id,
            matcher_metadata={
                "matcher": result["matcher"],
                "contextMatcher": result["context_matcher"],
                "excludeAnnotated": data.exclude_annotated,
            },
        )
        session.add(run)
        await session.flush()

        proposal_items = []
        for candidate in result["candidates"]:
            suggestion = candidate["suggested_term"]
            matches = candidate["matches"]
            best_score = matches[0].get("score") if matches else None
            item = AnnotationProposalItem(
                run_id=run.id,
                text=candidate["text"],
                start=candidate["start"],
                end=candidate["end"],
                lemma=candidate["lemma"],
                extraction_rule=candidate["rule"],
                match_status=candidate["match_status"],
                match_score=float(best_score) if best_score is not None else None,
                suggested_term=suggestion["content"],
                suggested_term_id=UUID(suggestion["id"]) if suggestion.get("id") else None,
                suggested_term_is_new=suggestion["isNew"],
                token_data=candidate["tokens"],
            )
            session.add(item)
            proposal_items.append(item)
        await session.flush()

        return_data = [
            {**candidate, "proposal_id": item.id}
            for candidate, item in zip(result["candidates"], proposal_items, strict=True)
        ]
        run_id = run.id
        revision_id = revision.id
        await session.commit()
        return AnnotationProposalResponse(
            question_id=question_id,
            revision_id=revision_id,
            proposal_run_id=run_id,
            candidates=return_data,
            matcher=result["matcher"],
            context_matcher=result["context_matcher"],
        )

    @staticmethod
    async def record_review(
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
        run_id: UUID,
        revision_id: UUID,
        annotations: list[AnnotationDTO],
        reviewer_id: UUID,
    ) -> AnnotationProposalRun:
        run = await session.scalar(
            select(AnnotationProposalRun)
            .where(
                AnnotationProposalRun.id == run_id,
                AnnotationProposalRun.project_id == project_id,
                AnnotationProposalRun.question_id == question_id,
                AnnotationProposalRun.question_version_id == revision_id,
            )
            .options(selectinload(AnnotationProposalRun.proposals))
        )
        if run is None:
            raise NotFoundException()
        if run.reviewed_at is not None:
            raise HTTPException(status_code=HTTP_409_CONFLICT, detail="This proposal set has already been reviewed.")

        revision = await session.get(Version, revision_id)
        question = await session.scalar(
            select(Question)
            .join(Group, Group.id == Question.group_id)
            .where(Question.id == question_id, Group.project_id == project_id)
        )
        if revision is None or question is None:
            raise NotFoundException()
        if revision.version_number != question.version_number and annotations:
            raise HTTPException(status_code=HTTP_409_CONFLICT, detail="The question changed after proposals were generated.")

        from domain.terms.services import AnnotationService

        for annotation in annotations:
            if not AnnotationService.span_matches(
                revision.question_string, annotation.start, annotation.end, annotation.passage
            ):
                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail="Annotation span must match the selected text in the question.",
                )

        decisions = []
        for proposal in run.proposals:
            accepted = next(
                (
                    annotation
                    for annotation in annotations
                    if annotation.start == proposal.start
                    and annotation.end == proposal.end
                    and annotation.passage == proposal.text
                ),
                None,
            )
            decisions.append(
                (
                    proposal,
                    accepted is not None,
                    accepted.term == proposal.suggested_term if accepted is not None else False,
                    accepted.term if accepted is not None else None,
                )
            )

        for proposal, span_accepted, term_accepted, final_term in decisions:
            proposal.span_accepted = span_accepted
            proposal.term_accepted = term_accepted
            proposal.final_term = final_term
        run.reviewed_at = datetime.now(UTC)
        run.reviewer_id = reviewer_id
        return run

    @staticmethod
    async def review(
        session: AsyncSession,
        project_id: UUID,
        question_id: UUID,
        run_id: UUID,
        reject: bool,
        reviewer_id: UUID,
    ) -> None:
        revision_id = await session.scalar(
            select(AnnotationProposalRun.question_version_id).where(
                AnnotationProposalRun.id == run_id,
                AnnotationProposalRun.project_id == project_id,
                AnnotationProposalRun.question_id == question_id,
            )
        )
        if revision_id is None:
            raise NotFoundException()
        annotations: list[AnnotationDTO] = []
        if not reject:
            latest_annotation_version_id = await session.scalar(
                select(AnnotationVersion.id)
                .where(AnnotationVersion.question_version_id == revision_id)
                .order_by(AnnotationVersion.version_number.desc())
                .limit(1)
            )
            if latest_annotation_version_id is not None:
                passages = await session.scalars(
                    select(Passage)
                    .where(Passage.annotation_version_id == latest_annotation_version_id)
                    .options(selectinload(Passage.term))
                )
                annotations = [
                    AnnotationDTO(
                        passage=passage.content,
                        term=passage.term.content,
                        start=passage.start,
                        end=passage.end,
                    )
                    for passage in passages.all()
                ]
        await AnnotationProposalService.record_review(
            session, project_id, question_id, run_id, revision_id, annotations, reviewer_id
        )
        await session.commit()

    @staticmethod
    async def _load_glossary(session: AsyncSession, project_id: UUID) -> dict:
        terms = (
            await session.scalars(select(Term).where(Term.project_id == project_id).order_by(Term.content))
        ).all()
        glossary = {
            term.id: {
                "id": str(term.id),
                "label": term.content,
                "definition": term.definition,
                "concept_iri": term.concept_iri,
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
