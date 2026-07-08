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
    
    # Allowed extensions (including JPEG/JPG as per user request)
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
                    "--single-process"
                ]
            )
            context = browser.new_context()
            page = context.new_page()
            
            # Go to URL and wait for DOMContentLoaded (fastest)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90000)
            except Exception as e:
                logger.warning(f"Goto timed out or had an issue, but attempting to extract anyway: {e}")
            
            # Inject a script to scroll down slightly or completely to trigger lazy loads?
            page.evaluate("""
                window.scrollTo(0, document.body.scrollHeight);
            """)
            page.wait_for_timeout(2000) # give it a moment
            
            # Extract data using browser JS
            images_data = page.evaluate("""() => {
                const results = [];
                // Find all img tags
                const imgs = document.querySelectorAll('img');
                
                imgs.forEach(img => {
                    // Try to determine src
                    let src = img.currentSrc || img.src || img.getAttribute('src');
                    if (!src) return;
                    
                    if (src.startsWith('data:image') || src.startsWith('blob:')) {
                        return;
                    }
                    
                    let tag = '<img>';
                    if (img.parentElement && img.parentElement.tagName.toLowerCase() === 'picture') {
                        tag = '<picture>';
                    }
                    
                    // Dimensions
                    let width = img.width || img.clientWidth || 0;
                    let height = img.height || img.clientHeight || 0;
                    let naturalWidth = img.naturalWidth || 0;
                    let naturalHeight = img.naturalHeight || 0;
                    
                    let broken = false;
                    if (naturalWidth === 0 || naturalHeight === 0) {
                        broken = true;
                    }
                    
                    results.push({
                        tag: tag,
                        src: src,
                        alt: img.getAttribute('alt') !== null ? img.getAttribute('alt') : null,
                        displayedWidth: width,
                        displayedHeight: height,
                        originalWidth: naturalWidth,
                        originalHeight: naturalHeight,
                        loadingAttribute: img.getAttribute('loading') || '',
                        fetchpriority: img.getAttribute('fetchpriority') || '',
                        decoding: img.getAttribute('decoding') || '',
                        crossorigin: img.getAttribute('crossorigin') || '',
                        referrerpolicy: img.getAttribute('referrerpolicy') || '',
                        missingWHAttributes: (!img.getAttribute('width') || !img.getAttribute('height')),
                        lazyLoaded: (img.getAttribute('loading') === 'lazy'),
                        responsive: (img.getAttribute('srcset') || img.getAttribute('sizes')) ? true : false,
                        broken: broken
                    });
                });
                
                // Now handle sources in picture that didn't have an img fallback maybe? 
                // Mostly covered by img.currentSrc, but let's check <source> tags directly
                const sources = document.querySelectorAll('source');
                sources.forEach(source => {
                    let src = source.getAttribute('srcset') || source.getAttribute('src');
                    if (!src) return;
                    
                    // take just the first part of srcset if it has multiple
                    src = src.split(' ')[0];
                    if (src.startsWith('data:image') || src.startsWith('blob:')) {
                        return;
                    }
                    
                    results.push({
                        tag: '<source>',
                        src: src,
                        alt: null,
                        displayedWidth: 0, // cannot reliably determine without matching img
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
                
                # Try to get extension
                ext = ""
                file_name = ""
                try:
                    path = src.split('?')[0].split('#')[0]
                    file_name = path.split('/')[-1]
                    ext = "." + file_name.split('.')[-1].lower() if '.' in file_name else ""
                except:
                    pass
                
                # Check if it's one of allowed
                if ext not in allowed_exts:
                    # Also check if the URL contains .png etc. as a fallback
                    if not any(a_ext in parsed_url for a_ext in allowed_exts):
                        continue
                    # Re-assign best guess ext
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
                
                # Compute difference
                nw = img['originalWidth']
                nh = img['originalHeight']
                w = img['displayedWidth']
                h = img['displayedHeight']
                
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
