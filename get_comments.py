import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import os
from datetime import datetime

async def scrape_video_comments(page, url, max_comments=100):
    """Scrapes comments from a specific TikTok video URL."""
    print(f"--- Scraping: {url} ---")
    await page.goto(url, wait_until="networkidle")
    
    # Wait for the comment section
    try:
        await page.wait_for_selector('[data-e2e="comment-level-1-item"]', timeout=10000)
    except:
        print(f"No comments found or layout changed for {url}")
        # Sometimes you need to click to see comments on some layouts
        pass

    comments_data = []
    last_len = 0
    retries = 0
    
    while len(comments_data) < max_comments:
        # Scroll the comment container if it exists, otherwise scroll the page
        await page.mouse.wheel(0, 1500)
        await asyncio.sleep(2) # Wait for loading
        
        elements = await page.query_selector_all('[data-e2e="comment-level-1-item"]')
        
        for el in elements:
            try:
                author = await (await el.query_selector('[data-e2e="comment-author-name"]')).inner_text()
                text = await (await el.query_selector('[data-e2e="comment-level-1-text"]')).inner_text()
                
                comment = {'username': author, 'comment_text': text}
                if comment not in comments_data:
                    comments_data.append(comment)
                    if len(comments_data) >= max_comments:
                        break
            except:
                continue
        
        print(f"Progress: {len(comments_data)} comments...")
        
        if len(comments_data) == last_len:
            retries += 1
            if retries > 4: break # Stop if no new comments
        else:
            retries = 0
        last_len = len(comments_data)
        
    return comments_data

async def main():
    # You can pass a list of URLs here
    video_urls = [
        # "https://www.tiktok.com/@user/video/1234567890",
    ]
    
    if not video_urls:
        url_input = input("Enter TikTok video URL (or leave blank to use examples): ")
        if url_input:
            video_urls.append(url_input)
        else:
            print("No URLs provided. Please edit the script or provide an input.")
            return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) # Headless=False helps avoid detection
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        all_results = []

        for url in video_urls:
            comments = await scrape_video_comments(page, url, max_comments=100)
            
            if comments:
                # Add metadata to each comment
                for c in comments:
                    c['video_url'] = url
                
                # Save individual Excel for this video
                video_id = url.split('/')[-1].split('?')[0]
                filename = f"comments_{video_id}.xlsx"
                
                df = pd.DataFrame(comments)
                
                # Add total count as a header-like row or separate sheet
                # User wants "total of comments" inside the table
                summary_data = pd.DataFrame([{'username': 'TOTAL COMMENTS', 'comment_text': len(comments)}])
                final_df = pd.concat([summary_data, df], ignore_index=True)
                
                final_df.to_excel(filename, index=False)
                print(f"Saved {len(comments)} comments to {filename}")
                all_results.append(final_df)

        await browser.close()
        
        if all_results:
            # Optionally save all to one master file
            master_df = pd.concat(all_results, ignore_index=True)
            master_df.to_excel("tiktok_comments_all.xlsx", index=False)
            print("Saved all comments to tiktok_comments_all.xlsx")

if __name__ == "__main__":
    asyncio.run(main())
