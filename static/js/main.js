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

    // Progress stage messages shown while polling
    const progressStages = [
        { main: "Launching Browser...",      sub: "Setting up headless environment" },
        { main: "Opening Website...",         sub: "Navigating to the provided URL" },
        { main: "Scanning Images...",         sub: "Finding all image tags and sources" },
        { main: "Calculating Dimensions...",  sub: "Comparing original vs display sizes" },
        { main: "Generating Excel...",        sub: "Creating your professional report" },
        { main: "Still working...",           sub: "Some pages take a little longer — please wait" },
        { main: "Almost there...",            sub: "Finalizing your report" }
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
            stage++;
            if (stage < progressStages.length) {
                progressText.textContent    = progressStages[stage].main;
                progressSubtext.textContent = progressStages[stage].sub;
            }
            // After the last stage just stop cycling — don't clear the interval
            // so the last message stays visible.
        }, 5000);
    };

    const stopProgressSimulation = () => {
        if (progressInterval) {
            clearInterval(progressInterval);
            progressInterval = null;
        }
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
    // Polling logic
    // -----------------------------------------------------------------------
    const pollJobStatus = (jobId) => {
        // Poll every 4 seconds
        pollTimer = setInterval(async () => {
            try {
                const res  = await fetch(`/status/${jobId}`);
                const data = await res.json();

                if (data.status === 'pending') {
                    // Still running — keep polling
                    return;
                }

                // Terminal state — stop polling
                clearInterval(pollTimer);
                pollTimer = null;
                stopProgressSimulation();

                if (data.status === 'done') {
                    showSuccess(data);
                } else {
                    // status === 'error'
                    showError(data.message || 'An error occurred during analysis.');
                }

            } catch (err) {
                // Network blip on the status check — keep retrying, do NOT surface error yet
                console.warn('Status poll failed, will retry:', err);
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

        // Clear any previous poll
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
        stopProgressSimulation();

        resetUI();
        startProgressSimulation();

        try {
            // This request returns almost immediately with a job_id
            const response = await fetch('/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls })
            });

            const data = await response.json();

            if (!response.ok || data.status === 'error') {
                stopProgressSimulation();
                showError(data.message || 'Failed to start analysis.');
                return;
            }

            // Start polling for the result
            pollJobStatus(data.job_id);

        } catch (error) {
            console.error('Submit error:', error);
            stopProgressSimulation();
            showError('Could not reach the server. Please check your connection and try again.');
        }
    });
});
