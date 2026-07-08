# Image Checkpoints

Image Checkpoints is a production-ready Flask web application that analyzes webpages and extracts PNG, SVG, and JPEG image properties, generating a detailed Excel report.

## Features

- **Automated Headless Browsing**: Uses Playwright to load full webpages, including lazy-loaded content.
- **Image Auditing**: Extracts dimensions (displayed vs. original), alt text, lazy-loading status, responsive attributes, and identifies broken or duplicate images.
- **Professional Reporting**: Generates heavily-formatted Excel (.xlsx) files with bold headers, hyperlink URLs, and alternate row colors.
- **Modern UI**: Clean and responsive frontend built with Bootstrap 5.

## Project Structure

```
image-checkpoints/
├── app.py                      # Flask application entry point
├── requirements.txt            # Python dependencies
├── routes/
│   └── api.py                  # API endpoints
├── services/
│   ├── image_extractor.py      # Playwright automation logic
│   ├── excel_generator.py      # Openpyxl logic for Excel reporting
│   ├── url_utils.py            # URL validation and resolution
│   └── logger.py               # Centralized logging config
├── templates/
│   └── index.html              # Frontend UI
├── static/
│   ├── css/
│   │   └── style.css           # Custom styles
│   └── js/
│       └── main.js             # AJAX and UI logic
├── downloads/                  # Generated Excel reports
└── logs/                       # Application logs
```

## Installation

### Prerequisites
- Python 3.12+

### 1. Virtual Environment Setup

Open your terminal and navigate to the `image-checkpoints` directory, then run:

```bash
python -m venv venv
```

Activate the virtual environment:
- Windows: `.\venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Playwright Browsers

```bash
playwright install chromium
```

## Running the Application

Ensure your virtual environment is activated, then run:

```bash
python app.py
```

The application will start on `http://localhost:5000`.

## API Documentation

### `POST /analyze`

Analyzes a URL and generates an Excel report.

**Request:**
```json
{
  "url": "https://example.com"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "totalImages": 12,
  "png": 5,
  "svg": 2,
  "jpeg": 5,
  "excel": "downloads/Image_Checkpoints.xlsx"
}
```

### `GET /downloads/<filename>`

Returns the generated Excel file.

## Troubleshooting

- **No Images Found**: The target website might block automated browsers. 
- **Playwright Errors**: Ensure you have run `playwright install chromium`. 
