"""Helpers for uniform result tables for all three methods"""

# Result rows are reported per segment (all records, gold inside the ontology namespace, gold external)
SEGMENTS = ("all", "gold_in_ns", "gold_external")


def ordered(values: set[str], canonical: list[str]) -> list[str]:
    """Sort values in canonical order"""
    return [v for v in canonical if v in values] + sorted(values - set(canonical))


def model_label(model: str, run: str) -> str:
    """Label of a run in the tables: the model, plus sample-web or sample-reference for sampled runs (distinguish from full runs)"""
    return model if run == "full" else f"{model} {run}"


def with_run_column(fieldnames: list[str], rows: list[dict]) -> list[str]:
    """The "run" column only in the tables of a sampled results dir, to distinguish sample-web and sample-reference runs"""
    if all(r["run"] == "full" for r in rows):
        return [f for f in fieldnames if f != "run"]
    return fieldnames


def fmt_cell(value: float | None, digits: int = 4) -> str:
    """Format a value with a fixed number of digits"""
    return "" if value is None else f"{value:.{digits}f}"


def latex_matrix(
    tasks: list[str], models: list[str], formats: list[str], cells: dict[tuple[str, str, str], float | None]
) -> str:
    """Build LaTeX table (ontology/task rows, model x format columns)"""

    def esc(s: str) -> str:
        """Escape LaTeX special characters in labels"""
        return s.replace("&", "\\&").replace("%", "\\%").replace("#", "\\#").replace("_", "\\_")

    span = len(formats)
    lines = [
        "\\begin{tabular}{l" + "c" * (span * len(models)) + "}",
        "\\toprule",
        " & "
        + " & ".join(f"\\multicolumn{{{span}}}{{c}}{{{esc(m)}}}" for m in models)
        + " \\\\",
        " ".join(
            f"\\cmidrule(lr){{{2 + i * span}-{1 + (i + 1) * span}}}" for i in range(len(models))
        ),
        "Ontology/Task & " + " & ".join(esc(f) for _ in models for f in formats) + " \\\\",
        "\\midrule",
    ]
    for task in tasks:
        row = [esc(task)]
        for model in models:
            for fmt in formats:
                value = cells.get((task, model, fmt))
                row.append("--" if value is None else f"{value:.2f}")
        lines.append(" & ".join(row) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lines) + "\n"
