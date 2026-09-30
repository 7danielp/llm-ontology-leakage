"""Start runs, grids and aggregations of the three leakage detection methods from the terminal"""

# uv run main.py run --method {ts-guessing,guided-prompting,min-k} --ontology-preset {FOAF,SCHEMA,DCTERMS,...} --task {taxonomy,domain,range,property} --model <maki or openai model> --format {plain,prefix,full} [--mock] [--sample N --seed S --results-dir <dir>]
# uv run main.py grid --method {...} --ontology-preset {...} [--tasks ...] [--models ...] [--formats ...] [--mock] [--sample N --seed S --results-dir <dir>]
# uv run main.py aggregate --method {ts-guessing,guided-prompting,min-k} [--results-dir <dir>]
# {...} required choices, [...] optional (grid runs everything if left out)

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from llm_ontology_leakage.ts_guessing.aggregate import aggregate_ts
from llm_ontology_leakage.guided_prompting.aggregate import aggregate_gp
from llm_ontology_leakage.guided_prompting.runner import run_guided_prompting
from llm_ontology_leakage.min_k.aggregate import aggregate_mink
from llm_ontology_leakage.min_k.runner import MINK_TASKS, run_min_k
from llm_ontology_leakage.core.config import (
    FULL_RUN_DIR,
    GRID_FORMATS,
    GRID_MODELS,
    GRID_TASKS,
    ONTOLOGY_PRESETS,
    OPENAI_MODELS,
    RunConfig,
    build_run_config,
    web_tool_calls,
)
from llm_ontology_leakage.core.clients import (
    CompletionClient,
    MakiClient,
    MockClient,
    OpenAIClient,
)
from llm_ontology_leakage.core.tasks import TASKS
from llm_ontology_leakage.core.runs import run_grid
from llm_ontology_leakage.ts_guessing.runner import run_ts_guessing

METHODS = ("ts-guessing", "guided-prompting", "min-k")
AGGREGATORS = {"ts-guessing": aggregate_ts, "guided-prompting": aggregate_gp, "min-k": aggregate_mink}
RUNNERS = {"ts-guessing": run_ts_guessing, "guided-prompting": run_guided_prompting, "min-k": run_min_k}


def _add_common_args(p: argparse.ArgumentParser) -> None:
    """Attach the arguments shared by "run" and "grid" (method, preset, limit, sample, seed, results dir, mock)"""
    p.add_argument(
        "--method",
        choices=list(METHODS),
        required=True,
        help="leakage-detection method to run",
    )
    p.add_argument(
        "--ontology-preset",
        choices=list(ONTOLOGY_PRESETS),
        required=True,
        help="preconfigured ontology (source, namespace, prefixes, examples, tasks)",
    )
    p.add_argument("--limit", type=int, help="only run the first N questions (TS, GP) or blocks (Min-K) per run")
    p.add_argument("--sample", type=int, help="random sample of at most N questions per task (TS, GP), identical across formats and methods, only for web search runs")
    p.add_argument("--seed", type=int, default=42, help="seed of the sample draw (default 42)")
    p.add_argument("--results-dir", type=Path)
    p.add_argument("--mock", action="store_true", help="use a canned-answer client (no MAKI or OpenAI)")


def _base_config(
    args: argparse.Namespace, *, task: str, model: str, id_format: str,
) -> RunConfig:
    """Build the RunConfig"""
    cfg = build_run_config(
        args.ontology_preset, task=task, model=model, id_format=id_format
    )
    if args.limit is not None:
        cfg.limit = args.limit
    if args.sample is not None:
        cfg.sample = args.sample
        cfg.seed = args.seed
    if args.results_dir is not None:
        cfg.results_dir = args.results_dir
    return cfg


def _select_client(models: list[str], *, mock: bool, method: str, parser) -> CompletionClient:
    """Return the requested client (OPENAI_MODELS to OpenAI, everything else to MAKI)"""
    if mock:
        return MockClient()
    openai_requested = [m for m in models if m in OPENAI_MODELS]
    if openai_requested and method == "min-k":
        parser.error(
            f"min-k cannot run on OpenAI models ({', '.join(openai_requested)}): "
            "the OpenAI API returns logprobs for output tokens only, echo mode "
            "for prompt tokens does not exist. Use MAKI models for min-k."
        )
    if openai_requested and len(openai_requested) < len(models):
        parser.error(
            "OpenAI and MAKI models cannot share one run; start them separately."
        )
    return OpenAIClient() if openai_requested else MakiClient()


def _print_aggregation(results_dir: Path, method: str) -> None:
    """Run the method's aggregator and print the written files"""
    for name, path in AGGREGATORS[method](results_dir).items():
        print(f"  {name}: {path}")


def main() -> None:
    """Parse the command line and start the chosen subcommand"""
    load_dotenv()  # MAKI_BASE_URL, MAKI_API_KEY and OPENAI_API_KEY from .env

    parser = argparse.ArgumentParser(description="LLM leakage detection on ontology axioms")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="one run (task x model x format)")
    run_p.add_argument("--task", choices=list(TASKS), required=True, help="the axiom task for this run")
    run_p.add_argument("--model", required=True, help="model name (MAKI or OpenAI)")
    run_p.add_argument("--format", choices=list(GRID_FORMATS), required=True)
    _add_common_args(run_p)

    grid_p = sub.add_parser("grid", help="all combinations (tasks x models x formats)")
    grid_p.add_argument("--tasks", nargs="+", choices=list(TASKS), default=None)
    grid_p.add_argument("--models", nargs="+", default=GRID_MODELS)
    grid_p.add_argument("--formats", nargs="+", choices=list(GRID_FORMATS), default=list(GRID_FORMATS))
    _add_common_args(grid_p)

    agg_p = sub.add_parser("aggregate", help="rebuild the method's CSV/LaTeX tables (no API calls)")
    agg_p.add_argument("--results-dir", type=Path, default=FULL_RUN_DIR)
    agg_p.add_argument("--method", choices=list(METHODS), required=True)

    args = parser.parse_args()

    if args.command == "aggregate":
        _print_aggregation(args.results_dir, args.method)
        return

    if args.sample is not None:
        if args.sample < 1:
            parser.error("--sample must be at least 1")
        if args.limit is not None:
            parser.error("--sample and --limit exclude each other")
        if args.method == "min-k":
            parser.error("min-k scores whole axiom blocks, it has no sampling")
        if args.results_dir is None:
            parser.error("--sample needs --results-dir, a sampled run has the same directory name as the full run")
        models = [args.model] if args.command == "run" else list(args.models)
        if not all(web_tool_calls(m) for m in models):
            parser.error("--sample is only for web search runs (a +web model)")

    if args.command == "run":  # run: task, model and format come straight from the arguments
        cfg = _base_config(
            args, task=args.task, model=args.model, id_format=args.format,
        )
    else:  # grid: the first value of each list only seeds the config, run_grid replaces them per combination
        cfg = _base_config(
            args, task=(args.tasks or GRID_TASKS)[0], model=args.models[0], id_format=args.formats[0],
        )

    requested_models = [args.model] if args.command == "run" else list(args.models)
    client: CompletionClient = _select_client(
        requested_models, mock=args.mock, method=args.method, parser=parser
    )

    # run (call the runner once)
    if args.command == "run":
        if args.method == "min-k" and args.task not in MINK_TASKS:
            parser.error("min-k has no property task: its axioms are the domain triples")
        result = RUNNERS[args.method](cfg, client)
        # TS reports its metrics, GP its gap, Min-K its block summary after the run
        summary = result["summary"]
        print(json.dumps(summary.get("metrics") or summary.get("gap") or summary, indent=2))
        print(f"Results written to {result['run_dir']}/")
        return

    # grid (run_grid calls the runner per combination, then aggregates)
    tasks = args.tasks if args.tasks is not None else list(GRID_TASKS)
    if args.method == "min-k":
        tasks = [t for t in tasks if t in MINK_TASKS]
        if not tasks:
            parser.error("none of the requested tasks exists in min-k (it has no property task)")
    run_grid(cfg, client, tasks, args.models, args.formats, runner=RUNNERS[args.method])
    print("\nGrid complete. Aggregation:")
    _print_aggregation(cfg.results_dir, args.method)


if __name__ == "__main__":
    main()
