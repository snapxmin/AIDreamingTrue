#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function

import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import collect_best_practices as collector


class BestPracticeFilteringTest(unittest.TestCase):
    def test_rejects_generic_engineering_pr_with_cursor_word(self):
        text = (
            "[WIP] Implement a Wayland DisplayServer. This PR implements cursor "
            "handling and windowing APIs for Godot. It discusses workflow details "
            "but does not describe how to use an AI coding agent."
        )

        self.assertFalse(collector.mentions_competitor(text, "cursor", "Cursor"))
        self.assertFalse(collector.is_practice_like(text))

    def test_rejects_product_complaints_and_billing_issues(self):
        samples = [
            "Copilot auth now sets far too many requests as user consuming premium requests rapidly.",
            "Claude Code is unusable for complex engineering tasks with the Feb updates.",
            "Your Pricing Is a Wallet-Wrecking Tragedy for Kiro users.",
        ]

        for text in samples:
            self.assertFalse(collector.is_practice_like(text))

    def test_accepts_actionable_coding_agent_workflow(self):
        text = (
            "Claude Code best practices: write a plan first, keep CLAUDE.md updated "
            "with test commands, ask the coding agent to run unit tests, and review "
            "the pull request before merging."
        )

        self.assertTrue(collector.mentions_competitor(text, "claude-code", "Claude Code"))
        self.assertTrue(collector.is_practice_like(text))

    def test_requires_actionable_usage_signal_not_feature_request_only(self):
        text = (
            "Feature request: add a command line interface for Kiro Agentic AI IDE. "
            "This asks the vendor to build a new feature but gives no user workflow."
        )

        self.assertFalse(collector.is_practice_like(text))

    def test_rejects_github_issues_that_are_not_usage_guides(self):
        samples = [
            "Claude Code does not respect the XDG Base Directory specification",
            "Open Source Kiro",
        ]

        for text in samples:
            self.assertFalse(collector.is_practice_like(text))
            self.assertFalse(collector.is_github_practice_title(text))

        self.assertTrue(collector.is_github_practice_title("Claude Code workflow guide for large refactors"))

    def test_search_github_skips_pull_requests_and_keeps_usage_guides(self):
        original_fetch_json = collector.fetch_json

        def fake_fetch_json(url):
            return {
                "items": [
                    {
                        "title": "Code review workflow improvements",
                        "body": (
                            "GitHub Copilot coding agent best practices: configure "
                            "instructions and ask Copilot to run tests before review."
                        ),
                        "html_url": "https://github.com/example/repo/pull/1",
                        "pull_request": {"url": "https://api.github.com/repos/example/repo/pulls/1"},
                        "user": {"login": "pr-author"},
                        "created_at": "2026-06-01T00:00:00Z",
                        "comments": 12,
                    },
                    {
                        "title": "GitHub Copilot workflow guide for code review",
                        "body": (
                            "GitHub Copilot coding agent best practices: configure "
                            "path-specific instructions, ask Copilot to review pull requests, "
                            "and run tests before merging."
                        ),
                        "html_url": "https://github.com/example/repo/issues/2",
                        "user": {"login": "guide-author"},
                        "created_at": "2026-06-02T00:00:00Z",
                        "comments": 8,
                    },
                ]
            }

        try:
            collector.fetch_json = fake_fetch_json
            results = collector.search_github("GitHub Copilot", "github-copilot", "GitHub Copilot")
        finally:
            collector.fetch_json = original_fetch_json

        self.assertEqual(1, len(results))
        self.assertEqual("https://github.com/example/repo/issues/2", results[0]["sourceUrl"])

    def test_cursor_bare_name_requires_strong_agent_practice_context(self):
        good = "Cursor best practices for coding agent work: write project rules and run tests."
        bad = "Cursor handling in the graphics engine workflow changed during this refactor."

        self.assertTrue(collector.mentions_competitor(good, "cursor", "Cursor"))
        self.assertFalse(collector.mentions_competitor(bad, "cursor", "Cursor"))


if __name__ == "__main__":
    unittest.main()
