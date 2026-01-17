# Built in modules
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Third party modules
import requests
from alive_progress import alive_bar
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

print("\n" * 12)
os.system("clear")


def init_link_to_link_base(init_link: str) -> str:
    # Example input: https://www.literotica.com/s/some-story-title?page=2
    # We want: some-story-title
    m = re.search(r"/s/([^/?#]+)", init_link)
    if not m:
        raise ValueError(f"Could not extract link base from: {init_link}")
    return m.group(1)


def link_base_to_link(link_base: str, page_number: int) -> str:
    return (
        f"https://literotica.com/api/3/stories/{link_base}"
        f'?params=%7B"contentPage"%3A{page_number}%7D'
    )


# ---- requests session per thread (avoids sharing a Session across threads) ----
_thread_local = threading.local()


def _get_session() -> requests.Session:
    s = getattr(_thread_local, "session", None)
    if s is not None:
        return s

    s = requests.Session()

    # Basic retries for transient network errors
    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)
    s.mount("http://", adapter)
    s.mount("https://", adapter)

    _thread_local.session = s
    return s


def get_json(link: str) -> dict:
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:53.0) Gecko/20100101 Firefox/53.0"
    }
    session = _get_session()
    resp = session.get(link, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_page_text(link_base: str, page_number: int) -> tuple[int, str]:
    j = get_json(link_base_to_link(link_base, page_number))
    return page_number, j["pageText"]


def get_story(link_base: str, max_workers: int = 12) -> None:
    init_json = get_json(link_base_to_link(link_base, 1))

    number_of_pages = int(init_json["meta"]["pages_count"])
    title = init_json["submission"]["title"]
    author_name = init_json["submission"]["authorname"]
    author_homepage = init_json["submission"]["author"]["homepage"]
    story_link = f"https://literotica.com/s/{link_base}"

    title_with_border = f"""
--------------------------------------------
|Title: {title}|
|Author: {author_name}|
|Author Homepage: {author_homepage}|
|Story link: {story_link}|
--------------------------------------------"""
    print(title_with_border)
    with open("story.txt", mode="a", encoding="utf-8") as text_file:
        text_file.write(title_with_border)

    # Collect texts by page number, then write in order
    page_texts: dict[int, str] = {}

    # We already have page 1 text from init_json — save one request.
    page_texts[1] = init_json["pageText"]

    # Fetch remaining pages concurrently (2..N)
    pages_to_fetch = list(range(2, number_of_pages + 1))

    with alive_bar(number_of_pages, title="Downloading pages") as bar:
        bar()  # page 1 done

        if pages_to_fetch:
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = [
                    ex.submit(fetch_page_text, link_base, p) for p in pages_to_fetch
                ]

                for fut in as_completed(futures):
                    p, txt = fut.result()
                    page_texts[p] = txt
                    bar()

    # Write pages sequentially to keep correct order in file
    with open("story.txt", mode="a", encoding="utf-8") as text_file:
        for i in range(1, number_of_pages + 1):
            page_number_with_border = f"""
--------------------------------------------
|PAGE {i}|
--------------------------------------------\n"""
            text_file.write(page_number_with_border)
            text_file.write(page_texts.get(i, ""))


def extract_series_items(init_json: dict) -> list[str]:
    """
    Literotica API shapes vary. Handle common shapes:
    - series is None / [] / {}
    - series has items list with objects containing "url"
    """
    series = init_json["submission"].get("series")
    if not series:
        return []

    # If it's a dict with items
    if isinstance(series, dict) and isinstance(series.get("items"), list):
        urls = []
        for it in series["items"]:
            u = it.get("url")
            if isinstance(u, str) and u:
                urls.append(u)
        return urls

    # If it's already a list of items
    if isinstance(series, list):
        urls = []
        for it in series:
            if isinstance(it, dict):
                u = it.get("url")
                if isinstance(u, str) and u:
                    urls.append(u)
        return urls

    return []


def get_series(link_base: str, max_workers: int = 12) -> None:
    init_json = get_json(link_base_to_link(link_base, 1))
    series_urls = extract_series_items(init_json)

    if not series_urls:
        get_story(link_base, max_workers=max_workers)
        return

    # series_urls contains paths like "/s/some-story" or full URLs depending on API;
    # normalize to link_base.
    for u in series_urls:
        # If it's a full link or "/s/..." link, reuse init_link_to_link_base
        try:
            lb = init_link_to_link_base(
                u if "://" in u else f"https://literotica.com{u}"
            )
        except Exception:
            # Fallback: if API gives plain slug already
            lb = u.strip("/").split("/")[-1]
        get_story(lb, max_workers=max_workers)


if __name__ == "__main__":
    if os.path.isfile("story.txt"):
        print("There is a story in the directory. Delete it")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python script.py <literotica_story_url>")
        sys.exit(2)

    print(sys.argv[1])
    link_base = init_link_to_link_base(sys.argv[1])
    print(link_base)

    # Tune this: too high can trigger rate limits.
    get_series(link_base, max_workers=12)

    print("\n\n\n\n|||||||CREATE A GITHUB ISSUE IF YOU ENCOUNTER ANY PROBLEM|||||||")
