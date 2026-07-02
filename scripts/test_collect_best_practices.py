#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function

import unittest

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


if __name__ == "__main__":
    unittest.main()
