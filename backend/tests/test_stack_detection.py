"""Unit tests for ``app.stack.attach_stacks``.

Stacks are detected per repo by chaining each PR's ``base_ref`` to
another dashboard PR's ``head_ref``. The tests cover the shapes the
poller is likely to see in production: a single chain, a root with
two siblings, a deeper chain, plus the defensive paths (cycles,
cross-repo same branch names, solo PRs).
"""
from __future__ import annotations

import unittest

from app.model import PR, Checks
from app.stack import attach_stacks


def _pr(
    number: int,
    *,
    head: str,
    base: str,
    repo: str = "acme/web",
    title: str | None = None,
    is_draft: bool = False,
    approved: bool = False,
    checks: Checks | None = None,
    comments_human: int = 0,
    comments_bot: int = 0,
    preview_url: str | None = "https://preview.example/x",
    conflicts: int = 0,
) -> PR:
    """Tiny builder so tests can focus on the head/base relationships.

    ``approved=True`` puts ``TEST_REVIEWER`` on the approver list so
    ``pr.column_for(TEST_REVIEWER) == "approved"``; tests that don't
    care about the reviewer dimension can ignore the argument
    entirely.
    """
    return PR(
        number=number,
        title=title or f"PR {number}",
        url=f"https://github.com/{repo}/pull/{number}",
        repo=repo,
        author="me",
        is_draft=is_draft,
        checks=checks or Checks(passed=1, pending=0, failed=0),
        comments_human=comments_human,
        comments_bot=comments_bot,
        preview_url=preview_url,
        conflicts=conflicts,
        updated_at="2026-05-20T10:00:00Z",
        approver_logins=(TEST_REVIEWER,) if approved else (),
        base_ref=base,
        head_ref=head,
    )


TEST_REVIEWER = "nicoraga1"


class TwoPRChainTests(unittest.TestCase):
    def test_root_and_child_both_get_stack(self) -> None:
        root = _pr(300, head="feat/a", base="main")
        child = _pr(301, head="feat/b", base="feat/a")
        result = attach_stacks([root, child])

        by_number = {p.number: p for p in result}
        self.assertIsNotNone(by_number[300].stack)
        self.assertIsNotNone(by_number[301].stack)
        # Both PRs share the *same* Stack instance so the template can
        # render the same tree from either card.
        self.assertIs(by_number[300].stack, by_number[301].stack)

    def test_nodes_are_in_preorder_root_first(self) -> None:
        root = _pr(300, head="feat/a", base="main")
        child = _pr(301, head="feat/b", base="feat/a")
        result = attach_stacks([root, child])

        stack = result[0].stack
        assert stack is not None
        self.assertEqual([n.number for n in stack.nodes], [300, 301])
        self.assertEqual([n.depth for n in stack.nodes], [0, 1])
        self.assertEqual(stack.nodes[0].parent_number, None)
        self.assertEqual(stack.nodes[1].parent_number, 300)

    def test_preserves_input_order(self) -> None:
        root = _pr(300, head="feat/a", base="main")
        child = _pr(301, head="feat/b", base="feat/a")
        result = attach_stacks([child, root])
        self.assertEqual([p.number for p in result], [301, 300])


class SiblingTests(unittest.TestCase):
    def test_root_with_two_siblings(self) -> None:
        root = _pr(300, head="feat/a", base="main")
        first = _pr(301, head="feat/b1", base="feat/a")
        second = _pr(302, head="feat/b2", base="feat/a")
        result = attach_stacks([root, first, second])

        stacks = {id(p.stack) for p in result if p.stack is not None}
        self.assertEqual(len(stacks), 1)

        stack = result[0].stack
        assert stack is not None
        self.assertEqual([n.number for n in stack.nodes], [300, 301, 302])
        self.assertEqual([n.depth for n in stack.nodes], [0, 1, 1])
        self.assertEqual(
            [n.parent_number for n in stack.nodes], [None, 300, 300]
        )

    def test_siblings_sorted_by_pr_number(self) -> None:
        # Input order intentionally not number-ascending; output should be.
        root = _pr(300, head="feat/a", base="main")
        higher = _pr(305, head="feat/b2", base="feat/a")
        lower = _pr(301, head="feat/b1", base="feat/a")
        result = attach_stacks([root, higher, lower])

        stack = result[0].stack
        assert stack is not None
        self.assertEqual([n.number for n in stack.nodes], [300, 301, 305])


class DeepChainTests(unittest.TestCase):
    def test_three_deep_chain(self) -> None:
        root = _pr(100, head="feat/a", base="main")
        middle = _pr(101, head="feat/b", base="feat/a")
        leaf = _pr(102, head="feat/c", base="feat/b")
        result = attach_stacks([root, middle, leaf])

        stack = result[0].stack
        assert stack is not None
        self.assertEqual([n.number for n in stack.nodes], [100, 101, 102])
        self.assertEqual([n.depth for n in stack.nodes], [0, 1, 2])
        self.assertEqual(
            [n.parent_number for n in stack.nodes], [None, 100, 101]
        )


class SoloPRTests(unittest.TestCase):
    def test_single_pr_has_no_stack(self) -> None:
        solo = _pr(900, head="feat/x", base="main")
        result = attach_stacks([solo])
        self.assertIsNone(result[0].stack)

    def test_unrelated_prs_have_no_stack(self) -> None:
        # Two PRs in the same repo but neither merges into the other's head.
        a = _pr(900, head="feat/x", base="main")
        b = _pr(901, head="feat/y", base="main")
        result = attach_stacks([a, b])
        self.assertTrue(all(p.stack is None for p in result))


class CrossRepoTests(unittest.TestCase):
    def test_same_branch_names_in_different_repos_dont_link(self) -> None:
        # If two repos both have ``feat/a`` and ``feat/b``, they shouldn't
        # cross-pollinate. Stack detection is strictly per-repo.
        a = _pr(1, head="feat/a", base="main", repo="acme/web")
        b = _pr(2, head="feat/b", base="feat/a", repo="acme/web")
        c = _pr(3, head="feat/a", base="main", repo="acme/api")
        d = _pr(4, head="feat/b", base="feat/a", repo="acme/api")

        result = attach_stacks([a, b, c, d])
        by_number = {p.number: p for p in result}

        # acme/web pair links to each other, acme/api pair links to each
        # other -- two distinct stacks, no cross-repo nodes.
        web_stack = by_number[1].stack
        api_stack = by_number[3].stack
        assert web_stack is not None and api_stack is not None
        self.assertIsNot(web_stack, api_stack)
        self.assertEqual({n.repo for n in web_stack.nodes}, {"acme/web"})
        self.assertEqual({n.repo for n in api_stack.nodes}, {"acme/api"})


class CycleTests(unittest.TestCase):
    def test_two_pr_cycle_yields_no_stack(self) -> None:
        # Pathological: A merges into B's head and B merges into A's
        # head. Neither has a base outside the set of heads, so neither
        # becomes a root -- both end up unstamped rather than looping.
        a = _pr(1, head="feat/a", base="feat/b")
        b = _pr(2, head="feat/b", base="feat/a")
        result = attach_stacks([a, b])
        self.assertTrue(all(p.stack is None for p in result))

    def test_cycle_buried_in_subtree_drops_whole_component(self) -> None:
        # Root -> A -> B -> A (B points back at A). The root walk hits
        # the cycle and the entire connected component is dropped rather
        # than rendered as a partial tree.
        root = _pr(10, head="feat/root", base="main")
        a = _pr(11, head="feat/a", base="feat/root")
        b = _pr(12, head="feat/b", base="feat/a")
        # ``a`` rewritten to point its base back at b's head -> cycle.
        a_cycle = a.model_copy(update={"base_ref": "feat/b"})
        result = attach_stacks([root, a_cycle, b])
        self.assertTrue(all(p.stack is None for p in result))


class StackLayoutHintsTests(unittest.TestCase):
    """``attach_stacks`` populates the layout fields the template needs.

    The frontend collapses same-column stacks into a single indented
    group instead of repeating the inline tree on each card. The hints
    we put on each ``PR`` are what makes that pass possible without the
    frontend having to re-derive the stack on every SSE swap.
    """

    def test_same_column_stack_is_marked_co_column(self) -> None:
        root = _pr(300, head="feat/a", base="main")
        child = _pr(301, head="feat/b", base="feat/a")
        result = attach_stacks([root, child])
        by_number = {p.number: p for p in result}
        self.assertTrue(by_number[300].stack_co_column)
        self.assertTrue(by_number[301].stack_co_column)
        self.assertEqual(by_number[300].stack_depth, 0)
        self.assertEqual(by_number[301].stack_depth, 1)
        self.assertEqual(by_number[300].stack_order, 0)
        self.assertEqual(by_number[301].stack_order, 1)

    def test_split_column_stack_is_not_co_column(self) -> None:
        # Root is approved by the viewer's reviewer, child still in
        # progress -> different columns *for that viewer*.
        root = _pr(300, head="feat/a", base="main", approved=True)
        child = _pr(
            301,
            head="feat/b",
            base="feat/a",
            checks=Checks(passed=0, pending=1, failed=0),
        )
        result = attach_stacks([root, child], reviewer=TEST_REVIEWER)
        by_number = {p.number: p for p in result}
        self.assertFalse(by_number[300].stack_co_column)
        self.assertFalse(by_number[301].stack_co_column)

    def test_approval_only_splits_stack_for_the_tracking_viewer(self) -> None:
        # Same stack as ``test_split_column_stack_is_not_co_column`` --
        # but a viewer who isn't tracking the approver should see the
        # stack stay co-column (root falls back to READY instead of
        # being promoted to APPROVED).
        root = _pr(300, head="feat/a", base="main", approved=True)
        child = _pr(301, head="feat/b", base="feat/a")
        result = attach_stacks([root, child], reviewer="someone-else")
        by_number = {p.number: p for p in result}
        self.assertTrue(by_number[300].stack_co_column)
        self.assertTrue(by_number[301].stack_co_column)

    def test_solo_prs_have_default_hints(self) -> None:
        solo = _pr(900, head="feat/x", base="main")
        result = attach_stacks([solo])
        self.assertFalse(result[0].stack_co_column)
        self.assertIsNone(result[0].stack_depth)
        self.assertIsNone(result[0].stack_order)


class StackNodeShapeTests(unittest.TestCase):
    def test_node_column_reflects_pr_column_for_tracking_viewer(self) -> None:
        # Mixed columns *for the viewer tracking the approver*: root
        # is approved, child is in progress.
        root = _pr(300, head="feat/a", base="main", approved=True)
        child = _pr(
            301,
            head="feat/b",
            base="feat/a",
            checks=Checks(passed=0, pending=1, failed=0),
        )
        self.assertEqual(root.column_for(TEST_REVIEWER), "approved")
        self.assertEqual(child.column_for(TEST_REVIEWER), "progress")

        result = attach_stacks([root, child], reviewer=TEST_REVIEWER)
        stack = result[0].stack
        assert stack is not None
        cols = {n.number: n.column_for(TEST_REVIEWER) for n in stack.nodes}
        self.assertEqual(cols, {300: "approved", 301: "progress"})

    def test_node_column_falls_back_to_ready_without_reviewer(self) -> None:
        # No viewer reviewer set -> the same "approved" PR sits in the
        # READY column instead of APPROVED.
        approved = _pr(300, head="feat/a", base="main", approved=True)
        self.assertEqual(approved.column_for(None), "ready")
        self.assertEqual(approved.column_for(""), "ready")

    def test_node_carries_title_and_url(self) -> None:
        root = _pr(300, head="feat/a", base="main", title="root work")
        child = _pr(
            301, head="feat/b", base="feat/a", title="follow-up"
        )
        result = attach_stacks([root, child])
        stack = result[0].stack
        assert stack is not None
        self.assertEqual(stack.nodes[0].title, "root work")
        self.assertEqual(stack.nodes[1].title, "follow-up")
        self.assertEqual(
            stack.nodes[1].url, "https://github.com/acme/web/pull/301"
        )


if __name__ == "__main__":
    unittest.main()
