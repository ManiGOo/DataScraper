let currentTaskId = null;
let pollInterval = null;

function setQuery(queryText) {
    const queryInput = document.getElementById('queryInput');
    queryInput.value = queryText;
    queryInput.focus();
    queryInput.style.borderColor = 'var(--accent-cyan)';
    setTimeout(() => { queryInput.style.borderColor = ''; }, 1200);
}

async function generateAiQuery() {
    const promptInput = document.getElementById('aiPromptInput');
    const btnAiGenerate = document.getElementById('btnAiGenerate');
    const prompt = promptInput.value.trim();

    if (!prompt) {
        alert("Please enter a plain English description for the AI Assistant.");
        return;
    }

    const origText = btnAiGenerate.innerHTML;
    btnAiGenerate.disabled = true;
    btnAiGenerate.innerHTML = `<span>Generating...</span>`;

    try {
        const response = await fetch('/api/generate-query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: prompt })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to generate AI query.");
        }

        const data = await response.json();
        if (data.query) {
            setQuery(data.query);
        }
    } catch (err) {
        alert("AI Assistant Error: " + err.message);
    } finally {
        btnAiGenerate.disabled = false;
        btnAiGenerate.innerHTML = origText;
    }
}

async function startScraping() {
    const query = document.getElementById('queryInput').value.trim();
    const maxResults = parseInt(document.getElementById('maxResults').value);

    if (!query) {
        alert("Please enter a valid GitHub search query.");
        return;
    }

    // Reset UI State
    const btnScrape = document.getElementById('btnScrape');
    const statusText = document.getElementById('statusText');
    const statusDot = document.querySelector('.status-dot');
    const progressSection = document.getElementById('progressSection');
    const resultsSection = document.getElementById('resultsSection');
    const terminalLog = document.getElementById('terminalLog');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');

    btnScrape.disabled = true;
    btnScrape.style.opacity = '0.6';
    statusText.innerText = "Scraping In Progress";
    statusDot.classList.add('active');

    progressSection.classList.remove('hidden');
    resultsSection.classList.add('hidden');

    progressBar.style.width = '0%';
    progressPercent.innerText = '0%';
    terminalLog.innerHTML = `<div class="log-line text-muted">[System] Initiating scrape task for query: "${query}"...</div>`;

    try {
        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query, max_results: maxResults })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to start scraping task.");
        }

        const data = await response.json();
        currentTaskId = data.task_id;
        
        pollInterval = setInterval(checkStatus, 1000);

    } catch (err) {
        alert("Error starting scraper: " + err.message);
        btnScrape.disabled = false;
        btnScrape.style.opacity = '1';
        statusText.innerText = "System Ready";
        statusDot.classList.remove('active');
        progressSection.classList.add('hidden');
    }
}

async function checkStatus() {
    if (!currentTaskId) return;

    try {
        const response = await fetch(`/api/status/${currentTaskId}`);
        if (!response.ok) return;

        const data = await response.json();

        const progressBar = document.getElementById('progressBar');
        const progressPercent = document.getElementById('progressPercent');
        const terminalLog = document.getElementById('terminalLog');

        progressBar.style.width = `${data.progress}%`;
        progressPercent.innerText = `${data.progress}%`;

        if (data.logs && data.logs.length > 0) {
            terminalLog.innerHTML = data.logs.map(log => `<div class="log-line">> ${log}</div>`).join('');
            terminalLog.scrollTop = terminalLog.scrollHeight;
        }

        if (data.status === 'completed') {
            clearInterval(pollInterval);
            finishScraping(data);
        } else if (data.status === 'failed') {
            clearInterval(pollInterval);
            alert("Scraping task failed: " + (data.error || "Unknown error"));
            resetUI();
        }
    } catch (err) {
        console.error("Polling error:", err);
    }
}

function finishScraping(data) {
    const btnScrape = document.getElementById('btnScrape');
    const statusText = document.getElementById('statusText');
    const statusDot = document.querySelector('.status-dot');
    const resultsSection = document.getElementById('resultsSection');
    const tableBody = document.getElementById('tableBody');
    const summaryStats = document.getElementById('summaryStats');

    btnScrape.disabled = false;
    btnScrape.style.opacity = '1';
    statusText.innerText = "Scrape Completed";
    statusDot.classList.remove('active');

    resultsSection.classList.remove('hidden');

    const results = data.results || [];
    const emailsCount = results.filter(r => r.Email && r.Email !== 'N/A').length;
    const linkedinCount = results.filter(r => r["LinkedIn URL"] && r["LinkedIn URL"] !== 'N/A').length;

    summaryStats.innerText = `Gathered ${results.length} profile(s) | Emails: ${emailsCount} | LinkedIn: ${linkedinCount}`;

    if (results.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-secondary);">No profile results found for query.</td></tr>`;
        return;
    }

    tableBody.innerHTML = results.map((row, idx) => {
        const name = row.Name || 'N/A';
        const emailHtml = (row.Email && row.Email !== 'N/A') 
            ? `<span class="badge-email">${row.Email}</span>` 
            : `<span class="badge-na">N/A</span>`;

        const linkedinHtml = (row["LinkedIn URL"] && row["LinkedIn URL"] !== 'N/A') 
            ? `<a href="${row["LinkedIn URL"]}" target="_blank" class="badge-linkedin">View Profile ↗</a>` 
            : `<span class="badge-na">N/A</span>`;

        const githubHtml = `<a href="${row["GitHub URL"]}" target="_blank" class="link-github">${row["GitHub URL"]}</a>`;
        const repos = row.Repositories || '0';

        return `
            <tr>
                <td>${idx + 1}</td>
                <td><strong>${name}</strong></td>
                <td>${emailHtml}</td>
                <td>${linkedinHtml}</td>
                <td>${githubHtml}</td>
                <td>${repos}</td>
            </tr>
        `;
    }).join('');
}

function resetUI() {
    const btnScrape = document.getElementById('btnScrape');
    const statusText = document.getElementById('statusText');
    const statusDot = document.querySelector('.status-dot');

    btnScrape.disabled = false;
    btnScrape.style.opacity = '1';
    statusText.innerText = "System Ready";
    statusDot.classList.remove('active');
}

function downloadFile(fileFormat) {
    if (!currentTaskId) {
        alert("No active or completed scrape task found.");
        return;
    }
    window.location.href = `/api/download/${currentTaskId}/${fileFormat}`;
}
