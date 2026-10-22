import sys

sys.path.append("src/app/")

from app import app  # noqa: F401  # configures all ORM mappers
from domain.terms.models import Passage, Term
from domain.versions.annotation_migration import AnnotationMigrationService

TERM = Term(content="Pfründe")


def passage(text: str, value: str, occurrence: int = 0) -> Passage:
    """Annotate the n-th occurrence of value, using UTF-16 offsets like the frontend."""
    index = -1
    for _ in range(occurrence + 1):
        index = text.index(value, index + 1)
    start = len(text[:index].encode("utf-16-le")) // 2
    end = start + len(value.encode("utf-16-le")) // 2
    return Passage(content=value, start=start, end=end, term=TERM)


def spans(annotations: list[Passage] | None) -> list[tuple[str, int, int]] | None:
    if annotations is None:
        return None
    return [(item.content, item.start, item.end) for item in annotations]


def retain(old: str, new: str, annotations: list[Passage]) -> list[tuple[str, int, int]] | None:
    return spans(AnnotationMigrationService.retain_matching(old, new, annotations))


def test_unchanged_text_keeps_all_annotations() -> None:
    text = "Welche Pfründe erhielt der Petent?"
    annotations = [passage(text, "Pfründe"), passage(text, "Petent")]
    assert retain(text, text, annotations) == spans(annotations)


def test_insertion_before_annotation_shifts_offsets() -> None:
    old = "Welche Pfründe erhielt der Petent?"
    new = "Welche kirchlichen Pfründe erhielt der Petent?"
    assert retain(old, new, [passage(old, "Pfründe"), passage(old, "Petent")]) == spans(
        [passage(new, "Pfründe"), passage(new, "Petent")]
    )


def test_editing_annotated_word_drops_only_that_annotation() -> None:
    old = "Welche Pfründe erhielt der Petent?"
    new = "Welche Pfründe erhielt der Bittsteller?"
    assert retain(old, new, [passage(old, "Pfründe"), passage(old, "Petent")]) == spans(
        [passage(new, "Pfründe")]
    )


def test_duplicate_words_keep_their_occurrence() -> None:
    old = "Welche Pfründe und welche Pfründe?"
    new = "Welche Pfründe und welche weitere Pfründe?"
    assert retain(old, new, [passage(old, "Pfründe", occurrence=1)]) == spans(
        [passage(new, "Pfründe", occurrence=1)]
    )


def test_offsets_count_utf16_code_units() -> None:
    old = "Welche Pfründe?"
    new = "📜 Welche Pfründe?"
    assert retain(old, new, [passage(old, "Pfründe")]) == spans([passage(new, "Pfründe")])
    assert passage(new, "Pfründe").start == 10  # the emoji is two UTF-16 code units


def test_no_surviving_annotation_starts_without_snapshot() -> None:
    old = "Welche Pfründe?"
    assert retain(old, "Welche Ablässe?", [passage(old, "Pfründe")]) is None


def test_empty_snapshot_is_retained() -> None:
    assert retain("Welche Pfründe?", "Welche Ablässe?", []) == []
