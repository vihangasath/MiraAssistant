"""BM25 keyword retrieval over published content chunks.

BM25 rather than embeddings: the corpus is ~30 short pages, results are
deterministic and explainable, and there is no second API dependency. Only
published documents are ever indexed, so drafts cannot leak into answers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from mira.data.content_loader import Chunk, Doc, chunk_doc

_STOP = set("a an the and or of to in on for is are do does you your we our with at by from it this that be can what how much which i me my there any".split())
# A few travel synonyms so "kids" finds the children policy and "refund" finds cancellation.
_SYNONYMS = {
    "kids": ["children", "child"], "kid": ["child", "children"], "baby": ["infant", "infants"],
    "refund": ["cancellation"], "cancel": ["cancellation"], "deposit": ["payment"], "pay": ["payment"],
    "whale": ["whales"], "whales": ["whale"], "elephants": ["elephant"], "leopards": ["leopard"],
    "ancient": ["anuradhapura", "polonnaruwa", "sigiriya", "cultural"], "train": ["railway"],
}


def tokenize(text: str) -> list[str]:
    tokens = [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP]
    expanded = list(tokens)
    for t in tokens:
        expanded.extend(_SYNONYMS.get(t, []))
    return expanded


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class ContentIndex:
    def __init__(self, docs: dict[str, Doc]):
        self.docs = {k: d for k, d in docs.items() if d.is_published}
        self.chunks: list[Chunk] = [c for d in self.docs.values() for c in chunk_doc(d)]
        corpus = [tokenize(f"{c.doc_title} {c.heading} {c.text}") for c in self.chunks]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, k: int = 6, doc_ids: list[str] | None = None, min_score: float = 0.5) -> list[Hit]:
        if not self._bm25:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        hits = [Hit(c, float(s)) for c, s in zip(self.chunks, scores)
                if s >= min_score and (doc_ids is None or c.doc_id in doc_ids)]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def doc_chunks(self, doc_id: str) -> list[Chunk]:
        return [c for c in self.chunks if c.doc_id == doc_id]

    def published_tours(self) -> list[Doc]:
        return [d for d in self.docs.values() if d.type == "tour"]
