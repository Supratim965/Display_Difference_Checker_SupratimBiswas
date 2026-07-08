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
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
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
            # (Wrapped in an IIFE () so it actually executes)
            page.evaluate("""(async () => {
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
            })()""")
            page.wait_for_timeout(2000)
            
            # Scroll back to top
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)
            
            # Extract all image metadata from the page using hybrid async loading for hidden/lazy images
            images_data = page.evaluate("""async () => {
                const results = [];
                const imgs = document.querySelectorAll('img');
                
                const promises = Array.from(imgs).map(async (img) => {
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
                    
                    let dispW = img.width || img.clientWidth || img.offsetWidth || 0;
                    let dispH = img.height || img.clientHeight || img.offsetHeight || 0;
                    
                    let origW = img.naturalWidth || 0;
                    let origH = img.naturalHeight || 0;
                    
                    // If original dimensions are 0 (lazy loaded or hidden), load in background to measure
                    if (origW === 0 || origH === 0) {
                        const dims = await new Promise(resolve => {
                            const tempImg = new Image();
                            tempImg.onload = () => resolve({ w: tempImg.naturalWidth, h: tempImg.naturalHeight });
                            tempImg.onerror = () => resolve({ w: 0, h: 0 });
                            tempImg.src = src;
                            // 5s timeout
                            setTimeout(() => resolve({ w: 0, h: 0 }), 5000);
                        });
                        origW = dims.w;
                        origH = dims.h;
                    }
                    
                    results.push({
                        tag: tag,
                        src: src,
                        alt: img.getAttribute('alt'),
                        displayedWidth: dispW,
                        displayedHeight: dispH,
                        originalWidth: origW,
                        originalHeight: origH,
                        loadingAttribute: img.getAttribute('loading') || '',
                        fetchpriority: img.getAttribute('fetchpriority') || '',
                        decoding: img.getAttribute('decoding') || '',
                        crossorigin: img.getAttribute('crossorigin') || '',
                        referrerpolicy: img.getAttribute('referrerpolicy') || '',
                        missingWHAttributes: (!img.getAttribute('width') || !img.getAttribute('height')),
                        lazyLoaded: (img.getAttribute('loading') === 'lazy'),
                        responsive: !!(img.getAttribute('srcset') || img.getAttribute('sizes')),
                        broken: (origW === 0 && origH === 0)
                    });
                });
                
                await Promise.all(promises);
                
                // Process all <source> elements (async so we can background-load for original dims)
                const sourcesPromises = Array.from(document.querySelectorAll('source')).map(async (source) => {
                    // srcset may contain multiple comma-separated candidates — take the first URL only
                    let srcRaw = source.getAttribute('srcset') || source.getAttribute('src');
                    if (!srcRaw) return;
                    
                    let src = srcRaw.split(',')[0].trim().split(/\\s+/)[0];
                    if (!src || src.startsWith('data:') || src.startsWith('blob:')) return;
                    
                    try { src = new URL(src, window.location.href).href; } catch(e) { return; }
                    
                    // --- Displayed dimensions ---
                    // <source> has no layout box; use the sibling <img> inside the same <picture> instead.
                    let dispW = null;
                    let dispH = null;
                    const parent = source.parentElement;
                    if (parent && parent.tagName.toLowerCase() === 'picture') {
                        const siblingImg = parent.querySelector('img');
                        if (siblingImg) {
                            const sw = siblingImg.width || siblingImg.clientWidth || siblingImg.offsetWidth;
                            const sh = siblingImg.height || siblingImg.clientHeight || siblingImg.offsetHeight;
                            // Only store if non-zero; leave null when the sibling is also unrendered
                            if (sw > 0) dispW = sw;
                            if (sh > 0) dispH = sh;
                        }
                    }
                    
                    // --- Original (intrinsic) dimensions ---
                    // Load the image URL in a temporary off-DOM Image() to read naturalWidth/naturalHeight.
                    let origW = null;
                    let origH = null;
                    const dims = await new Promise(resolve => {
                        const tempImg = new Image();
                        tempImg.onload  = () => resolve({ w: tempImg.naturalWidth, h: tempImg.naturalHeight });
                        tempImg.onerror = () => resolve({ w: null, h: null });
                        tempImg.src = src;
                        // 8-second safety timeout so a stalled request doesn't block everything
                        setTimeout(() => resolve({ w: null, h: null }), 8000);
                    });
                    if (dims.w && dims.w > 0) origW = dims.w;
                    if (dims.h && dims.h > 0) origH = dims.h;
                    
                    results.push({
                        tag: '<source>',
                        src: src,
                        alt: null,
                        // null means "could not determine" — Python will write "N/A" to Excel
                        displayedWidth: dispW,
                        displayedHeight: dispH,
                        originalWidth: origW,
                        originalHeight: origH,
                        loadingAttribute: '',
                        fetchpriority: '',
                        decoding: '',
                        crossorigin: '',
                        referrerpolicy: '',
                        missingWHAttributes: true,
                        lazyLoaded: false,
                        responsive: true,
                        broken: (origW === null && origH === null)
                    });
                });
                
                await Promise.all(sourcesPromises);
                
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
                # w/h/nw/nh may be None for <source> elements where the dimension is unknown
                w  = img['displayedWidth']
                h  = img['displayedHeight']
                nw = img['originalWidth']
                nh = img['originalHeight']
                
                # Only calculate percentage diffs when both displayed and original are real numbers
                def _num(v):
                    return isinstance(v, (int, float))
                
                w_diff_str = f"{((nw - w) / nw) * 100:.2f}%" if _num(w) and _num(nw) and nw > 0 else "N/A"
                h_diff_str = f"{((nh - h) / nh) * 100:.2f}%" if _num(h) and _num(nh) and nh > 0 else "N/A"
                display_diff_str = f"W: {w_diff_str}\nH: {h_diff_str}"
                
                img['displayDifference'] = display_diff_str
                img['extension'] = ext
                img['fileName'] = file_name
                img['duplicate'] = src in seen_urls
                seen_urls.add(src)
                
                # Replace None with "N/A" for the Excel columns — never write 0 for unknown dims
                img['displayedWidth']  = w  if w  is not None else "N/A"
                img['displayedHeight'] = h  if h  is not None else "N/A"
                img['originalWidth']   = nw if nw is not None else "N/A"
                img['originalHeight']  = nh if nh is not None else "N/A"
                
                img['missingAlt'] = img['alt'] is None
                # zeroDimensions only when we have real numbers and both are 0
                img['zeroDimensions'] = (_num(w) and w == 0 and _num(h) and h == 0)
                img['upscaled']   = (_num(w) and _num(nw) and w > nw and nw > 0) or \
                                    (_num(h) and _num(nh) and h > nh and nh > 0)
                img['downscaled'] = (_num(w) and _num(nw) and w < nw and w > 0) or \
                                    (_num(h) and _num(nh) and h < nh and h > 0)
                img['src'] = src
                
                processed_images.append(img)
                
            results["images"] = processed_images
            return results
            
        except Exception as e:
            logger.error(f"Error during Playwright execution: {str(e)}")
            raise e
