import feedparser
from googlenewsdecoder import new_decoderv1
from newspaper import Article
import json
import os
import xml.etree.ElementTree as ET

# File to store the last processed links
LAST_PROCESSED_FILE = "last_processed_links.json"

# Function to parse RSS feed and get links with their timestamps
def get_links_from_rss(feed_url):
    feed = feedparser.parse(feed_url)
    return [
        {"link": entry.link, "published": entry.published_parsed}
        for entry in feed.entries
    ]

# Function to decode Google News URLs using googlenewsdecoder
def decode_google_news_links(links):
    decoded_links = []
    for item in links:
        try:
            result = new_decoderv1(item["link"])  # Decode the Google News URL
            if result.get("status"):  # Check if decoding was successful
                decoded_links.append({
                    "link": result["decoded_url"],
                    "published": item["published"]
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

# Main function
if __name__ == "__main__":
    rss_url = "https://news.google.com/rss/search?q=gadwal&hl=en-US&gl=US&ceid=US:en"

    # Step 1: Load last processed links
    print("Loading last processed links...")
    last_processed_links = load_last_processed_links()
    print(f"Loaded {len(last_processed_links)} processed links.")

    # Step 2: Fetch links from RSS
    print("Fetching links from RSS...")
    links = get_links_from_rss(rss_url)
    print(f"Found {len(links)} links.")

    # Step 3: Decode Google News links
    print("Decoding Google News URLs...")
    decoded_links = decode_google_news_links(links)
    print(f"Decoded {len(decoded_links)} links.")

    # Step 4: Filter out already processed links
    print("Filtering out already processed links...")
    new_links = [item for item in decoded_links if item["link"] not in last_processed_links]
    print(f"Found {len(new_links)} new links.")

    if new_links:
        # Step 5: Scrape articles from new links
        print("Scraping articles from new links...")
        articles = scrape_articles_from_links(new_links)

        # Step 6: Save scraped articles to JSON
        articles_file = "new_articles.json"
        with open(articles_file, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=4)
        print(f"Scraped articles saved to {articles_file}.")

        # Step 7: Save articles to XML
        articles_xml_file = "new_articles.xml"
        save_articles_to_xml(articles, articles_xml_file)
        print(f"Scraped articles saved to {articles_xml_file}.")

        # Step 8: Update and save last processed links
        last_processed_links.extend([item["link"] for item in new_links])
        save_last_processed_links(last_processed_links)
        print(f"Last processed links updated and saved.")
    else:
        print("No new articles found.")
