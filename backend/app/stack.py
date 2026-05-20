"""Detect stacked PRs from a flat list of dashboard PRs.

Two PRs in the same repo form a parent/child link when the child's
``base_ref`` matches the parent's ``head_ref``. The transitive closure
of those links per repo is a forest of trees; every tree with two or
more nodes is a "stack" and gets reflected back onto each member as
``PR.stack`` so the template can render the same tree from any card.

The algorithm is purely structural: we deliberately don't hardcode
``main``/``master`` as the only valid stack base. The root of a stack is
whichever node's base isn't another dashboard PR's head -- typically a
default branch, but it could just as easily be a long-lived release
branch.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .model import PR, Stack, StackNode


def attach_stacks(prs: list[PR]) -> list[PR]:
    """Return PRs with ``.stack`` populated for every PR in a 2+ stack.

    Preserves input ordering. PRs that end up in a stack of size 1 (or
    that hit a cycle, see below) get ``stack=None`` so the template
    treats them as standalone cards.

    Cycle handling: a real branch can't be the base of itself, but two
    PRs could theoretically reference each other's heads if someone
    rebased mid-poll. We detect the cycle while walking each root's
    subtree and drop every PR in the connected component rather than
    looping forever or rendering a misleading partial tree.
    """
    by_repo: dict[str, list[PR]] = defaultdict(list)
    for pr in prs:
        by_repo[pr.repo].append(pr)

    stacks_by_pr_number: dict[tuple[str, int], Stack] = {}
    for repo, repo_prs in by_repo.items():
        for stack in _stacks_for_repo(repo_prs):
            for node in stack.nodes:
                stacks_by_pr_number[(repo, node.number)] = stack

    if not stacks_by_pr_number:
        return list(prs)

    return [
        pr.model_copy(update={"stack": stacks_by_pr_number.get((pr.repo, pr.number))})
        if (pr.repo, pr.number) in stacks_by_pr_number
        else pr
        for pr in prs
    ]


def _stacks_for_repo(prs: Iterable[PR]) -> list[Stack]:
    """Walk one repo's PRs and emit every stack of size >= 2."""
    head_to_pr: dict[str, PR] = {}
    for pr in prs:
        if pr.head_ref:
            head_to_pr.setdefault(pr.head_ref, pr)

    children_by_parent_head: dict[str, list[PR]] = defaultdict(list)
    for pr in prs:
        if pr.base_ref and pr.base_ref in head_to_pr:
            parent = head_to_pr[pr.base_ref]
            if parent.number == pr.number:
                # Self-loop (PR whose head and base are the same ref).
                # Treat as standalone rather than rendering a bogus stack.
                continue
            children_by_parent_head[parent.head_ref].append(pr)

    roots = [
        pr
        for pr in prs
        if not pr.base_ref or pr.base_ref not in head_to_pr
    ]

    stacks: list[Stack] = []
    for root in roots:
        nodes = _walk_tree(root, children_by_parent_head)
        if nodes is None:
            # Cycle detected somewhere in this subtree -- drop the whole
            # connected component rather than render a partial / wrong
            # tree. Members of the cycle keep stack=None.
            continue
        if len(nodes) < 2:
            continue
        stacks.append(Stack(nodes=tuple(nodes)))

    return stacks


def _walk_tree(
    root: PR, children_by_parent_head: dict[str, list[PR]]
) -> list[StackNode] | None:
    """Pre-order DFS from ``root``; returns ``None`` if a cycle is hit.

    Children of any given parent are visited in PR-number order so the
    rendered tree is stable across polls (the GraphQL response order
    happens to be ``updated_at`` desc, which would visibly flip the
    sibling order whenever one of them is touched).
    """
    nodes: list[StackNode] = []
    seen: set[int] = set()

    def visit(pr: PR, depth: int, parent_number: int | None) -> bool:
        if pr.number in seen:
            return False
        seen.add(pr.number)
        nodes.append(
            StackNode(
                number=pr.number,
                title=pr.title,
                url=pr.url,
                repo=pr.repo,
                depth=depth,
                parent_number=parent_number,
                column=pr.column,
            )
        )
        for child in sorted(
            children_by_parent_head.get(pr.head_ref, ()),
            key=lambda c: c.number,
        ):
            if not visit(child, depth + 1, pr.number):
                return False
        return True

    if not visit(root, 0, None):
        return None
    return nodes
