from flask import Blueprint, request, jsonify, send_from_directory, current_app
import os
from services.url_utils import is_valid_url
from services.image_extractor import extract_image_data
from services.excel_generator import generate_excel_report
from services.logger import logger

api_bp = Blueprint('api', __name__)

@api_bp.route('/analyze', methods=['POST'])
def analyze_url():
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
                aggregated_results["png"] += extraction_results["png"]
                aggregated_results["svg"] += extraction_results["svg"]
                aggregated_results["jpeg"] += extraction_results["jpeg"]
                # Optionally add a 'Page URL' attribute to the images if we wanted to distinguish, 
                # but we'll just merge them for now as per the existing structure.
                aggregated_results["images"].extend(extraction_results["images"])
            except Exception as e:
                logger.error(f"Analysis failed for specific URL {u}: {str(e)}")
                # Continue with the next URL even if one fails
        
        if aggregated_results["totalImages"] == 0:
            return jsonify({
                "status": "error", 
                "message": "No PNG, SVG, or JPEG images found on the provided page(s)."
            }), 404
            
        # Generate Excel
        excel_filename = "Image_Checkpoints.xlsx"
        generate_excel_report(aggregated_results["images"], excel_filename)
        
        return jsonify({
            "status": "success",
            "totalImages": aggregated_results["totalImages"],
            "png": aggregated_results["png"],
            "svg": aggregated_results["svg"],
            "jpeg": aggregated_results["jpeg"],
            "excel": f"downloads/{excel_filename}"
        })
        
    except Exception as e:
        logger.error(f"Analysis failed globally: {str(e)}")
        return jsonify({"status": "error", "message": "An error occurred during analysis. Please try again."}), 500

@api_bp.route('/downloads/<filename>', methods=['GET'])
def download_excel(filename):
    downloads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'downloads')
    try:
        return send_from_directory(downloads_dir, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"status": "error", "message": "File not found"}), 404
