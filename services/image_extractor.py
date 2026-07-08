import os
import re
from playwright.sync_api import sync_playwright
from .logger import logger
from .url_utils import make_absolute_url

def extract_image_data(url: str):
    logger.info(f"Starting extraction for URL: {url}")
    
    results = {
        "totalImages": 0,
        "png": 0,
        "svg": 0,
        "jpeg": 0,
        "images": []
    }
    
    # Allowed extensions
    allowed_exts = [".png", ".svg", ".jpg", ".jpeg"]
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--single-process",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Upgrade-Insecure-Requests": "1"
                }
            )
            page = context.new_page()
            
            # Remove the webdriver flag to avoid bot detection
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Go to URL and wait for page load
            try:
                page.goto(url, wait_until="load", timeout=90000)
            except Exception as e:
                logger.warning(f"Goto timed out, attempting to extract anyway: {e}")
            
            # Scroll down to the bottom of the page in steps to trigger lazy loading
            page.evaluate("""async () => {
                await new Promise((resolve) => {
                    let totalHeight = 0;
                    const distance = 100;
                    const timer = setInterval(() => {
                        const scrollHeight = document.body.scrollHeight;
                        window.scrollBy(0, distance);
                        totalHeight += distance;
                        
                        if (totalHeight >= scrollHeight || totalHeight > 20000) {
                            clearInterval(timer);
                            resolve();
                        }
                    }, 50);
                });
            }""")
            page.wait_for_timeout(2000)
            
            # Scroll back to top
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)
            
            # Extract all image metadata from the page
            images_data = page.evaluate("""() => {
                const results = [];
                
                // Process all img elements
                document.querySelectorAll('img').forEach(img => {
                    let src = img.currentSrc || img.src 
                           || img.getAttribute('src')
                           || img.getAttribute('data-src')
                           || img.getAttribute('data-lazy-src')
                           || img.getAttribute('data-original');
                           
                    if (!src || src === window.location.href) return;
                    if (src.startsWith('data:') || src.startsWith('blob:')) return;
                    
                    try { src = new URL(src, window.location.href).href; } catch(e) { return; }
                    
                    let tag = '<img>';
                    if (img.parentElement && img.parentElement.tagName.toLowerCase() === 'picture') {
                        tag = '<picture>';
                    }
                    
                    results.push({
                        tag: tag,
                        src: src,
                        alt: img.getAttribute('alt'),
                        displayedWidth: img.width || img.clientWidth || img.offsetWidth || 0,
                        displayedHeight: img.height || img.clientHeight || img.offsetHeight || 0,
                        originalWidth: img.naturalWidth || 0,
                        originalHeight: img.naturalHeight || 0,
                        loadingAttribute: img.getAttribute('loading') || '',
                        fetchpriority: img.getAttribute('fetchpriority') || '',
                        decoding: img.getAttribute('decoding') || '',
                        crossorigin: img.getAttribute('crossorigin') || '',
                        referrerpolicy: img.getAttribute('referrerpolicy') || '',
                        missingWHAttributes: (!img.getAttribute('width') || !img.getAttribute('height')),
                        lazyLoaded: (img.getAttribute('loading') === 'lazy'),
                        responsive: !!(img.getAttribute('srcset') || img.getAttribute('sizes')),
                        broken: (img.naturalWidth === 0 && img.naturalHeight === 0)
                    });
                });
                
                // Process all source elements in picture tags
                document.querySelectorAll('source').forEach(source => {
                    let src = source.getAttribute('srcset') || source.getAttribute('src');
                    if (!src) return;
                    
                    src = src.split(' ')[0];
                    if (src.startsWith('data:') || src.startsWith('blob:')) return;
                    
                    try { src = new URL(src, window.location.href).href; } catch(e) { return; }
                    
                    results.push({
                        tag: '<source>',
                        src: src,
                        alt: null,
                        displayedWidth: 0,
                        displayedHeight: 0,
                        originalWidth: 0,
                        originalHeight: 0,
                        loadingAttribute: '',
                        fetchpriority: '',
                        decoding: '',
                        crossorigin: '',
                        referrerpolicy: '',
                        missingWHAttributes: true,
                        lazyLoaded: false,
                        responsive: true,
                        broken: false
                    });
                });
                
                return results;
            }""")
            
            browser.close()
            
            # Post process images
            processed_images = []
            seen_urls = set()
            
            for img in images_data:
                src = make_absolute_url(url, img['src'])
                if not src:
                    continue
                    
                parsed_url = str(src).lower()
                
                # Get extension and filename
                ext = ""
                file_name = ""
                try:
                    path = src.split('?')[0].split('#')[0]
                    file_name = path.split('/')[-1]
                    ext = "." + file_name.split('.')[-1].lower() if '.' in file_name else ""
                except:
                    pass
                
                # Verify allowed extension
                if ext not in allowed_exts:
                    if not any(a_ext in parsed_url for a_ext in allowed_exts):
                        continue
                    for a_ext in allowed_exts:
                        if a_ext in parsed_url:
                            ext = a_ext
                            break
                            
                results["totalImages"] += 1
                if ext == ".png":
                    results["png"] += 1
                elif ext == ".svg":
                    results["svg"] += 1
                elif ext in [".jpg", ".jpeg"]:
                    results["jpeg"] += 1
                
                # Compute display difference
                w = img['displayedWidth']
                h = img['displayedHeight']
                nw = img['originalWidth']
                nh = img['originalHeight']
                
                w_diff = 0
                h_diff = 0
                if nw > 0:
                    w_diff = ((nw - w) / nw) * 100
                if nh > 0:
                    h_diff = ((nh - h) / nh) * 100
                    
                display_diff_str = f"W: {w_diff:.2f}%\nH: {h_diff:.2f}%"
                
                img['displayDifference'] = display_diff_str
                img['extension'] = ext
                img['fileName'] = file_name
                img['duplicate'] = src in seen_urls
                seen_urls.add(src)
                
                img['missingAlt'] = img['alt'] is None
                img['zeroDimensions'] = (w == 0 and h == 0)
                img['upscaled'] = (w > nw and nw > 0) or (h > nh and nh > 0)
                img['downscaled'] = (w < nw and w > 0) or (h < nh and h > 0)
                img['src'] = src
                
                processed_images.append(img)
                
            results["images"] = processed_images
            return results
            
        except Exception as e:
            logger.error(f"Error during Playwright execution: {str(e)}")
            raise e
