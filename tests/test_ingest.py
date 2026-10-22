from bootup import config
from bootup.ingest import (Unit, chunk_file, clean_text, drop_repeated_lines, ingest_all,
                           pack_atoms, pack_slides, split_man_sections, to_atoms)

MAX_WORDS = int(config.CHUNK_TOKENS * config.WORDS_PER_TOKEN)


def test_clean_text_joins_hyphens_and_drops_page_numbers():
    out = clean_text("a virtual mem-\nory system\n12\nPage 3\nnext   line")
    assert "memory" in out
    assert "\n12\n" not in f"\n{out}\n" and "Page 3" not in out
    assert "next line" in out


def test_repeated_header_removed():
    units = [Unit(f"Course Header\nbody {i}", f"p.{i}") for i in range(5)]
    cleaned = drop_repeated_lines(units)
    assert all("Course Header" not in u.text for u in cleaned)
    assert all(f"body {i}" in u.text for i, u in enumerate(cleaned))


def test_chunks_respect_size_and_overlap():
    sentences = [f"Sentence number {i} talks about scheduling and memory today." for i in range(120)]
    atoms = to_atoms([Unit(" ".join(sentences), "p.1")])
    overlap = int(MAX_WORDS * config.OVERLAP_FRACTION)
    chunks = pack_atoms(atoms, MAX_WORDS, overlap)
    assert len(chunks) > 3
    assert all(len(text.split()) <= MAX_WORDS for text, _ in chunks)
    # consecutive chunks share at least one full sentence
    for (a, _), (b, _) in zip(chunks, chunks[1:]):
        last_sentence = a.split(". ")[-1].rstrip(".")
        assert last_sentence in b


def test_oversized_sentence_is_hard_split():
    atoms = [(["word"] * (MAX_WORDS * 2 + 10), "p.1")]
    chunks = pack_atoms(atoms, MAX_WORDS, 20)
    assert len(chunks) >= 3 and all(len(t.split()) <= MAX_WORDS for t, _ in chunks)


def test_short_slides_are_merged_long_ones_stay_alone():
    long_body = "This slide has plenty of explanatory text about the topic. " * 8
    units = [Unit(long_body, "slide 1", "Long"), Unit("tiny", "slide 2", "A"),
             Unit("small", "slide 3", "B")]
    out = pack_slides(units, MAX_WORDS, 20)
    assert [loc for _, loc in out] == ["slide 1", "slide 2-3"]


def test_man_sections_split_on_headings():
    secs = split_man_sections("NAME\n    fork - make a child\n\nSYNOPSIS\n    pid_t fork(void);\n")
    assert [t for t, _ in secs] == ["NAME", "SYNOPSIS"]


def test_ingest_all_on_corpus(corpus):
    chunks, files, skipped = ingest_all(corpus)
    assert not skipped
    types = {c.source_type for c in chunks}
    assert types == {"course", "open", "qa_bank"}
    assert len(files) == 6
    assert all(c.text.strip() and c.id and c.locator for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)


def test_pdf_cleaning_end_to_end(corpus):
    chunks = chunk_file(corpus / "course" / "paged.pdf", corpus)
    joined = " ".join(c.text for c in chunks)
    assert "Operating Systems Notes" not in joined
    assert "Page 3" not in joined
    assert "page fault" in joined


def test_slide_chunks_carry_title_and_locator(corpus):
    chunks = chunk_file(corpus / "course" / "scheduling" / "slides.pptx", corpus)
    rr = next(c for c in chunks if "Round Robin" in c.text)
    assert rr.locator.startswith("slide 1") and rr.topic == "scheduling"


def test_man_page_chunks_are_per_section(corpus):
    chunks = chunk_file(corpus / "open" / "man" / "pthread_mutex_lock.txt", corpus)
    assert {c.locator for c in chunks} == {"NAME", "SYNOPSIS", "DESCRIPTION"}


def test_qa_bank_keeps_pair_whole_with_exam_metadata(corpus):
    (c,) = chunk_file(corpus / "qa_bank" / "qa.json", corpus)
    assert "Question:" in c.text and "Answer:" in c.text
    assert (c.exam, c.year, c.topic) == ("CAT-2", "2024", "deadlocks")


def test_unreadable_file_is_reported_not_fatal(corpus):
    (corpus / "course" / "broken.pdf").write_bytes(b"not a pdf")
    _, _, skipped = ingest_all(corpus)
    assert any(f == "course/broken.pdf" for f, _ in skipped)
