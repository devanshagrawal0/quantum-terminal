"""Public crowd text: Telegram, Reddit, 4chan, StockTwits. No keys anywhere.

Everything here returns the same record shape and nothing more:

    source      telegram | reddit | 4chan | stocktwits
    channel     which channel, subreddit, board or symbol
    post_id     that platform's own id, so re-polling cannot duplicate a post
    publish_ts  what the platform CLAIMS, and it is often wrong or missing
    fetch_ts    when our request returned. This is the one to trust.
    author, text, url

Deliberately absent: any sentiment score, and any guess at which coin a post is
about. Both are real decisions that belong upstream, and both are the documented
way this kind of pipeline fools itself - a sentiment number that mostly tracks
price, and a ticker match that thinks "ME" and "W" are mentions of tokens.

Store the words. Decide what they mean somewhere you can audit.
"""
from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}


def now_ms() -> int:
    return int(time.time() * 1000)


# One limiter per HOST, not one global pause. Reddit's unauthenticated quota is
# far tighter than Telegram's or 4chan's, and a single global delay either
# crawls for everyone or gets 429s from Reddit - it did exactly that: the first
# subreddit succeeded and the next five were refused.
_MIN_GAP = {"www.reddit.com": 14.0, "old.reddit.com": 14.0,
            "api.stocktwits.com": 1.0, "t.me": 0.5, "a.4cdn.org": 1.0}
_last_hit: Dict[str, float] = {}


def _throttle(host: str) -> None:
    gap = _MIN_GAP.get(host, 0.4)
    wait = gap - (time.time() - _last_hit.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.time()


def _get(url: str, timeout: float = 20.0, tries: int = 3) -> bytes:
    host = urllib.parse.urlparse(url).netloc
    last = None
    for attempt in range(tries):
        _throttle(host)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 429:
                # Honour the server's own instruction when it gives one.
                retry_after = exc.headers.get("Retry-After")
                delay = float(retry_after) if (retry_after or "").isdigit() else 5.0 * (attempt + 1)
                _last_hit[host] = time.time() + delay
                time.sleep(min(delay, 30.0))
                continue
            raise
        except Exception as exc:
            last = exc
            time.sleep(2.0 * (attempt + 1))
    raise last


def _clean(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


# ------------------------------------------------------------------ telegram


class _TgParser(HTMLParser):
    """Pulls messages out of a t.me/s/<channel> page.

    An HTML parser rather than a regex over the markup: Telegram nests links,
    bold and emoji inside the message body, and a regex that looks right on
    today's page silently truncates tomorrow's.

    Messages are keyed by their data-post id and finalised when the NEXT message
    starts (or at the end of the page), because the <time> tag comes after the
    text block - closing the record when the text ended left every publish time
    null.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.posts: Dict[str, Dict[str, Any]] = {}
        self._id: Optional[str] = None
        self._in_text = False
        self._text_depth = 0
        self._buf: List[str] = []

    def _finish_text(self) -> None:
        if self._id and self._buf:
            rec = self.posts.setdefault(self._id, {})
            joined = " ".join(x.strip() for x in self._buf if x.strip())
            rec["text"] = (rec.get("text", "") + " " + joined).strip()
        self._buf = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        if "tgme_widget_message" in cls and a.get("data-post"):
            self._finish_text()
            self._id = a["data-post"]
            self.posts.setdefault(self._id, {})
        if "tgme_widget_message_text" in cls and self._id:
            self._in_text = True
            self._text_depth = 0
            self._buf = []
        elif self._in_text:
            self._text_depth += 1
        # The message footer carries the publish time, after the body.
        if tag == "time" and self._id and a.get("datetime"):
            self.posts.setdefault(self._id, {})["publish_ts"] = a["datetime"]

    def handle_data(self, data):
        if self._in_text:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if self._in_text:
            if self._text_depth == 0:
                self._in_text = False
                self._finish_text()
            else:
                self._text_depth -= 1

    def close(self):
        super().close()
        self._finish_text()


def telegram(channel: str, timeout: float = 20.0) -> List[Dict[str, Any]]:
    """A public channel's recent posts. No account, no bot token, no API key -
    t.me/s/<channel> is the channel's own public web preview."""
    raw = _get(f"https://t.me/s/{channel}", timeout).decode("utf-8", "ignore")
    p = _TgParser()
    p.feed(raw)
    p.close()
    fetched = now_ms()
    out = []
    for pid, post in p.posts.items():
        text = (post.get("text") or "").strip()
        if not text:
            continue
        out.append({"source": "telegram", "channel": channel, "post_id": pid,
                    "publish_ts": post.get("publish_ts"), "fetch_ts": fetched,
                    "author": channel, "text": text[:4000],
                    "url": f"https://t.me/{pid}"})
    return out


# -------------------------------------------------------------------- reddit


def reddit(subreddit: str, timeout: float = 20.0) -> List[Dict[str, Any]]:
    """New posts via RSS. Reddit's .json endpoint returns 403 without OAuth,
    but the Atom feed is still open."""
    raw = _get(f"https://www.reddit.com/r/{subreddit}/new/.rss", timeout)
    root = ET.fromstring(raw)
    ns = "{http://www.w3.org/2005/Atom}"
    fetched = now_ms()
    out = []
    for e in root.iter(ns + "entry"):
        link = e.find(ns + "link")
        author = e.find(ns + "author/" + ns + "name")
        out.append({
            "source": "reddit", "channel": subreddit,
            "post_id": (e.findtext(ns + "id") or "").strip(),
            "publish_ts": (e.findtext(ns + "published")
                           or e.findtext(ns + "updated") or "").strip(),
            "fetch_ts": fetched,
            "author": author.text if author is not None else None,
            "text": ((e.findtext(ns + "title") or "").strip() + "\n"
                     + _clean(e.findtext(ns + "content") or ""))[:4000],
            "url": link.get("href") if link is not None else None,
        })
    return out


# --------------------------------------------------------------------- 4chan


def fourchan(board: str = "biz", timeout: float = 20.0) -> List[Dict[str, Any]]:
    """Thread subjects and opening posts from a board catalog. Retail froth in
    its rawest form; treat accordingly."""
    data = json.loads(_get(f"https://a.4cdn.org/{board}/catalog.json", timeout))
    fetched = now_ms()
    out = []
    for page in data:
        for t in page.get("threads", []):
            text = " ".join(x for x in (_clean(t.get("sub", "")),
                                        _clean(t.get("com", ""))) if x)
            if not text:
                continue
            out.append({
                "source": "4chan", "channel": board,
                "post_id": str(t.get("no")),
                "publish_ts": t.get("time"), "fetch_ts": fetched,
                "author": None, "text": text[:4000],
                "url": f"https://boards.4chan.org/{board}/thread/{t.get('no')}",
                "replies": t.get("replies"),
            })
    return out


# ---------------------------------------------------------------- stocktwits


def stocktwits(symbol: str = "BTC.X", timeout: float = 20.0) -> List[Dict[str, Any]]:
    """Messages for one symbol. StockTwits users label their own posts Bullish
    or Bearish - a stated position, not a score we invented, so it is kept."""
    data = json.loads(_get(
        f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json", timeout))
    fetched = now_ms()
    out = []
    for m in data.get("messages", []):
        ent = (m.get("entities") or {}).get("sentiment") or {}
        user = m.get("user") or {}
        out.append({
            "source": "stocktwits", "channel": symbol,
            "post_id": str(m.get("id")), "publish_ts": m.get("created_at"),
            "fetch_ts": fetched, "author": user.get("username"),
            "text": (m.get("body") or "")[:4000],
            "url": f"https://stocktwits.com/message/{m.get('id')}",
            "stated_sentiment": ent.get("basic"),
            "author_followers": user.get("followers"),
        })
    return out


FETCHERS = {"telegram": telegram, "reddit": reddit,
            "4chan": fourchan, "stocktwits": stocktwits}
