"""Runner for the Min-K% method (Shi et al.)"""

import json
from dataclasses import asdict, dataclass
from typing import Any

from rdflib import URIRef

from ..core.config import RunConfig, TaskName
from ..core.clients import CompletionClient
from ..core.ontology import axiom_pairs, load_graph, render_identifier
from ..core.runs import run_dir_for, write_meta

METHOD = "min-k"
BLOCK_SIZE = 10  # axioms per block, single axioms are too short for the method
PRIMARY_RATIO = 0.2  # suggested in reference paper (Shi et al.)
RATIO_SWEEP = (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6)  # additional ratios

# no property task, its axioms are the domain triples (the blocks would be identical)
MINK_TASKS: tuple[TaskName, ...] = ("taxonomy", "domain", "range")


@dataclass
class Block:
    """A block of axiom lines of one task"""

    block_id: str
    task: str
    axiom_lines: list[str]


@dataclass
class MinKRecord:
    """One record per block"""

    key: str  # = block_id
    task: str
    n_axioms: int
    text: str
    tokens: list[str]
    token_logprobs: list[float | None]
    scores: dict[str, float]


def min_k_score(logprobs: list[float | None], ratio: float) -> float:
    """Return Min-K% score (mean of the int(n * ratio) lowest log probs)"""
    values = [x for x in logprobs if x is not None]
    k = max(1, int(len(values) * ratio))
    lowest = sorted(values)[:k]
    return sum(lowest) / len(lowest)


def score_sweep(logprobs: list[float | None]) -> dict[str, float]:
    """Compute Min-K% score for every ratio in the sweep"""
    return {f"min_{int(r * 100)}": min_k_score(logprobs, r) for r in RATIO_SWEEP}


def build_blocks(graph, cfg: RunConfig) -> list[Block]:
    """Build the blocks for the run's task"""
    pred_label = render_identifier(
        URIRef(cfg.axiom_predicates[cfg.task]), graph, "prefix"
    )
    triples = sorted(axiom_pairs(graph, cfg, cfg.task))
    lines = [
        f"{render_identifier(s, graph, cfg.id_format)} {pred_label} "
        f"{render_identifier(o, graph, cfg.id_format)}"
        for s, o in triples
    ]
    return [
        Block(
            block_id=f"{cfg.task}-{i // BLOCK_SIZE:03d}",
            task=cfg.task,
            axiom_lines=lines[i : i + BLOCK_SIZE],
        )
        for i in range(0, len(lines), BLOCK_SIZE)
    ]


def _summarize_mink(records: list[dict], cfg: RunConfig) -> dict:
    """Summarize one run (scores recomputed from the logged log probs)"""
    primary = [min_k_score(r["token_logprobs"], PRIMARY_RATIO) for r in records]
    return {
        "method": METHOD,
        "task": cfg.task,
        "model": cfg.model,
        "id_format": cfg.id_format,
        "ontology_source": cfg.ontology_source,
        "ontology_name": cfg.ontology_name,
        "block_size": BLOCK_SIZE,
        "n_blocks": len(records),
        "n_axioms": sum(r["n_axioms"] for r in records),
        f"mean_min_{int(PRIMARY_RATIO * 100)}": sum(primary) / len(primary),
    }


def run_min_k(cfg: RunConfig, client: CompletionClient) -> dict[str, Any]:
    """Execute Min-K run"""
    graph = load_graph(cfg.ontology_source, cfg.prefix_map)
    # build the axiom blocks from the graph
    blocks = build_blocks(graph, cfg)
    if not blocks:
        raise ValueError(
            f"0 axiom blocks extracted from {cfg.ontology_name} for task {cfg.task}! "
            "Check the preset's axiom_predicates mapping."
        )
    if cfg.limit is not None:
        blocks = blocks[: cfg.limit]

    run_dir = run_dir_for(cfg, "MK")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").unlink(missing_ok=True)  # drop a stale summary so a crashed rerun cannot look complete
    write_meta(run_dir, cfg, method=METHOD, client_name=type(client).__name__)

    records: list[dict] = []
    with open(run_dir / "records.jsonl", "w", encoding="utf-8") as records_file:
        for i, block in enumerate(blocks, start=1):
            text = "\n".join(block.axiom_lines)
            # one echo call per block
            tlp = client.token_logprobs(text, model=cfg.model)
            record = MinKRecord(
                key=block.block_id,
                task=block.task,
                n_axioms=len(block.axiom_lines),
                text=text,
                tokens=tlp.tokens,
                token_logprobs=tlp.logprobs,
                scores=score_sweep(tlp.logprobs),
            )
            records.append(asdict(record))
            records_file.write(json.dumps(records[-1], ensure_ascii=False) + "\n")
            primary = record.scores[f"min_{int(PRIMARY_RATIO * 100)}"]
            print(f"  [{i}/{len(blocks)}] {block.block_id}: min-{int(PRIMARY_RATIO*100)}% = {primary:.3f}")

    summary = _summarize_mink(records, cfg)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {"summary": summary, "run_dir": str(run_dir)}
