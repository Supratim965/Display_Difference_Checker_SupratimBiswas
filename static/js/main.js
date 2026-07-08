document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('analyzeForm');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const urlInput = document.getElementById('urlInput');
    const errorAlert = document.getElementById('errorAlert');
    
    const progressCard = document.getElementById('progressCard');
    const progressText = document.getElementById('progressText');
    const progressSubtext = document.getElementById('progressSubtext');
    
    const resultsCard = document.getElementById('resultsCard');
    const totalImages = document.getElementById('totalImages');
    const pngCount = document.getElementById('pngCount');
    const svgCount = document.getElementById('svgCount');
    const jpegCount = document.getElementById('jpegCount');
    const downloadBtn = document.getElementById('downloadBtn');

    // Simulate progress messages since the backend is synchronous
    const progressStages = [
        { main: "Launching Browser...", sub: "Setting up headless environment" },
        { main: "Opening Website...", sub: "Navigating to the provided URL" },
        { main: "Scanning Images...", sub: "Finding all image tags and sources" },
        { main: "Calculating Dimensions...", sub: "Comparing original vs display sizes" },
        { main: "Generating Excel...", sub: "Creating your professional report" }
    ];

    let progressInterval;

    const startProgressSimulation = () => {
        let stage = 0;
        
        // Initial setup
        progressText.textContent = progressStages[0].main;
        progressSubtext.textContent = progressStages[0].sub;
        
        progressInterval = setInterval(() => {
            stage++;
            if (stage < progressStages.length) {
                progressText.textContent = progressStages[stage].main;
                progressSubtext.textContent = progressStages[stage].sub;
            } else {
                clearInterval(progressInterval);
                // Hold at the last stage if the API is still running
                progressText.textContent = "Finalizing...";
                progressSubtext.textContent = "Almost there!";
            }
        }, 3000); // Change stage every 3 seconds
    };

    const stopProgressSimulation = () => {
        if (progressInterval) {
            clearInterval(progressInterval);
        }
    };

    const resetUI = () => {
        errorAlert.classList.add('d-none');
        resultsCard.classList.add('d-none');
        progressCard.classList.remove('d-none');
        analyzeBtn.disabled = true;
        urlInput.disabled = true;
    };

    const showError = (message) => {
        errorAlert.textContent = message;
        errorAlert.classList.remove('d-none');
        progressCard.classList.add('d-none');
        analyzeBtn.disabled = false;
        urlInput.disabled = false;
    };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const urlText = urlInput.value.trim();
        if (!urlText) return;
        
        // Split by newline and filter empty lines
        const urls = urlText.split('\n').map(u => u.trim()).filter(u => u.length > 0);
        if (urls.length === 0) return;

        resetUI();
        startProgressSimulation();

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ urls: urls })
            });

            const data = await response.json();
            stopProgressSimulation();

            if (!response.ok) {
                showError(data.message || 'An error occurred during analysis.');
                return;
            }

            // Success
            progressCard.classList.add('d-none');
            resultsCard.classList.remove('d-none');
            analyzeBtn.disabled = false;
            urlInput.disabled = false;

            // Populate counts
            totalImages.textContent = data.totalImages;
            pngCount.textContent = data.png;
            svgCount.textContent = data.svg;
            jpegCount.textContent = data.jpeg;

            // Update download button
            downloadBtn.href = '/' + data.excel;
            
        } catch (error) {
            console.error("Error:", error);
            stopProgressSimulation();
            showError("Network error or server unavailable. Please try again.");
        }
    });
});
