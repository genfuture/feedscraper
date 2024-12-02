import feedparser
from googlenewsdecoder import new_decoderv1
from newspaper import Article
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
import hashlib
import time

# Constants
LAST_PROCESSED_FILE = "last_processed_links.json"
ARTICLES_JSON_FILE = "new_articles.json"
ARTICLES_XML_FILE = "new_articles.xml"
RSS_FEED_URL = "https://news.google.com/rss/search?q=gadwal&hl=en-US&gl=US&ceid=US:en"
LIMIT_LINKS = 30  # Analyze top 30 posts

def load_existing_articles():
    """Load existing articles from JSON file."""
    try:
        with open(ARTICLES_JSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def load_processed_links():
    """Load previously processed links."""
    try:
        with open(LAST_PROCESSED_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_processed_links(links_set):
    """Save processed links to JSON file."""
    with open(LAST_PROCESSED_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(links_set), f, ensure_ascii=False, indent=4)

def get_links_from_rss(feed_url, limit=30):
    """Parse RSS feed and get links with their timestamps, limited to top N entries."""
    feed = feedparser.parse(feed_url)
    links = [
        {"link": entry.link, "published": entry.published_parsed, "title": entry.title}
        for entry in feed.entries
    ]
    return sorted(
        links,
        key=lambda x: time.mktime(x["published"]) if x["published"] else 0,
        reverse=True
    )[:limit]

def decode_google_news_links(links):
    """Decode Google News URLs."""
    decoded_links = []
    for item in links:
        try:
            result = new_decoderv1(item["link"])
            if result.get("status"):
                decoded_links.append({
                    "link": result["decoded_url"],
                    "published": item["published"],
                    "title": item["title"]
                })
            else:
                print(f"Failed to decode link: {item['link']}")
        except Exception as e:
            print(f"Error decoding link {item['link']}: {e}")
    return decoded_links

def scrape_articles_from_links(links):
    """Scrape articles using newspaper3k."""
    articles_data = []
    for item in links:
        try:
            article = Article(item["link"])
            article.download()
            article.parse()
            articles_data.append({
                "title": article.title,
                "author": article.authors,
                "publish_date": article.publish_date.strftime("%Y-%m-%d") if article.publish_date else None,
                "text": article.text,
                "top_image": article.top_image,
                "link": item["link"]
            })
        except Exception as e:
            print(f"Error processing {item['link']}: {e}")
    return articles_data

def save_articles_to_xml(articles, filename):
    """Save articles to XML in GitHub Pages-compatible format."""
    # Define namespaces
    namespaces = {
        "media": "http://search.yahoo.com/mrss/"
    }
    
    # Register namespaces
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)
    
    # Create the root RSS element with namespaces
    rss = ET.Element("rss", version="2.0", nsmap=namespaces)
    channel = ET.SubElement(rss, "channel")
    
    # Add channel metadata
    title = ET.SubElement(channel, "title")
    title.text = "Gadwal News Feed"
    link = ET.SubElement(channel, "link")
    link.text = RSS_FEED_URL
    description = ET.SubElement(channel, "description")
    description.text = "Latest news about Gadwal"
    language = ET.SubElement(channel, "language")
    language.text = "en-US"
    
    for article in articles:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = article["title"]
        ET.SubElement(item, "link").text = article["link"]
        ET.SubElement(item, "description").text = f'<![CDATA[{article["text"][:500]}...]]>'
        if article.get("publish_date"):
            ET.SubElement(item, "pubDate").text = article["publish_date"]
        if article.get("author"):
            ET.SubElement(item, "author").text = ", ".join(article["author"])
        if article.get("top_image"):
            ET.SubElement(item, f"{{{namespaces['media']}}}content", url=article["top_image"], medium="image")

    # Write XML to file
    tree = ET.ElementTree(rss)
    with open(filename, 'wb') as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding='utf-8', xml_declaration=False)


def parse_publish_date(article):
    """Convert publish_date to a datetime object for sorting."""
    publish_date = article.get("publish_date")
    if publish_date:
        try:
            return datetime.strptime(publish_date, "%Y-%m-%d")
        except ValueError:
            pass  # Handle invalid date formats gracefully
    return datetime.min  # Default to the earliest date for missing/invalid dates

if __name__ == "__main__":
    print("Loading existing data...")
    existing_articles = load_existing_articles()
    processed_links = load_processed_links()

    print("Fetching RSS feed...")
    all_links = get_links_from_rss(RSS_FEED_URL, LIMIT_LINKS)
    new_links = [
        link for link in all_links
        if link["link"] not in processed_links and not any(article['title'] == link['title'] for article in existing_articles)
    ]

    if not new_links:
        print("No new articles to process. Exiting...")
        exit(0)

    print("Decoding new links...")
    decoded_links = decode_google_news_links(new_links)

    print("Scraping articles...")
    new_articles = scrape_articles_from_links(decoded_links)

    if new_articles:
        processed_links.update(link['link'] for link in new_links)
        save_processed_links(processed_links)

        all_articles = existing_articles + new_articles
        all_articles.sort(key=parse_publish_date, reverse=True)
        all_articles = all_articles[:LIMIT_LINKS]

        with open(ARTICLES_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_articles, f, ensure_ascii=False, indent=4)

        save_articles_to_xml(all_articles, ARTICLES_XML_FILE)
        print(f"Saved {len(new_articles)} new articles.")
    else:
        print("No new articles were successfully scraped.")
