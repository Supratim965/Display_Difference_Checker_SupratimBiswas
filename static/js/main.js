document.addEventListener('DOMContentLoaded', () => {
    const form        = document.getElementById('analyzeForm');
    const analyzeBtn  = document.getElementById('analyzeBtn');
    const urlInput    = document.getElementById('urlInput');
    const errorAlert  = document.getElementById('errorAlert');

    const progressCard    = document.getElementById('progressCard');
    const progressText    = document.getElementById('progressText');
    const progressSubtext = document.getElementById('progressSubtext');

    const resultsCard  = document.getElementById('resultsCard');
    const totalImages  = document.getElementById('totalImages');
    const pngCount     = document.getElementById('pngCount');
    const svgCount     = document.getElementById('svgCount');
    const jpegCount    = document.getElementById('jpegCount');
    const downloadBtn  = document.getElementById('downloadBtn');

    const progressStages = [
        { main: "Waking up server...",        sub: "Free tier server is starting, please hold on" },
        { main: "Launching Browser...",        sub: "Setting up headless Chromium environment" },
        { main: "Opening Website...",          sub: "Navigating to the provided URL" },
        { main: "Scanning Images...",          sub: "Finding all image tags and sources" },
        { main: "Calculating Dimensions...",   sub: "Comparing original vs displayed sizes" },
        { main: "Generating Excel...",         sub: "Creating your professional report" },
        { main: "Still working...",            sub: "Some pages take a little longer — please wait" },
        { main: "Almost there...",             sub: "Finalizing your report" }
    ];

    let progressInterval = null;
    let pollTimer        = null;

    // -----------------------------------------------------------------------
    // Progress animation
    // -----------------------------------------------------------------------
    const startProgressSimulation = () => {
        let stage = 0;
        progressText.textContent    = progressStages[0].main;
        progressSubtext.textContent = progressStages[0].sub;

        progressInterval = setInterval(() => {
            stage = Math.min(stage + 1, progressStages.length - 1);
            progressText.textContent    = progressStages[stage].main;
            progressSubtext.textContent = progressStages[stage].sub;
        }, 6000);
    };

    const stopProgressSimulation = () => {
        if (progressInterval) { clearInterval(progressInterval); progressInterval = null; }
    };

    // -----------------------------------------------------------------------
    // UI helpers
    // -----------------------------------------------------------------------
    const resetUI = () => {
        errorAlert.classList.add('d-none');
        resultsCard.classList.add('d-none');
        progressCard.classList.remove('d-none');
        analyzeBtn.disabled = true;
        urlInput.disabled   = true;
    };

    const showError = (message) => {
        errorAlert.textContent = message;
        errorAlert.classList.remove('d-none');
        progressCard.classList.add('d-none');
        analyzeBtn.disabled = false;
        urlInput.disabled   = false;
    };

    const showSuccess = (data) => {
        progressCard.classList.add('d-none');
        resultsCard.classList.remove('d-none');
        analyzeBtn.disabled = false;
        urlInput.disabled   = false;
        totalImages.textContent = data.totalImages;
        pngCount.textContent    = data.png;
        svgCount.textContent    = data.svg;
        jpegCount.textContent   = data.jpeg;
        downloadBtn.href = '/' + data.excel;
    };

    // -----------------------------------------------------------------------
    // Fetch with timeout helper (ms)
    // -----------------------------------------------------------------------
    const fetchWithTimeout = async (url, options = {}, timeoutMs = 120000) => {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), timeoutMs);
        try {
            const response = await fetch(url, { ...options, signal: controller.signal });
            clearTimeout(id);
            return response;
        } catch (err) {
            clearTimeout(id);
            throw err;
        }
    };

    // -----------------------------------------------------------------------
    // POST /analyze with automatic retry (handles cold-start sleeps)
    // -----------------------------------------------------------------------
    const postAnalyze = async (urls, maxRetries = 3) => {
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                const response = await fetchWithTimeout('/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ urls })
                }, 120000); // 2-minute timeout per attempt

                return response;
            } catch (err) {
                console.warn(`Attempt ${attempt}/${maxRetries} failed:`, err.message);
                if (attempt < maxRetries) {
                    // Update UI to let user know we're retrying
                    progressText.textContent    = `Server waking up... (retry ${attempt}/${maxRetries - 1})`;
                    progressSubtext.textContent = 'Free tier servers sleep when idle — please wait';
                    await new Promise(r => setTimeout(r, 3000)); // wait 3s before retry
                } else {
                    throw err; // all retries exhausted
                }
            }
        }
    };

    // -----------------------------------------------------------------------
    // Polling logic
    // -----------------------------------------------------------------------
    const pollJobStatus = (jobId) => {
        let consecutiveFailures = 0;

        pollTimer = setInterval(async () => {
            try {
                const res  = await fetchWithTimeout(`/status/${jobId}`, {}, 30000);
                const data = await res.json();
                consecutiveFailures = 0;

                if (data.status === 'pending') return; // still running

                clearInterval(pollTimer);
                pollTimer = null;
                stopProgressSimulation();

                if (data.status === 'done') {
                    showSuccess(data);
                } else {
                    showError(data.message || 'An error occurred during analysis.');
                }
            } catch (err) {
                consecutiveFailures++;
                console.warn(`Poll attempt failed (${consecutiveFailures}):`, err.message);

                // After 10 consecutive poll failures (~40s) give up
                if (consecutiveFailures >= 10) {
                    clearInterval(pollTimer);
                    pollTimer = null;
                    stopProgressSimulation();
                    showError('Server is not responding. Please try again.');
                }
            }
        }, 4000);
    };

    // -----------------------------------------------------------------------
    // Form submit
    // -----------------------------------------------------------------------
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const urlText = urlInput.value.trim();
        if (!urlText) return;

        const urls = urlText.split('\n').map(u => u.trim()).filter(u => u.length > 0);
        if (urls.length === 0) return;

        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
        stopProgressSimulation();

        resetUI();
        startProgressSimulation();

        try {
            const response = await postAnalyze(urls);
            const data     = await response.json();

            if (!response.ok || data.status === 'error') {
                stopProgressSimulation();
                showError(data.message || 'Failed to start analysis.');
                return;
            }

            // Kick off status polling
            pollJobStatus(data.job_id);

        } catch (error) {
            console.error('Submit error:', error);
            stopProgressSimulation();
            showError('Server could not be reached after multiple attempts. Please try again in a moment.');
        }
    });
});
