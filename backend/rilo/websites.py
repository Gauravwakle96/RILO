"""Bounded robots-aware website capture without executing page scripts."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from .network import fetch, public_url
from .storage import now


class ReadableHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.links: list[str] = []
        self.title: list[str] = []
        self.hidden = 0
        self.in_title = False
        self.in_head = False
        self.published: str | None = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "head":
            self.in_head = True
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden += 1
        if tag == "title":
            self.in_title = True
        if tag == "a" and values.get("href"):
            self.links.append(values["href"])
        if tag == "meta" and values.get("property", values.get("name")) in {
            "article:published_time",
            "date",
            "datePublished",
        }:
            self.published = values.get("content")

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if not self.hidden and not self.in_title and not self.in_head and data.strip():
            self.parts.append(data.strip())


async def crawl(url: str, max_pages: int = 3, max_depth: int = 1) -> tuple[list[dict], dict]:
    scheme, host, _ = public_url(url)
    robots_url = f"{scheme}://{host}/robots.txt"
    robots_response = await fetch(robots_url, limit=256000, allowed_host=host)
    robots = RobotFileParser()
    if robots_response["status"] == 200:
        robots.parse(robots_response["body"].decode("utf-8", errors="replace").splitlines())
    elif robots_response["status"] in {404, 410}:
        robots.parse([])
    else:
        raise ValueError("Could not confirm website access rules from robots.txt.")
    queue = [(url, 0)]
    seen: set[str] = set()
    sources: list[dict] = []
    skipped = []
    while queue and len(sources) < max_pages and len(seen) < max_pages * 4:
        current, depth = queue.pop(0)
        current = urldefrag(current)[0]
        if current in seen:
            continue
        seen.add(current)
        if not robots.can_fetch("Rilo", current):
            skipped.append({"url": current, "reason": "robots.txt disallows retrieval"})
            continue
        response = await fetch(
            current,
            allowed_host=host,
            url_guard=lambda destination: robots.can_fetch("Rilo", destination),
        )
        if not robots.can_fetch("Rilo", response["url"]):
            raise ValueError("Redirected page is disallowed by robots.txt.")
        if response["status"] != 200:
            skipped.append({"url": current, "reason": f"HTTP {response['status']}"})
            continue
        content_type = next(
            (v for k, v in response["headers"].items() if k.lower() == "content-type"), ""
        )
        if "text/html" not in content_type and "text/plain" not in content_type:
            skipped.append({"url": current, "reason": "Unsupported content type"})
            continue
        parser = ReadableHTML()
        parser.feed(response["body"].decode("utf-8", errors="replace"))
        content = "\n".join(parser.parts)[:200000]
        if content:
            sources.append(
                {
                    "reference": response["url"],
                    "title": "".join(parser.title).strip() or response["url"],
                    "type": "website",
                    "published_at": parser.published,
                    "retrieved_at": now(),
                    "content": content,
                    "dns_policy": response.get("dns_policy"),
                }
            )
        else:
            skipped.append(
                {"url": current, "reason": "No readable page body; only metadata or scripts"}
            )
        if depth < max_depth:
            for link in parser.links[:200]:
                destination = urljoin(response["url"], link)
                if urlsplit(destination).hostname == host and destination not in seen:
                    queue.append((destination, depth + 1))
    if not sources:
        raise ValueError(
            "No readable page body could be captured within the access and crawl limits. "
            "The site may require JavaScript or restrict access. Rilo does not run page scripts. "
            "Use a directly readable article URL, paste the page text in Chat, or use Search with Tavily if configured. "
            "Neither agent was started."
        )
    return sources, {
        "website": url,
        "max_pages": max_pages,
        "max_depth": max_depth,
        "allowed_domains": [host],
        "skipped": skipped,
        "limitations": [
            "Page scripts were not executed; client-rendered content may be absent.",
            "Publication dates are publisher metadata, not independently verified.",
            "Crawl is bounded and does not establish whole-site coverage.",
        ],
    }
