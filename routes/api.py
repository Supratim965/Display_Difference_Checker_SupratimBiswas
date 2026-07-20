from flask import Blueprint, request, jsonify, send_from_directory, current_app
import os
import uuid
import threading
from services.url_utils import is_valid_url
from services.image_extractor import extract_image_data
from services.excel_generator import generate_excel_report
from services.logger import logger

api_bp = Blueprint('api', __name__)

# In-memory job store  { job_id: { status, result, error } }
_jobs = {}
_jobs_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------
def _run_analysis(job_id: str, valid_urls: list):
    try:
        aggregated_results = {
            "totalImages": 0,
            "png": 0,
            "svg": 0,
            "jpeg": 0,
            "images": []
        }

        for u in valid_urls:
            try:
                extraction_results = extract_image_data(u)
                aggregated_results["totalImages"] += extraction_results["totalImages"]
                aggregated_results["png"]         += extraction_results["png"]
                aggregated_results["svg"]         += extraction_results["svg"]
                aggregated_results["jpeg"]        += extraction_results["jpeg"]
                aggregated_results["images"].extend(extraction_results["images"])
            except Exception as e:
                logger.error(f"Analysis failed for URL {u}: {str(e)}")

        if aggregated_results["totalImages"] == 0:
            with _jobs_lock:
                _jobs[job_id] = {
                    "status": "error",
                    "error": "No PNG, SVG, or JPEG images found on the provided page(s)."
                }
            return

        excel_filename = f"Image_Checkpoints_{job_id[:8]}.xlsx"
        generate_excel_report(aggregated_results["images"], excel_filename)

        with _jobs_lock:
            _jobs[job_id] = {
                "status": "done",
                "result": {
                    "totalImages": aggregated_results["totalImages"],
                    "png":         aggregated_results["png"],
                    "svg":         aggregated_results["svg"],
                    "jpeg":        aggregated_results["jpeg"],
                    "excel":       f"downloads/{excel_filename}"
                }
            }

    except Exception as e:
        logger.error(f"Background analysis failed (job {job_id}): {str(e)}")
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "error",
                "error": "An unexpected error occurred during analysis. Please try again."
            }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@api_bp.route('/analyze', methods=['POST'])
def analyze_url():
    """Accepts URLs, starts a background job, and returns a job_id immediately."""
    data = request.get_json()
    if not data or ('url' not in data and 'urls' not in data):
        return jsonify({"status": "error", "message": "URL(s) required"}), 400

    urls = data.get('urls', [])
    if 'url' in data and not urls:
        urls = [data['url']]

    if not urls:
        return jsonify({"status": "error", "message": "No valid URLs provided"}), 400

    valid_urls = [u for u in urls if is_valid_url(u)]
    if not valid_urls:
        return jsonify({"status": "error", "message": "Invalid URL(s) provided"}), 400

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {"status": "pending"}

    thread = threading.Thread(target=_run_analysis, args=(job_id, valid_urls), daemon=True)
    thread.start()

    return jsonify({"status": "pending", "job_id": job_id}), 202


@api_bp.route('/status/<job_id>', methods=['GET'])
def job_status(job_id: str):
    """Poll this endpoint to check the status of an analysis job."""
    with _jobs_lock:
        job = _jobs.get(job_id)

    if job is None:
        return jsonify({"status": "error", "message": "Job not found."}), 404

    if job["status"] == "pending":
        return jsonify({"status": "pending"}), 200

    if job["status"] == "error":
        return jsonify({"status": "error", "message": job.get("error", "Unknown error")}), 200

    # status == "done"
    return jsonify({"status": "done", **job["result"]}), 200


@api_bp.route('/downloads/<filename>', methods=['GET'])
def download_excel(filename):
    downloads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'downloads')
    try:
        return send_from_directory(downloads_dir, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "File not found"}), 404


@api_bp.route('/debug', methods=['GET'])
def debug():
    """Diagnostic endpoint to test Playwright on the server."""
    import sys, platform
    test_url = request.args.get('url', 'https://example.com')
    result = {
        "python": sys.version,
        "platform": platform.platform(),
        "test_url": test_url,
        "playwright_test": None,
        "error": None
    }
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox",
                      "--disable-dev-shm-usage", "--disable-gpu", "--single-process",
                      "--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page.goto(test_url, wait_until="domcontentloaded", timeout=60000)
            title = page.title()
            html = page.content()
            img_count = page.evaluate("document.querySelectorAll('img').length")
            html_snippet = html[:2000]
            browser.close()
            result["playwright_test"] = {
                "success": True,
                "page_title": title,
                "html_length": len(html),
                "img_count": img_count,
                "html_snippet": html_snippet
            }
    except Exception as e:
        result["error"] = str(e)
    return jsonify(result)
