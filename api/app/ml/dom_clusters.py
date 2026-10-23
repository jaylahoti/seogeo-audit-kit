"""Template detection, signal 2: page structure.

Two views of each page, each compared with Jaccard distance (estimated by MinHash):

  * tag paths  — the shallow DOM skeleton ("body>main>section>h2"), depth 6, no class names.
                 Class names and deep paths vary with data (more photos → more paths), so
                 they make same-template pages look different.
  * headings   — the h1–h3 outline with the page's own entity name and numbers removed:
                 "Reviews of 25 Lincoln Avenue" → "reviews of". Programmatic templates
                 generate headings from a pattern, so this is a strong template signal.

The page distance is the mean of the two. HDBSCAN clusters the distance matrix, close
clusters are merged, and the result is reconciled with the URL patterns from signal 1:

  * split — one URL pattern whose pages fall into clearly different layouts
  * merge — sibling URL patterns in the same section that share one layout

Tuned on real pages: same-template pairs scored 0.16–0.45, different templates 0.59–0.77.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from datasketch import MinHash
from selectolax.lexbor import LexborHTMLParser as HTMLParser
from sklearn.cluster import HDBSCAN
from sklearn.manifold import TSNE

from app.ml.url_patterns import Template

SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "path", "iframe", "-text", "-comment"}
MAX_DEPTH = 6
MAX_HEADINGS = 40
NUM_PERM = 128
# Split a URL pattern only if each layout holds at least this share of its sampled pages.
SPLIT_MIN_SHARE = 0.25
# Clusters closer than this (mean combined distance) are the same layout.
SAME_LAYOUT_DISTANCE = 0.52

RE_WORD = re.compile(r"[a-z0-9#'-]+")


@dataclass
class Fingerprint:
    paths: set[str] = field(default_factory=set)
    headings: set[str] = field(default_factory=set)


def _tag_paths(body) -> set[str]:
    shingles: set[str] = set()
    stack = [(body, "body", 0)]
    while stack:
        node, path, depth = stack.pop()
        shingles.add(path)
        if depth >= MAX_DEPTH:
            continue
        child = node.child
        while child is not None:
            if child.tag and child.tag not in SKIP_TAGS:
                stack.append((child, f"{path}>{child.tag}", depth + 1))
            child = child.next
    return shingles


def heading_skeleton(tree) -> set[str]:
    heads = [n.text(strip=True).lower() for n in tree.css("h1, h2, h3")][:MAX_HEADINGS]
    if not heads:
        return set()
    entity = set(RE_WORD.findall(heads[0]))  # the page's own name, from its first heading
    out = {"<h1>"}
    for text in heads[1:]:
        words = ["#" if any(c.isdigit() for c in w) else w for w in RE_WORD.findall(text) if w not in entity]
        if words:
            out.add(" ".join(words)[:50])
    return out


def fingerprint(html: str) -> Fingerprint:
    tree = HTMLParser(html)
    if tree.body is None:
        return Fingerprint()
    return Fingerprint(paths=_tag_paths(tree.body), headings=heading_skeleton(tree))


def minhash(shingles: set[str]) -> MinHash:
    m = MinHash(num_perm=NUM_PERM, seed=7)
    for s in shingles:
        m.update(s.encode())
    return m


@dataclass
class LayoutResult:
    labels: list[int]  # HDBSCAN label per page, -1 = noise
    coords: list[tuple[float, float]] | None  # 2D map (t-SNE) for the ML Lab
    distances: np.ndarray
    cluster_distances: dict | None = None  # "a-b" -> mean Jaccard distance between layouts


def cluster_layouts(fingerprints: list[Fingerprint]) -> LayoutResult:
    n = len(fingerprints)
    if n < 3:
        return LayoutResult(labels=[0] * n, coords=None, distances=np.zeros((n, n)), cluster_distances={})
    paths = [minhash(f.paths) for f in fingerprints]
    heads = [minhash(f.headings) if f.headings else None for f in fingerprints]
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d_path = 1.0 - paths[i].jaccard(paths[j])
            if heads[i] is not None and heads[j] is not None:
                d = (d_path + 1.0 - heads[i].jaccard(heads[j])) / 2
            else:
                d = d_path
            dist[i, j] = dist[j, i] = d
    raw = HDBSCAN(
        metric="precomputed", min_cluster_size=3, min_samples=2, allow_single_cluster=True,
        copy=True,
    ).fit_predict(dist)
    labels, cluster_dist = _merge_close_clusters([int(x) for x in raw], dist)
    coords = None
    if n >= 6:
        tsne = TSNE(
            n_components=2, metric="precomputed", init="random",
            perplexity=float(min(30, max(2, (n - 1) // 3))), random_state=0,
        )
        xy = tsne.fit_transform(dist)
        # Normalize to 0..100 for plotting.
        xy = (xy - xy.min(axis=0)) / np.maximum(np.ptp(xy, axis=0), 1e-9) * 100
        coords = [(round(float(x), 2), round(float(y), 2)) for x, y in xy]
    return LayoutResult(labels=labels, coords=coords, distances=dist, cluster_distances=cluster_dist)


def _mean_between(dist: np.ndarray, a: list[int], b: list[int]) -> float:
    return float(dist[np.ix_(a, b)].mean())


def _merge_close_clusters(labels: list[int], dist: np.ndarray) -> tuple[list[int], dict]:
    """Average-linkage merge of HDBSCAN clusters closer than SAME_LAYOUT_DISTANCE."""
    members: dict[int, list[int]] = {}
    for i, lab in enumerate(labels):
        if lab >= 0:
            members.setdefault(lab, []).append(i)
    while len(members) > 1:
        keys = sorted(members)
        best = min(
            ((_mean_between(dist, members[a], members[b]), a, b) for i, a in enumerate(keys) for b in keys[i + 1 :]),
            key=lambda t: t[0],
        )
        d, a, b = best
        if d >= SAME_LAYOUT_DISTANCE:
            break
        members[a].extend(members.pop(b))
    # Relabel 0..k-1, biggest first, and report distances between the final layouts.
    order = sorted(members, key=lambda k: -len(members[k]))
    remap = {old: new for new, old in enumerate(order)}
    out = [remap.get(lab, -1) if lab >= 0 else -1 for lab in labels]
    for old, idxs in members.items():
        for i in idxs:
            out[i] = remap[old]
    final = {remap[k]: v for k, v in members.items()}
    cdist = {
        f"{a}-{b}": round(_mean_between(dist, final[a], final[b]), 3)
        for a in sorted(final) for b in sorted(final) if a < b
    }
    return out, cdist


# --- reconciling layouts with URL patterns ----------------------------------

@dataclass
class Sampled:
    template: int  # index into the URL-template list
    url: str
    label: int


def _segs(pattern: str) -> list[str]:
    return pattern.strip("/").split("/")


def _unify(patterns: list[str]) -> str:
    parts = [_segs(p) for p in patterns]
    out = []
    for column in zip(*parts, strict=True):
        out.append(column[0] if len(set(column)) == 1 else "{slug}")
    return "/" + "/".join(out)


def reconcile(templates: list[Template], samples: list[Sampled]) -> list[Template]:
    by_t: dict[int, list[Sampled]] = {}
    for s in samples:
        by_t.setdefault(s.template, []).append(s)

    # 1. Split URL patterns that hide several layouts.
    split_out: list[Template] = []
    for ti, t in enumerate(templates):
        ss = [s for s in by_t.get(ti, []) if s.label >= 0]
        counts = Counter(s.label for s in ss)
        big = [lab for lab, c in counts.items() if c >= 2 and c / max(1, len(ss)) >= SPLIT_MIN_SHARE]
        if len(big) < 2 or t.pattern == "/{static}":
            t.layout = counts.most_common(1)[0][0] if counts else None
            split_out.append(t)
            continue
        sampled_by_label = {lab: [s.url for s in ss if s.label == lab] for lab in big}
        sampled_urls = {s.url for s in by_t[ti]}
        unsampled = [u for u in t.urls if u.loc not in sampled_urls]
        total_big = sum(counts[lab] for lab in big)
        cursor = 0
        for k, lab in enumerate(sorted(big, key=lambda lab: -counts[lab])):
            share = counts[lab] / total_big
            n_take = round(share * len(unsampled)) if k < len(big) - 1 else len(unsampled) - cursor
            mine = set(sampled_by_label[lab])
            if k == 0:
                # Noise and minor-layout samples stay with the biggest layout, not dropped.
                big_urls = {u for urls_ in sampled_by_label.values() for u in urls_}
                mine |= sampled_urls - big_urls
            urls = [u for u in t.urls if u.loc in mine] + unsampled[cursor : cursor + n_take]
            cursor += n_take
            variant = Template(pattern=t.pattern, urls=urls, has_query=t.has_query)
            variant.layout = lab
            variant.variant = k + 1
            split_out.append(variant)

    # 2. Merge same-section, same-depth patterns that share a dominant layout.
    def dominant(t: Template) -> int | None:
        return t.layout

    groups: dict[tuple, list[Template]] = {}
    for t in split_out:
        if t.layout is None or t.pattern in ("/", "/{static}") or t.variant:
            continue
        segs = _segs(t.pattern)
        groups.setdefault((segs[0], len(segs), dominant(t)), []).append(t)

    merged_ids: set[int] = set()
    result: list[Template] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        merged = Template(pattern=_unify([m.pattern for m in members]))
        merged.layout = members[0].layout
        merged.merged_from = [m.pattern for m in members]
        for m in members:
            merged.urls.extend(m.urls)
            merged.has_query = merged.has_query or m.has_query
            merged_ids.add(id(m))
        result.append(merged)
    result.extend(t for t in split_out if id(t) not in merged_ids)
    result.sort(key=lambda t: t.estimated_pages, reverse=True)
    return result
