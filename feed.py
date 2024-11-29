import feedparser
from googlenewsdecoder import new_decoderv1
from newspaper import Article
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import hashlib
import time

# File to store the last processed links
LAST_PROCESSED_FILE = "last_processed_links.json"

# Function to parse RSS feed and get links with their timestamps
def get_links_from_rss(feed_url, limit=50):
    """Parse RSS feed and get links with their timestamps, limited to top N entries"""
    feed = feedparser.parse(feed_url)
    links = [
        {"link": entry.link, "published": entry.published_parsed, "title": entry.title}
        for entry in feed.entries
    ]
    # Sort by published date (newest first) and limit to top N
    sorted_links = sorted(links, 
                         key=lambda x: time.mktime(x["published"]) if x["published"] else 0, 
                         reverse=True)
    return sorted_links[:limit]

# Function to decode Google News URLs using googlenewsdecoder
def decode_google_news_links(links):
    """Decode Google News URLs using googlenewsdecoder"""
    decoded_links = []
    for item in links:
        try:
            result = new_decoderv1(item["link"])  # Decode the Google News URL
            if result.get("status"):  # Check if decoding was successful
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

# Function to scrape articles using newspaper3k
def scrape_articles_from_links(links):
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
                "top_image": article.top_image,  # Fetch the main image URL
                "link": item["link"]
            })
        except Exception as e:
            print(f"Error processing {item['link']}: {e}")
    return articles_data

# Function to load last processed links
def load_last_processed_links():
    if os.path.exists(LAST_PROCESSED_FILE):
        with open(LAST_PROCESSED_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# Function to save last processed links
def save_last_processed_links(links):
    with open(LAST_PROCESSED_FILE, 'w', encoding='utf-8') as f:
        json.dump(links, f, ensure_ascii=False, indent=4)

# Function to save articles to RSS XML
def save_articles_to_xml(articles, filename):
    # Create the root RSS element
    rss = ET.Element("rss", version="2.0")
    
    # Create channel element
    channel = ET.SubElement(rss, "channel")
    
    # Add required channel elements
    title = ET.SubElement(channel, "title")
    title.text = "Gadwal News Feed"
    
    link = ET.SubElement(channel, "link")
    link.text = "https://news.google.com/rss/search?q=gadwal"
    
    description = ET.SubElement(channel, "description")
    description.text = "Latest news about Gadwal"
    
    language = ET.SubElement(channel, "language")
    language.text = "en-US"
    
    # Add each article as an item
    for article in articles:
        item = ET.SubElement(channel, "item")
        
        # Title (required)
        item_title = ET.SubElement(item, "title")
        item_title.text = article["title"]
        
        # Link (required)
        item_link = ET.SubElement(item, "link")
        item_link.text = article["link"]
        
        # Description (required)
        item_description = ET.SubElement(item, "description")
        # Create CDATA section for the content
        item_description.text = f'<![CDATA[{article["text"][:500]}...]]>'
        
        # Publication date
        if article["publish_date"]:
            pubDate = ET.SubElement(item, "pubDate")
            pubDate.text = article["publish_date"]
        
        # Author(s)
        if article["author"]:
            author = ET.SubElement(item, "author")
            author.text = ", ".join(article["author"])
        
        # Image (using media:content namespace)
        if article["top_image"]:
            media = ET.SubElement(item, "media:content", 
                                url=article["top_image"],
                                medium="image",
                                xmlns="http://search.yahoo.com/mrss/")

    # Create the ElementTree and write to file
    tree = ET.ElementTree(rss)
    
    # Add XML declaration and write with proper encoding
    with open(filename, 'wb') as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding='utf-8', xml_declaration=False)

# Add new function to generate unique hash for articles
def generate_article_hash(article_data):
    """Generate a unique hash based on article title and link"""
    content = f"{article_data['title']}{article_data['link']}"
    return hashlib.md5(content.encode()).hexdigest()

# Add new function to load existing articles
def load_existing_articles():
    """Load existing articles from JSON file"""
    try:
        with open("new_articles.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def check_for_updates(current_links, existing_count):
    """
    Check if there are actually new articles to process
    Returns True if new articles exist, False otherwise
    """
    if len(current_links) <= existing_count:
        print(f"No new articles found (Current: {len(current_links)}, Existing: {existing_count})")
        return False
    
    print(f"Found {len(current_links) - existing_count} new articles to process")
    return True

def load_processed_links():
    """Load the set of processed links from JSON file"""
    try:
        with open("processed_links.json", 'r', encoding='utf-8') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_processed_links(links_set):
    """Save the set of processed links to JSON file"""
    with open("processed_links.json", 'w', encoding='utf-8') as f:
        json.dump(list(links_set), f, ensure_ascii=False, indent=4)

# Main function
if __name__ == "__main__":
    rss_url = "https://news.google.com/rss/search?q=gadwal&hl=en-US&gl=US&ceid=US:en"
    LIMIT_LINKS = 50  # Set limit for top N links

    # Load existing articles and processed links
    print("Loading existing articles and processed links...")
    existing_articles = load_existing_articles()
    processed_links = load_processed_links()
    print(f"Loaded {len(existing_articles)} existing articles.")
    print(f"Loaded {len(processed_links)} processed links.")

    # Fetch latest top 50 links from RSS
    print(f"Fetching top {LIMIT_LINKS} links from RSS...")
    all_links = get_links_from_rss(rss_url, LIMIT_LINKS)
    print(f"Found {len(all_links)} total links.")

    # Filter new links using both title and link checks
    new_links = [
        link for link in all_links 
        if not any(article['title'] == link['title'] for article in existing_articles)
        and link['link'] not in processed_links
    ]
    
    print(f"Found {len(new_links)} new links to process.")

    if not new_links:
        print("No new articles to process. Exiting...")
        print("\nFinal Statistics:")
        print(f"Total articles in database: {len(existing_articles)}")
        print(f"Total processed links: {len(processed_links)}")
        print(f"New articles added: 0")
        exit(0)

    # Only decode the new links
    print(f"Decoding {len(new_links)} new Google News URLs...")
    decoded_links = decode_google_news_links(new_links)
    print(f"Successfully decoded {len(decoded_links)} links.")

    if decoded_links:
        # Scrape articles from new links
        print("Scraping articles from new links...")
        new_articles = scrape_articles_from_links(decoded_links)

        if new_articles:
            # Update processed links before combining articles
            for link in new_links:
                processed_links.add(link['link'])
            
            # Keep only the latest processed links if exceeding limit
            if len(processed_links) > LIMIT_LINKS * 2:  # Keep twice the limit for history
                processed_links = set(sorted(processed_links, reverse=True)[:LIMIT_LINKS])
            
            # Save updated processed links
            save_processed_links(processed_links)
            print(f"Updated processed links saved. Total: {len(processed_links)}")

            # Combine with existing and keep only top 50
            all_articles = existing_articles + new_articles
            
            # Sort by date and limit to 50
            all_articles.sort(
                key=lambda x: datetime.strptime(x["publish_date"], "%Y-%m-%d") 
                if x.get("publish_date") else datetime.min,
                reverse=True
            )
            all_articles = all_articles[:LIMIT_LINKS]

            # Save all articles to JSON
            articles_file = "new_articles.json"
            with open(articles_file, 'w', encoding='utf-8') as f:
                json.dump(all_articles, f, ensure_ascii=False, indent=4)
            print(f"Articles saved to {articles_file}.")

            # Save to XML
            articles_xml_file = "new_articles.xml"
            save_articles_to_xml(all_articles, articles_xml_file)
            print(f"Articles saved to {articles_xml_file}.")

            print("\nFinal Statistics:")
            print(f"Total articles in database: {len(all_articles)}")
            print(f"Total processed links: {len(processed_links)}")
            print(f"New articles added: {len(new_articles)}")
        else:
            print("No articles were successfully scraped.")
    else:
        print("No links were successfully decoded.")

    # Final statistics even if no new articles were added
    print("\nFinal Statistics:")
    print(f"Total articles in database: {len(existing_articles)}")
    print(f"Total processed links: {len(processed_links)}")
    print(f"New articles added: {len(new_articles) if 'new_articles' in locals() else 0}")
