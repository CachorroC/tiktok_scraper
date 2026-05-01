import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import os
from datetime import datetime

async def scrape_video_comments(page, url, max_comments=100):
    """Scrapes comments from a specific TikTok video URL."""
    print(f"--- Scraping: {url} ---")
    
    # Use a more lenient wait
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"Initial load timed out, continuing anyway... {e}")
    
    await asyncio.sleep(5) # Wait for JS to settle

    # Updated selectors based on current TikTok DOM
    comment_item_selector = '[data-e2e="comment-item"], [class*="DivCommentItemWrapper"], [data-e2e="comment-level-1-item"]'
    
    # Try to ensure comments are visible
    try:
        # Check if we need to click to see comments (sometimes required on mobile/narrow layouts)
        comment_icon = await page.query_selector('[data-e2e="comment-icon"], button[aria-label*="comentarios"]')
        if comment_icon:
            print("Found comment icon, clicking to reveal comments...")
            await comment_icon.click()
            await asyncio.sleep(2)
    except:
        pass

    try:
        await page.wait_for_selector(comment_item_selector, timeout=15000)
    except:
        print(f"Warning: Comment selector not found immediately for {url}. Attempting to scroll...")

    comments_data = []
    last_len = 0
    retries = 0
    
    # TikTok often uses a specific scrollable container for comments
    # We try to find it, otherwise we scroll the body
    comment_container_selector = '[class*="DivCommentListContainer"], [class*="DivCommentContainer"], [class*="DivCommentItemWrapperContainer"]'
    
    while len(comments_data) < max_comments:
        container = await page.query_selector(comment_container_selector)
        if container:
            await container.evaluate("el => el.scrollTop += 2000")
        else:
            await page.mouse.wheel(0, 2000)
            
        await asyncio.sleep(3) # Wait for dynamic content
        
        elements = await page.query_selector_all(comment_item_selector)
        
        for el in elements:
            try:
                # Try multiple possible selectors for author and text
                author_el = await el.query_selector('[data-e2e="comment-username-1"], [data-e2e="comment-author-name"], [class*="DivUsernameContentWrapper"]')
                text_el = await el.query_selector('[data-e2e="comment-level-1"], [data-e2e="comment-level-1-text"], [class*="SpanCommentText"]')
                
                if author_el and text_el:
                    author = await author_el.inner_text()
                    text = await text_el.inner_text()
                    
                    if author and text:
                        comment = {'username': author.strip(), 'comment_text': text.strip()}
                        if comment not in comments_data:
                            comments_data.append(comment)
                            if len(comments_data) >= max_comments:
                                break
            except Exception:
                continue
        
        print(f"Progress: {len(comments_data)} comments found so far...")
        
        if len(comments_data) == last_len:
            retries += 1
            # If no new comments, try one last big scroll
            if retries == 3:
                await page.mouse.wheel(0, 5000)
            if retries > 6: break 
        else:
            retries = 0
        last_len = len(comments_data)
        
    return comments_data

async def main():
    video_urls = []
    
    # Try to read from a file if it exists, or ask for input
    url_input = input("Enter TikTok video URL: ")
    if url_input:
        video_urls.append(url_input)
    else:
        print("No URL provided.")
        return

    async with async_playwright() as p:
        # Using headless=False is crucial for TikTok to avoid easy detection/captchas
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()

        for url in video_urls:
            comments = await scrape_video_comments(page, url, max_comments=100)
            
            if comments:
                for c in comments:
                    c['video_url'] = url
                
                video_id = url.split('/')[-1].split('?')[0]
                filename = f"comments_{video_id}.xlsx"
                
                df = pd.DataFrame(comments)
                summary_data = pd.DataFrame([{'username': 'TOTAL COMMENTS', 'comment_text': len(comments)}])
                final_df = pd.concat([summary_data, df], ignore_index=True)
                
                final_df.to_excel(filename, index=False)
                print(f"SUCCESS: Saved {len(comments)} comments to {filename}")
            else:
                print(f"FAILED: No comments extracted for {url}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
