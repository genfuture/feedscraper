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
ARTICLES_JSON_FILE = "articles.json"
RSS_FEEDS = {
    "gadwal": "https://news.google.com/rss/search?q=gadwal&hl=en-US&gl=US&ceid=US:en",
    "raichur": "https://news.google.com/rss/search?q=raichur&hl=en-US&gl=US&ceid=US:en",
}
LIMIT_LINKS = 30

def load_processed_links(feed_name):
    """Load previously processed links for a specific feed."""
    try:
        with open(f"{feed_name}_processed_links.json", 'r', encoding='utf-8') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_processed_links(feed_name, links_set):
    """Save processed links for a specific feed."""
    with open(f"{feed_name}_processed_links.json", 'w', encoding='utf-8') as f:
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

def save_articles_to_xml(feed_name, articles, filename):
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
    title.text = f"{feed_name.capitalize()} News Feed"
    link = ET.SubElement(channel, "link")
    link.text = RSS_FEEDS[feed_name]
    description = ET.SubElement(channel, "description")
    description.text = f"Latest news about {feed_name.capitalize()}"
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
            pass
    return datetime.min

if __name__ == "__main__":
    for feed_name, feed_url in RSS_FEEDS.items():
        print(f"Processing {feed_name.capitalize()} news feed...")

        processed_links = load_processed_links(feed_name)

        all_links = get_links_from_rss(feed_url, LIMIT_LINKS)
        new_links = [
            link for link in all_links
            if link["link"] not in processed_links
        ]

        if not new_links:
            print(f"No new articles for {feed_name}.")
            continue

        decoded_links = decode_google_news_links(new_links)
        new_articles = scrape_articles_from_links(decoded_links)

        if new_articles:
            processed_links.update(link['link'] for link in new_links)
            save_processed_links(feed_name, processed_links)

            # Sort by date
            new_articles.sort(key=parse_publish_date, reverse=True)

            # Save to XML
            save_articles_to_xml(feed_name, new_articles, f"{feed_name}.xml")
            print(f"Saved {len(new_articles)} new articles for {feed_name} to {feed_name}.xml.")
        else:
            print(f"No articles were successfully scraped for {feed_name}.")
