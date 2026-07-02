#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Top 20 Skill 用户反馈采集 — 从 Hacker News、GitHub Issues、Reddit 抓取真实用户讨论。

输出: data/skill-feedback.json
"""

from __future__ import print_function

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
SKILLS_PATH = os.path.join(DATA_DIR, "skills.json")
FEEDBACK_PATH = os.path.join(DATA_DIR, "skill-feedback.json")
USER_AGENT = "AIDreamingTrue-SkillFeedback/1.0"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

ECOSYSTEM_KEYWORDS = {
    "superpowers": ["superpowers", "obra/superpowers", "cursor skill"],
    "awesome-copilot": ["awesome-copilot", "copilot skill", "github copilot skill", "gh skill"],
    "anthropics-skills": ["anthropics/skills", "claude code skill", "claude skill"],
    "openai-skills": ["openai/skills", "codex skill", ".codex/skills", "codex cli skill"],
}

GENERIC_SLUGS = {
    "playwright", "brainstorming", "frontend-design", "security-review",
    "security-best-practices", "mcp-builder", "skill-creator", "context-map",
}

SOURCE_LABELS = {
    "hacker-news": "Hacker News",
    "github": "GitHub",
    "reddit": "Reddit",
}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch_json(url, headers=None):
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if GITHUB_TOKEN and "api.github.com" in url:
        hdrs["Authorization"] = "Bearer {}".format(GITHUB_TOKEN)
    req = Request(url, headers=hdrs)
    try:
        with urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, ValueError) as exc:
        print("  [WARN] 无法抓取 {}: {}".format(url, exc), file=sys.stderr)
        return None


def normalize_text(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def skill_key(ecosystem, slug):
    return "{}/{}".format(ecosystem, slug)


def build_search_queries(skill, repo):
    slug = skill["slug"]
    display = skill.get("displayName", slug)
    ecosystem = skill.get("ecosystem", "")
    slug_spaced = slug.replace("-", " ")

    queries = [
        '"{}" "{}" skill'.format(display, ecosystem),
        '"{}" {}'.format(slug, repo.split("/")[-1]),
        '{} superpowers skill'.format(slug_spaced) if ecosystem == "superpowers" else '{} {} skill'.format(slug_spaced, ecosystem),
    ]
    return queries[:3]


def is_relevant(text, skill):
    if not text or len(text) < 30:
        return False
    lower = text.lower()
    slug = skill["slug"].lower()
    slug_spaced = slug.replace("-", " ")
    display = skill.get("displayName", "").lower()
    ecosystem = skill.get("ecosystem", "")

    has_slug = slug in lower or slug_spaced in lower
    has_display = display and display in lower
    if not has_slug and not has_display:
        return False

    if slug in GENERIC_SLUGS or len(slug) <= 12:
        eco_hits = ECOSYSTEM_KEYWORDS.get(ecosystem, [])
        if not any(kw.lower() in lower for kw in eco_hits):
            if " skill" not in lower and "skills" not in lower:
                return False
    return True


def infer_sentiment(text):
    lower = text.lower()
    positive = sum(1 for w in ["great", "love", "helpful", "recommend", "game changer", "works well", "useful", "best", "awesome", "excellent"] if w in lower)
    negative = sum(1 for w in ["useless", "doesn't work", "broken", "bad", "waste", "avoid", "problem", "issue", "bug", "disappoint"] if w in lower)
    if positive > negative:
        return "positive"
    if negative > positive:
        return "negative"
    return "neutral"


def feedback_id(source, url, author):
    raw = "{}|{}|{}".format(source, url, author)
    return re.sub(r"[^a-z0-9]+", "-", raw.lower())[:120]


def search_hacker_news(query, skill, max_hits=8):
    url = "https://hn.algolia.com/api/v1/search?{}".format(urllib.parse.urlencode({
        "query": query,
        "tags": "comment,story",
        "hitsPerPage": max_hits,
    }))
    data = fetch_json(url)
    if not data:
        return []

    results = []
    for hit in data.get("hits", []):
        text = normalize_text(hit.get("comment_text") or hit.get("story_text") or hit.get("title") or "")
        if not is_relevant(text, skill):
            continue
        created = hit.get("created_at_i") or 0
        date_str = datetime.fromtimestamp(created, tz=timezone.utc).strftime("%Y-%m-%d") if created else ""
        item_url = "https://news.ycombinator.com/item?id={}".format(hit.get("objectID", hit.get("story_id", "")))
        author = hit.get("author") or "anonymous"
        results.append({
            "id": feedback_id("hacker-news", item_url, author),
            "source": "hacker-news",
            "sourceLabel": SOURCE_LABELS["hacker-news"],
            "author": author,
            "date": date_str,
            "text": text[:600],
            "url": item_url,
            "score": hit.get("points") or 0,
            "sentiment": infer_sentiment(text),
        })
    return results


def search_github_issues(repo, query, skill, max_hits=6):
    q = "repo:{} {} in:title,body".format(repo, query)
    url = "https://api.github.com/search/issues?{}".format(urllib.parse.urlencode({
        "q": q,
        "sort": "updated",
        "per_page": max_hits,
    }))
    data = fetch_json(url)
    if not data:
        return []

    results = []
    for item in data.get("items", []):
        if "pull_request" in item:
            continue
        text = normalize_text("{} {}".format(item.get("title", ""), item.get("body", "")))
        if not is_relevant(text, skill):
            continue
        author = (item.get("user") or {}).get("login") or "github-user"
        date_str = (item.get("created_at") or "")[:10]
        results.append({
            "id": feedback_id("github", item.get("html_url", ""), author),
            "source": "github",
            "sourceLabel": SOURCE_LABELS["github"],
            "author": author,
            "date": date_str,
            "text": text[:600],
            "url": item.get("html_url", ""),
            "score": item.get("comments", 0),
            "sentiment": infer_sentiment(text),
        })
    return results


def search_reddit(query, skill, max_hits=5):
    url = "https://www.reddit.com/search.json?{}".format(urllib.parse.urlencode({
        "q": query,
        "sort": "relevance",
        "limit": max_hits,
        "type": "link",
    }))
    data = fetch_json(url)
    if not data:
        return []

    results = []
    for child in (data.get("data") or {}).get("children", []):
        post = child.get("data") or {}
        text = normalize_text("{} {}".format(post.get("title", ""), post.get("selftext", "")))
        if not is_relevant(text, skill):
            continue
        author = post.get("author") or "reddit-user"
        permalink = "https://www.reddit.com{}".format(post.get("permalink", ""))
        date_str = datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc).strftime("%Y-%m-%d") if post.get("created_utc") else ""
        results.append({
            "id": feedback_id("reddit", permalink, author),
            "source": "reddit",
            "sourceLabel": SOURCE_LABELS["reddit"],
            "author": author,
            "date": date_str,
            "text": text[:600],
            "url": permalink,
            "score": post.get("score", 0),
            "sentiment": infer_sentiment(text),
        })
    return results


def dedupe_and_rank(comments, limit=8):
    seen = set()
    unique = []
    for c in comments:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        unique.append(c)
    unique.sort(key=lambda x: (-(x.get("score") or 0), x.get("date", "")))
    return unique[:limit]


def collect_feedback_for_skill(skill, repo):
    queries = build_search_queries(skill, repo)
    all_comments = []

    for query in queries:
        print("    HN: {}".format(query[:60]))
        all_comments.extend(search_hacker_news(query, skill))
        time.sleep(0.3)

    for query in queries[:2]:
        print("    GitHub: {} @ {}".format(query[:40], repo))
        all_comments.extend(search_github_issues(repo, query, skill))
        time.sleep(0.5)

    for query in queries[:1]:
        print("    Reddit: {}".format(query[:60]))
        all_comments.extend(search_reddit(query, skill))
        time.sleep(1.0)

    comments = dedupe_and_rank(all_comments, limit=8)
    return comments


def collect_all_feedback(dry_run=False):
    skills_data = load_json(SKILLS_PATH, default={"skills": []})
    skills = skills_data.get("skills", [])
    if not skills:
        print("未找到 skills.json 中的策展 Skill，请先运行 collect_skills.py", file=sys.stderr)
        return None

    discovery = (skills_data.get("meta") or {}).get("discovery", {})
    repo_by_ecosystem = {k: v.get("repo", "") for k, v in discovery.items()}

    feedback_by_skill = {}
    total_comments = 0

    print("采集 Top {} Skill 用户反馈...".format(len(skills)))
    for skill in skills:
        ecosystem = skill.get("ecosystem", "")
        slug = skill.get("slug", "")
        repo = repo_by_ecosystem.get(ecosystem, "")
        key = skill_key(ecosystem, slug)
        print("  → #{} {} [{}]".format(skill.get("rank", "?"), slug, ecosystem))

        if not repo:
            feedback_by_skill[key] = {
                "slug": slug,
                "ecosystem": ecosystem,
                "displayName": skill.get("displayName", slug),
                "feedbackCount": 0,
                "comments": [],
            }
            continue

        comments = collect_feedback_for_skill(skill, repo)
        total_comments += len(comments)
        feedback_by_skill[key] = {
            "slug": slug,
            "ecosystem": ecosystem,
            "displayName": skill.get("displayName", slug),
            "feedbackCount": len(comments),
            "comments": comments,
        }
        print("    找到 {} 条反馈".format(len(comments)))

    payload = {
        "meta": {
            "lastUpdated": now_iso(),
            "skillCount": len(skills),
            "totalComments": total_comments,
            "sources": ["hacker-news", "github", "reddit"],
            "note": "来自 HN / GitHub Issues / Reddit 的公开用户讨论，按相关性与热度筛选。",
        },
        "feedbackBySkill": feedback_by_skill,
    }

    if dry_run:
        print("\n[DRY-RUN] 共 {} 条反馈".format(total_comments))
        return payload

    save_json(FEEDBACK_PATH, payload)
    print("\n已写入 {}（{} 条反馈）".format(FEEDBACK_PATH, total_comments))
    return payload


def main():
    parser = argparse.ArgumentParser(description="采集 Top Skill 用户反馈")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    collect_all_feedback(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
