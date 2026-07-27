"""
chunker.py
----------
Parses the DSM-5-TR Disorder Compendium PDF into hierarchy-aware chunks:

    PDF -> pages -> disorder blocks -> section chunks -> (oversized) sub-chunks

Design (confirmed against the actual PDF structure):

- Section II (disorders 1-165) headings:
    Diagnostic Criteria, Diagnostic Features, Associated Features, Prevalence,
    Development and Course, Risk and Prognostic Factors, Differential Diagnosis,
    Comorbidity, Functional Consequences

- Section III (disorders 166-173, "Alternative Model for Personality Disorders")
  headings:
    Overview, Proposed Diagnostic Criteria

- Disorder #169 ("General Criteria for Personality Disorder") is a CONCEPT page,
  not an actual disorder -> tagged document_type="concept".

Each chunk's embedded text is prefixed with "<Disorder Name> - <Section Name>:"
so the embedding captures which disorder/section it belongs to, since the
embedding model never sees metadata separately.
"""

import re
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

import pdfplumber

try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_ENC.encode(text))
except ImportError:
    # Fallback if tiktoken isn't installed: rough word-based approximation
    def count_tokens(text: str) -> int:
        return int(len(text.split()) * 1.3)


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

SECTION_II_HEADINGS = [
    "Diagnostic Criteria",
    "Diagnostic Features",
    "Associated Features",
    "Prevalence",
    "Development and Course",
    "Risk and Prognostic Factors",
    "Differential Diagnosis",
    "Comorbidity",
    "Functional Consequences",
]

SECTION_III_HEADINGS = [
    "Overview",
    "Proposed Diagnostic Criteria",
]

ALL_HEADINGS = set(SECTION_II_HEADINGS) | set(SECTION_III_HEADINGS)

CONCEPT_PAGE_NAMES = set()

SECTION_III_MARKER_RE = re.compile(
    r"SECTION\s+III\s*[—\-–]\s*ALTERNATIVE\s+MODEL\s+FOR\s+PERSONALITY\s+DISORDERS",
    re.IGNORECASE,
)

# Matches a disorder header line, e.g. "1. Acute Stress Disorder"
DISORDER_HEADER_RE = re.compile(
    r"^(\d{1,3})\.\s+(.+?)\s*$",
    re.MULTILINE,
)

MAX_CHUNK_TOKENS = 300
OVERLAP_TOKENS = 50


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class Chunk:
    chunk_id: str
    disorder_id: int
    disorder_name: str
    dsm_section: str          # "II" or "III"
    document_type: str        # "disorder" or "concept"
    chapter: str              # human-readable chapter label
    section_name: str         # e.g. "Prevalence"
    chunk_index: int          # 0 unless split from an oversized section
    page_number: int
    text: str                 # final text to embed (prefixed)


# --------------------------------------------------------------------------
# Step 1: Extract text page-by-page, tracking page boundaries
# --------------------------------------------------------------------------

def load_pages(pdf_path: str):
    """Returns list of (page_number, page_text)."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append((i, text))
    return pages


def build_full_text(pages):
    """
    Joins all page texts into one string and returns:
      full_text, offsets
    where offsets is a sorted list of (start_char_offset, page_number)
    used to map any character position back to its page number.
    """
    parts = []
    offsets = []
    cursor = 0
    for page_num, text in pages:
        offsets.append((cursor, page_num))
        parts.append(text)
        cursor += len(text) + 1  # +1 for the join newline
    full_text = "\n".join(parts)
    return full_text, offsets


def page_for_offset(offset, offsets):
    """Binary-search-free linear lookup (page count is small: 148)."""
    page_num = offsets[0][1]
    for start, pg in offsets:
        if start <= offset:
            page_num = pg
        else:
            break
    return page_num


# --------------------------------------------------------------------------
# Step 2: Detect disorder boundaries (with false-positive filtering)
# --------------------------------------------------------------------------

def find_disorder_headers(full_text: str):
    """
    Finds real disorder header lines, filtering out inline numbered-list
    false positives (e.g. "1. Identity: ..." inside Diagnostic Criteria).

    A real header's next non-blank line must be one of the known section
    headings (Section II or Section III vocabulary).
    """
    lines = full_text.split("\n")
    # Precompute char offset of the start of each line
    line_offsets = []
    cursor = 0
    for line in lines:
        line_offsets.append(cursor)
        cursor += len(line) + 1

    headers = []
    header_line_re = re.compile(r"^(\d{1,3})\.\s+(.+?)\s*$")
    MAX_TITLE_WRAP_LINES = 3  # disorder titles can wrap across a couple of lines

    for idx, line in enumerate(lines):
        m = header_line_re.match(line.strip())
        if not m:
            continue

        # Disorder titles can wrap onto the next 1-2 lines before the first
        # section heading appears. Walk forward, treating non-heading,
        # non-blank lines as title continuations, until we hit a known
        # heading (real header) or run out of lookahead budget (false
        # positive, e.g. an inline numbered list item like "1. Identity:").
        name_parts = [m.group(2).strip()]
        lookahead_ok = False
        j = idx + 1
        wraps_used = 0
        while j < len(lines) and wraps_used < MAX_TITLE_WRAP_LINES:
            nxt = lines[j].strip()
            if not nxt:
                j += 1
                continue
            if nxt in ALL_HEADINGS:
                lookahead_ok = True
                break
            # treat as a title continuation line (short lines only, to avoid
            # swallowing real paragraph text from a false-positive match)
            if len(nxt.split()) <= 6:
                name_parts.append(nxt)
                wraps_used += 1
                j += 1
                continue
            break  # long non-heading line -> not a valid header, bail out

        if lookahead_ok:
            headers.append({
                "disorder_id": int(m.group(1)),
                "disorder_name": " ".join(name_parts).strip(),
                "offset": line_offsets[idx],
                "line_idx": idx,
            })

    return headers


# --------------------------------------------------------------------------
# Step 3: Split full text into disorder blocks
# --------------------------------------------------------------------------

def build_disorder_blocks(full_text: str, headers):
    marker_match = SECTION_III_MARKER_RE.search(full_text)
    section3_start = marker_match.start() if marker_match else len(full_text) + 1

    blocks = []
    for i, h in enumerate(headers):
        start = h["offset"]
        end = headers[i + 1]["offset"] if i + 1 < len(headers) else len(full_text)
        block_text = full_text[start:end]

        dsm_section = "III" if start >= section3_start else "II"
        document_type = (
            "concept" if h["disorder_name"] in CONCEPT_PAGE_NAMES else "disorder"
        )

        blocks.append({
            "disorder_id": h["disorder_id"],
            "disorder_name": h["disorder_name"],
            "dsm_section": dsm_section,
            "document_type": document_type,
            "start_offset": start,
            "text": block_text,
        })
    return blocks


# --------------------------------------------------------------------------
# Step 4: Extract section-level chunks from within a disorder block
# --------------------------------------------------------------------------

def extract_sections(block, offsets):
    heading_vocab = (
        SECTION_II_HEADINGS if block["dsm_section"] == "II" else SECTION_III_HEADINGS
    )

    text = block["text"]
    lines = text.split("\n")

    # locate heading line indices within this block
    heading_positions = []  # (line_idx, heading_name, char_offset_within_block)
    cursor = 0
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped in heading_vocab:
            heading_positions.append((idx, stripped, cursor))
        cursor += len(line) + 1

    sections = []
    for i, (line_idx, heading, char_off) in enumerate(heading_positions):
        content_start_line = line_idx + 1
        content_end_line = (
            heading_positions[i + 1][0] if i + 1 < len(heading_positions) else len(lines)
        )
        content = "\n".join(lines[content_start_line:content_end_line]).strip()
        if not content:
            continue

        abs_offset = block["start_offset"] + char_off
        page_num = page_for_offset(abs_offset, offsets)

        sections.append({
            "section_name": heading,
            "content": content,
            "page_number": page_num,
        })

    return sections


# --------------------------------------------------------------------------
# Step 5: Split oversized sections while preserving prefix/context
# --------------------------------------------------------------------------

def split_oversized(text: str, max_tokens=MAX_CHUNK_TOKENS, overlap_tokens=OVERLAP_TOKENS):
    """
    Paragraph-first, sentence-fallback splitter. Returns list of text parts.
    Never splits mid-sentence.
    """
    if count_tokens(text) <= max_tokens:
        return [text]

    # Split into sentences (simple, safe for this clinical-prose text)
    sentences = re.split(r"(?<=[.!?])\s+", text)

    parts = []
    current = []
    current_tokens = 0

    for sent in sentences:
        sent_tokens = count_tokens(sent)
        if current_tokens + sent_tokens > max_tokens and current:
            parts.append(" ".join(current))
            # start next chunk with overlap: keep trailing sentences
            overlap = []
            overlap_count = 0
            for s in reversed(current):
                t = count_tokens(s)
                if overlap_count + t > overlap_tokens:
                    break
                overlap.insert(0, s)
                overlap_count += t
            current = overlap
            current_tokens = overlap_count

        current.append(sent)
        current_tokens += sent_tokens

    if current:
        parts.append(" ".join(current))

    return parts


# --------------------------------------------------------------------------
# Step 6: Orchestrate full pipeline -> list[Chunk]
# --------------------------------------------------------------------------

def chunk_pdf(pdf_path: str):
    pages = load_pages(pdf_path)
    full_text, offsets = build_full_text(pages)
    headers = find_disorder_headers(full_text)
    blocks = build_disorder_blocks(full_text, headers)

    chapter_label = {
        "II": "Section II",
        "III": "Section III (Alternative Model for Personality Disorders)",
    }

    all_chunks = []
    for block in blocks:
        sections = extract_sections(block, offsets)

        for sec in sections:
            slug = re.sub(r"[^a-z0-9]+", "_", sec["section_name"].lower()).strip("_")
            parts = split_oversized(sec["content"])

            for idx, part_text in enumerate(parts):
                prefix = f"{block['disorder_name']} — {sec['section_name']}: "
                final_text = prefix + part_text

                chunk = Chunk(
                    chunk_id=f"{block['disorder_id']}_{slug}_{idx}",
                    disorder_id=block["disorder_id"],
                    disorder_name=block["disorder_name"],
                    dsm_section=block["dsm_section"],
                    document_type=block["document_type"],
                    chapter=chapter_label[block["dsm_section"]],
                    section_name=sec["section_name"],
                    chunk_index=idx,
                    page_number=sec["page_number"],
                    text=final_text,
                )
                all_chunks.append(chunk)

    return blocks, all_chunks


# --------------------------------------------------------------------------
# CLI entry point (for testing this stage standalone)
# --------------------------------------------------------------------------

if __name__ == "__main__":
    PDF_PATH = str(Path(__file__).resolve().parent.parent / "data" / "DSM_5_TR_Disorder_Compendium.pdf")
    OUT_PATH = str(Path(__file__).resolve().parent.parent / "data" / "chunks.json")

    blocks, chunks = chunk_pdf(PDF_PATH)

    print(f"Disorders detected: {len(blocks)} (expected 173)")
    print(f"Total chunks: {len(chunks)}")

    missing_ids = set(range(1, 174)) - {b["disorder_id"] for b in blocks}
    if missing_ids:
        print(f"WARNING - missing disorder IDs: {sorted(missing_ids)}")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump([asdict(c) for c in chunks], f, ensure_ascii=False, indent=2)

    print(f"Chunks written to {OUT_PATH}")