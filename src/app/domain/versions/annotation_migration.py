from collections.abc import Sequence

from domain.terms.models import Passage
from domain.terms.services import AnnotationService


class AnnotationMigrationService:
    """Decide which annotations carry forward to a new question revision."""

    @staticmethod
    def retain_if_offsets_match(new_question: str, annotations: Sequence[Passage]) -> list[Passage] | None:
        """Retain the complete set only while every span still matches at its old offsets.

        An empty list is a valid explicitly saved empty snapshot. ``None`` means the
        existing annotations did not map and the new revision should start without a snapshot.
        This is the current migration strategy. A future mapper can replace this method
        without changing revision creation or annotation save validation.
        """
        if not all(
            AnnotationService.span_matches(new_question, item.start, item.end, item.content)
            for item in annotations
        ):
            return None

        return [
            Passage(
                content=item.content,
                start=item.start,
                end=item.end,
                term=item.term,
            )
            for item in annotations
        ]
