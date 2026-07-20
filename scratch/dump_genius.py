import sys
import time
from playwright.sync_api import sync_playwright

def main():
    url = "https://powerprogenius.com/secure-bogo/index-B.php"
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("Navigating to URL...")
        page.goto(url, wait_until="load", timeout=90000)
        
        # Scroll to load everything
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)
        
        print("Running hybrid extraction...")
        images_data = page.evaluate("""async () => {
            const results = [];
            const imgs = document.querySelectorAll('img');
            
            const promises = Array.from(imgs).map(async (img, idx) => {
                let src = img.currentSrc || img.src 
                       || img.getAttribute('src')
                       || img.getAttribute('data-src')
                       || img.getAttribute('data-lazy-src')
                       || img.getAttribute('data-original');
                       
                if (!src || src === window.location.href) return;
                if (src.startsWith('data:') || src.startsWith('blob:')) return;
                
                try { src = new URL(src, window.location.href).href; } catch(e) { return; }
                
                let dispW = img.width || img.clientWidth || img.offsetWidth || 0;
                let dispH = img.height || img.clientHeight || img.offsetHeight || 0;
                
                let origW = img.naturalWidth || 0;
                let origH = img.naturalHeight || 0;
                
                // If original dimensions are 0 (lazy loaded/hidden), load in background to measure
                if (origW === 0 || origH === 0) {
                    const dims = await new Promise(resolve => {
                        const tempImg = new Image();
                        tempImg.onload = () => resolve({ w: tempImg.naturalWidth, h: tempImg.naturalHeight });
                        tempImg.onerror = () => resolve({ w: 0, h: 0 });
                        tempImg.src = src;
                        setTimeout(() => resolve({ w: 0, h: 0 }), 8000);
                    });
                    origW = dims.w;
                    origH = dims.h;
                }
                
                results.push({
                    idx: idx,
                    src: src,
                    displayedWidth: dispW,
                    displayedHeight: dispH,
                    originalWidth: origW,
                    originalHeight: origH
                });
            });
            
            await Promise.all(promises);
            return results;
        }""")
        
        print(f"Extracted {len(images_data)} images:")
        for img in images_data:
            if "paypal" in img["src"] or "shield" in img["src"] or "60days" in img["src"]:
                print(f"Idx {img['idx']}: {img['src']} | Displayed: {img['displayedWidth']}x{img['displayedHeight']} | Original: {img['originalWidth']}x{img['originalHeight']}")
                
        browser.close()

if __name__ == "__main__":
    main()
