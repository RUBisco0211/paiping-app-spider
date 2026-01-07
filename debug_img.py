import logging
import sys
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

from spider.fetcher import SspaiFetcher

print("Starting debug script...", flush=True)
try:
    f = SspaiFetcher()
    print("Fetcher init done.", flush=True)
    articles = f.fetch_feed_articles(limit=1)
    print(f"Articles: {len(articles)}", flush=True)
    if articles:
        print(f"First article: {articles[0]['title']}", flush=True)
        aid = articles[0]['id']
        detail = f.get_article_detail(aid)
        if detail:
            body = detail.get('body', '')
            print(f"Body snippet: {body[:100]}", flush=True)
            if '<img' in body:
                print("Found img tag!", flush=True)
            else:
                print("No img tag found.", flush=True)
        else:
            print("Detail is None", flush=True)
except Exception as e:
    print(f"Exception: {e}", flush=True)
