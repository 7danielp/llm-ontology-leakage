"""Specification of the four tasks (taxonomy, domain, range, property)"""

from dataclasses import dataclass
from typing import Callable, Literal

from rdflib import Graph

from .config import RunConfig, TaskName
from .ontology import (
    TaskItem,
    extract_domain_items,
    extract_property_items,
    extract_range_items,
    extract_taxonomy_items,
)


# "any_of" counts one hit among the gold(s) (single-answer tasks)
# "exact_set" requires the full set to be equal (property task)
MatchMode = Literal["any_of", "exact_set"]

_SINGLE_CLASS_REPLY = "Reply with the class identifier only, in exactly this format: {example}"


@dataclass(frozen=True)
class TaskSpec:
    """Description of a task"""

    name: str
    reply_clause: str
    match: MatchMode
    list_valued: bool  # true when a list of answers is expected (property task)
    default_max_tokens: int
    extract: Callable[[Graph, RunConfig], list[TaskItem]]  # task items extractor from ontology.py


TASKS: dict[TaskName, TaskSpec] = {
    "taxonomy": TaskSpec(
        name="taxonomy",
        reply_clause=_SINGLE_CLASS_REPLY,
        match="any_of",
        list_valued=False,
        default_max_tokens=64,
        extract=extract_taxonomy_items,
    ),
    "domain": TaskSpec(
        name="domain",
        reply_clause=_SINGLE_CLASS_REPLY,
        match="any_of",
        list_valued=False,
        default_max_tokens=64,
        extract=extract_domain_items,
    ),
    "range": TaskSpec(
        name="range",
        reply_clause=_SINGLE_CLASS_REPLY,
        match="any_of",
        list_valued=False,
        default_max_tokens=64,
        extract=extract_range_items,
    ),
    "property": TaskSpec(
        name="property",
        reply_clause="Reply with the property identifiers only, comma-separated, in exactly this format: {example}",
        match="exact_set",
        list_valued=True,
        default_max_tokens=4096,  # covers the largest gold set (schema.org CreativeWork, 111 properties)
        extract=extract_property_items,
    ),
}

