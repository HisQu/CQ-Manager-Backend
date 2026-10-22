from collections.abc import Sequence
from difflib import SequenceMatcher

from domain.terms.models import Passage
from domain.terms.services import AnnotationService


def _utf16_units(text: str) -> list[bytes]:
    """Split text into UTF-16 code units so diff offsets match the stored span offsets."""
    encoded = text.encode("utf-16-le", errors="surrogatepass")
    return [encoded[index : index + 2] for index in range(0, len(encoded), 2)]


class AnnotationMigrationService:
    """Decide which annotations carry forward to a new question revision."""

    @staticmethod
    def retain_matching(
        old_question: str, new_question: str, annotations: Sequence[Passage]
    ) -> list[Passage] | None:
        """Carry forward every annotation whose span survives the edit unchanged.

        The old and new texts are diffed; a span is kept, at its shifted offsets, when it lies
        entirely inside an unchanged region and still matches its content there. Spans touching
        an edited region are dropped. An empty list is a valid explicitly saved empty snapshot.
        ``None`` means none of the existing annotations mapped and the new revision should start
        without a snapshot.
        """
        matcher = SequenceMatcher(
            None, _utf16_units(old_question), _utf16_units(new_question), autojunk=False
        )
        unchanged_blocks = [
            (old_start, old_end, new_start - old_start)
            for tag, old_start, old_end, new_start, _ in matcher.get_opcodes()
            if tag == "equal"
        ]

        retained = []
        for item in annotations:
            shift = next(
                (
                    block_shift
                    for old_start, old_end, block_shift in unchanged_blocks
                    if old_start <= item.start and item.end <= old_end
                ),
                None,
            )
            if shift is None:
                continue
            start, end = item.start + shift, item.end + shift
            if AnnotationService.span_matches(new_question, start, end, item.content):
                retained.append(Passage(content=item.content, start=start, end=end, term=item.term))

        if annotations and not retained:
            return None
        return retained
