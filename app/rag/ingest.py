"""
Offline ingestion: crawl ONLY the allow-listed Karnataka government domains,
chunk, embed and save the index.

    python -m app.rag.ingest
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
from collections import deque
from urllib import robotparser
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.logger import get_logger, setup_logging
from app.rag.config import RagSettings
from app.rag.embeddings import GeminiEmbedder
from app.rag.vector_store import Chunk, VectorStore

logger = get_logger("awaaz_setu.rag.ingest")

SKIP_EXTENSIONS = (".exe", ".zip", ".rar", ".apk", ".jpg", ".jpeg", ".png", ".gif", ".svg",
                   ".mp3", ".mp4", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")
SKIP_URL_PARTS = ("login", "logout", "signin", "register", "captcha", "feedback", "directapply")
_INDIC = re.compile(r"[\u0900-\u0DFF]")   # Devanagari ... Sinhala blocks, includes Kannada


def indic_ratio(text: str) -> float:
    """Share of alphabetic characters that are in Indian scripts (0.0 = pure English)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if _INDIC.match(c)) / len(letters)


def should_skip_url(url: str) -> bool:
    low = url.lower().split("?")[0]
    return low.endswith(SKIP_EXTENSIONS) or any(p in url.lower() for p in SKIP_URL_PARTS)


def same_site(url: str, seed: str) -> bool:
    host = lambda u: (urlparse(u).hostname or "").lower().removeprefix("www.")
    return host(url) == host(seed)


def is_allowed_domain(url: str, allowed: tuple[str, ...]) -> bool:
    """True only for http(s) URLs whose host is an allowed domain or subdomain."""
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return False
    host = (p.hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in allowed)


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]
    chunks: list[str] = []
    cur = ""
    for p in paras:
        if len(cur) + len(p) + 1 <= max_chars:
            cur = f"{cur}\n{p}".strip()
            continue
        if cur:
            chunks.append(cur)
        cur = (cur[-overlap:] + "\n" + p).strip() if cur else p
        while len(cur) > max_chars * 2:           # one very long paragraph
            chunks.append(cur[:max_chars])
            cur = cur[max_chars - overlap:]
    if cur:
        chunks.append(cur)
    return [c for c in chunks if len(c) > 80]


def _extract(resp: httpx.Response, url: str):
    ctype = resp.headers.get("content-type", "").lower()
    if "pdf" in ctype or url.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(resp.content))
            return url.rsplit("/", 1)[-1], "\n".join((p.extract_text() or "") for p in reader.pages), []
        except Exception as exc:  # noqa: BLE001
            logger.warning("pdf skipped %s: %s", url, exc)
            return "", "", []
    if "html" not in ctype:
        return "", "", []
    soup = BeautifulSoup(resp.text, "html.parser")
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else url
    links = [urldefrag(urljoin(url, a["href"]))[0] for a in soup.find_all("a", href=True)]
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "form"]):
        tag.decompose()
    return title, soup.get_text("\n"), links


def _robots_ok(url: str, cache: dict, ua: str) -> bool:
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in cache:
        rp = robotparser.RobotFileParser()
        try:
            rp.set_url(base + "/robots.txt")
            rp.read()
            cache[base] = rp
        except Exception:  # noqa: BLE001  unreadable robots.txt -> allow
            cache[base] = None
    rp = cache[base]
    return True if rp is None else rp.can_fetch(ua, url)


def crawl(settings: RagSettings, seeds: list[str]) -> list[Chunk]:
    chunks: list[Chunk] = []
    seen_urls: set[str] = set()
    seen_hash: set[str] = set()
    robots: dict = {}
    headers = {"User-Agent": settings.user_agent}
    with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
        for seed in seeds:
            if not is_allowed_domain(seed, settings.allowed_domains):
                logger.warning("SKIP seed (domain not allowed): %s", seed)
                continue
            queue, pages = deque([(seed, 0)]), 0
            while queue and pages < settings.max_pages_per_seed:
                url, depth = queue.popleft()
                if (url in seen_urls or should_skip_url(url)
                        or not is_allowed_domain(url, settings.allowed_domains)
                        or not _robots_ok(url, robots, settings.user_agent)):
                    continue
                seen_urls.add(url)
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("fetch failed %s: %s", url, exc.__class__.__name__)
                    continue
                title, text, links = _extract(resp, url)
                text = clean_text(text)
                pages += 1
                logger.info("[%d] %s (%d chars)", pages, url, len(text))
                for c in chunk_text(text, settings.chunk_chars, settings.chunk_overlap):
                    if settings.english_only and indic_ratio(c) > 0.2:
                        continue                      # Kannada/Hindi text: not used while English-only
                    h = hashlib.md5(c.encode("utf-8")).hexdigest()
                    if h not in seen_hash:
                        seen_hash.add(h)
                        chunks.append(Chunk(text=c, url=url, title=title))
                if depth < settings.crawl_depth:
                    queue.extend(
                        (l, depth + 1) for l in links
                        if l.startswith("http")
                        and (not settings.same_host_only or same_site(l, seed))
                    )
                time.sleep(settings.crawl_delay_seconds)
    return chunks


_SOURCE_LINE = re.compile(r"\s*Source:\s*(\S+)", re.IGNORECASE)


def load_local_docs(settings: RagSettings) -> list[Chunk]:
    """
    Official text saved by the team in data/rag_docs/*.txt|*.md (for sites that only
    render in JavaScript). The FIRST line must be `Source: <URL on an allowed domain>`,
    which is the page the text was copied from and what the answer will cite.
    """
    chunks: list[Chunk] = []
    docs_dir = settings.local_docs_dir
    if not docs_dir.exists():
        return chunks
    for path in sorted(docs_dir.iterdir()):
        if path.suffix.lower() not in (".txt", ".md") or path.name.startswith(("_", "README")):
            continue
        first, _, body = path.read_text(encoding="utf-8").partition("\n")
        m = _SOURCE_LINE.match(first)
        if not m or not is_allowed_domain(m.group(1), settings.allowed_domains):
            logger.warning("SKIP %s: first line must be 'Source: <URL on an allowed Karnataka government domain>'",
                           path.name)
            continue
        for c in chunk_text(clean_text(body), settings.chunk_chars, settings.chunk_overlap):
            if settings.english_only and indic_ratio(c) > 0.2:
                continue
            chunks.append(Chunk(text=c, url=m.group(1), title=path.stem))
        logger.info("local doc %s -> %s", path.name, m.group(1))
    return chunks


def _save_chunks(path, chunks: list[Chunk]) -> None:
    path.write_text(json.dumps([c.__dict__ for c in chunks], ensure_ascii=False), encoding="utf-8")


def _load_chunks(path) -> list[Chunk]:
    return [Chunk(**c) for c in json.loads(path.read_text(encoding="utf-8"))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Karnataka-government RAG index.")
    parser.add_argument("--resume", action="store_true",
                        help="reuse the chunks from the last crawl instead of crawling again")
    parser.add_argument("--allow-partial", action="store_true",
                        help="if the embedding quota runs out, save an index from the chunks "
                             "embedded so far (finish later with --resume)")
    args = parser.parse_args()

    setup_logging("INFO")
    s = RagSettings.from_env()
    if not s.gemini_api_key:
        raise SystemExit("GEMINI_API_KEY is not set (backend/.env or environment).")
    s.index_dir.mkdir(parents=True, exist_ok=True)
    crawl_file = s.index_dir / "crawl_chunks.json"
    cache_file = s.index_dir / "embed_cache.json"

    seeds = json.loads(s.sources_file.read_text(encoding="utf-8"))["seed_urls"]
    if args.resume and crawl_file.exists():
        # keep only chunks from sites that are still seeds, so removing a seed prunes it
        seed_hosts = {(urlparse(u).hostname or "").lower().removeprefix("www.") for u in seeds}
        chunks = [c for c in _load_chunks(crawl_file)
                  if (urlparse(c.url).hostname or "").lower().removeprefix("www.") in seed_hosts]
        logger.info("Resuming with %d chunks from the last crawl (no new crawl)", len(chunks))
    else:
        chunks = crawl(s, seeds)
        if chunks:
            _save_chunks(crawl_file, chunks)

    local = load_local_docs(s)
    chunks = chunks + local
    if not chunks:
        raise SystemExit("Nothing to index. Check seed URLs, your internet, and data/rag_docs/.")
    if local:
        logger.info("Added %d chunks from local official docs", len(local))

    logger.info("%d chunks; embedding with %s ...", len(chunks), s.embed_model)
    embedder = GeminiEmbedder(s)
    texts = [c.text for c in chunks]
    try:
        vectors = embedder.embed_documents(texts, cache_path=cache_file)
    except RuntimeError as exc:
        if not args.allow_partial:
            raise
        idxs, vectors = embedder.cached_subset(texts, cache_file)
        if not idxs:
            raise
        logger.warning("%s", exc)
        logger.warning("Saving a PARTIAL index: %d of %d chunks. "
                       "Finish later with: python -m app.rag.ingest --resume", len(idxs), len(chunks))
        chunks = [chunks[i] for i in idxs]
    VectorStore(vectors, chunks).save(s.index_dir)
    logger.info("Index saved to %s (%d chunks)", s.index_dir, len(chunks))


if __name__ == "__main__":
    main()
