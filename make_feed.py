r"""*Module to generate PG RSS feed.*
"""

import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Union

import arrow  # type: ignore
import attr
import bs4  # type: ignore
import requests_cache

import requests as rq
from bs4 import BeautifulSoup as BSoup
from feedgen.feed import FeedGenerator  # type: ignore
from packaging.utils import canonicalize_version

BASE_URL: str = "https://podcast.app"
PG_URL: str = "https://podcast.app/paul-graham-essays-audio-p1755465/?limit=250&offset=0"

FORMAT: str = "%(asctime)-15s  [%(levelname)-10s]  %(message)s"
logging.basicConfig(format=FORMAT, stream=sys.stdout, level=logging.INFO)

logger: logging.Logger = logging.getLogger()

FEED_PATH: str = "feed/pg.rss"


@attr.s(slots=True)
class Info:
    id: str = attr.ib(validator=attr.validators.instance_of(str))
    title: str = attr.ib(validator=attr.validators.instance_of(str))
    description: str = attr.ib(validator=attr.validators.instance_of(str))
    enc: str = attr.ib(validator=attr.validators.instance_of(str))
    date: datetime = attr.ib(validator=attr.validators.instance_of(datetime))


def resp_report(resp: rq.Response) -> str:
    """Supply combo of status code and reason."""
    return f"{resp.status_code} {resp.reason}"


def get_release_pages() -> rq.Response:
    """Retrieve the release page contents."""
    return rq.get(PG_URL)
    

def gen_entries(resp: rq.Response) -> Iterable[bs4.Tag]:
    """Yield the release entries from the stable downloads page."""
    soup = BSoup(resp.text, "html.parser")
    yield from (li for li in soup("tr") if li.find("span", class_="ep-published"))


def extract_info(li: bs4.Tag) -> Info:
    """Produce an Info instance with relevant info for the provided stable release."""
    #logger.debug(f"got li={li.contents})")
    
    id = li.find("a", class_="ep-item").get('href')
    logger.debug(f"id= {id}")

    title = li.find("h3", class_="ep-row-title").string
    logger.debug(f"title= {title}")

    description = li.find("p", class_="ep-row-desc").string
    logger.debug(f"desc= {description}")
    
    date_str = li.find("span", class_="ep-published").string.strip()
    date = datetime.strptime(date_str, '%m.%d.%Y').replace(tzinfo=timezone.utc)
    logger.debug(f"date= {date}")

    enc = li.find("a", class_="play-btn").get('data-mp3')
    logger.debug(f"enclosure= {enc}")

    return Info(id=id, title=title, description=description, enc=enc, date=date)


def create_base_feed() -> FeedGenerator:
    """Create feed generator and configure feed-level data."""
    fg = FeedGenerator()

    fg.id(PG_URL)
    fg.title("Paul Graham Essays (Audio)")
#    fg.author({"name": "App Champ", "email": "app.engine.champ@gmail.com"})
    fg.link(
        href="https://podcast.app/paul-graham-essays-audio-p1755465/",
        rel="self",
    )
    fg.logo(
        "https://podcast-api-images.s3.amazonaws.com/podcast_logo_1755465_300x300.jpg"
    )
    fg.language("en")
    fg.description("PG Podcast")
    fg.docs("http://www.rssboard.org/rss-specification")

    return fg


def add_feed_item(fg: FeedGenerator, info: Info) -> None:
    """Add the item information from 'info' in a new entry on 'fg'."""
    fe = fg.add_entry(order="append")

    fe.id(f"{BASE_URL+info.id}")
    fe.title(desc := f"{info.title}")
    fe.link({"href": info.enc, "rel": "alternate"})
    fe.author(fg.author())
    fe.content(info.description)
    fe.updated(arrow.utcnow().datetime)
    fe.published(info.date)

    logger.debug(f"Feed entry created for {fe.title()}")


def write_feed(fg: FeedGenerator) -> None:
    """Write the completed RSS feed to disk."""
    fg.rss_file(str(FEED_PATH), pretty=True)


def main():
    """Execute data collection and feed generation."""
    # init the global cache
    requests_cache.install_cache('pg_cache')

    # get the main page
    resp_pg = get_release_pages()

    if not resp_pg.ok:
        logger.critical(
            f"PG pages download failed: {resp_report(resp_pg)}"
        )
        return 1

    logger.info("Download pages retrieved.")

    fg = create_base_feed()
    logger.info("Base feed generator created")

    [
        add_feed_item(fg, extract_info(li))
        for li in gen_entries(resp_pg)
    ]
    logger.info("Articles added to feed")

    write_feed(fg)
    logger.info("Feed written to disk")


if __name__ == "__main__":
    sys.exit(main())
