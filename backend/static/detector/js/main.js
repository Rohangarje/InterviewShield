const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas ? canvas.getContext('2d') : null;
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const logList = document.getElementById('logList');
const kpiGrid = document.getElementById('kpiGrid');
const pieCtx = document.getElementById('pieChart')?.getContext('2d');
const barCtx = document.getElementById('barChart')?.getContext('2d');
const lineCtx = document.getElementById('lineChart')?.getContext('2d');
const lastUpdateEl = document.getElementById('lastUpdate');
const dataCountEl = document.getElementById('dataCount');

let detectionInterval = null;
let isDetecting = false;
let analyticsInterval = null;
let pieChart, barChart, lineChart;

// ================= LIVE DETECTION (PRESERVED) =================
let captureCanvas = null;
let captureCtx = null;

async function initCamera() {
    if (!video) return;
    try {
        console.log('Initializing camera...');
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { 
                facingMode: 'user', 
                width: { ideal: 640 }, 
                height: { ideal: 480 },
                frameRate: { ideal: 30 }
            } 
        });
        video.srcObject = stream;
        video.onloadedmetadata = () => {
            video.play().catch(err => {
                console.error('Video play error:', err);
                showToast('Camera play error: ' + err.message, 'error');
            });
            // Create a small offscreen canvas for frame capture (faster encoding)
            if (!captureCanvas) {
                captureCanvas = document.createElement('canvas');
                captureCanvas.width = 320;
                captureCanvas.height = 240;
                captureCtx = captureCanvas.getContext('2d', { willReadFrequently: true });
            }
            showToast('Camera ready!', 'success');
            console.log('Camera initialized:', video.videoWidth, 'x', video.videoHeight);
        };
    } catch (err) {
        console.error('Camera access error:', err);
        const errorMsg = err.name === 'NotAllowedError' 
            ? 'Camera permission denied. Please allow camera access in browser settings.'
            : err.name === 'NotFoundError'
            ? 'No camera found on this device.'
            : 'Camera access failed: ' + err.message;
        showToast(errorMsg, 'error');
    }
}

function captureFrame() {
    // Use the small offscreen canvas for fast capture + encoding
    if (!captureCtx || !video || video.readyState < 2) return null;
    captureCtx.drawImage(video, 0, 0, 320, 240);
    return captureCanvas.toDataURL('image/jpeg', 0.5);
}

function getCsrfToken() {
    const name = 'csrftoken';
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [key, value] = cookie.trim().split('=');
        if (key === name) return decodeURIComponent(value);
    }
    return '';
}

async function detectFaces() {
    const imgBase64 = captureFrame();
    if (!imgBase64) return;
    
    const csrfToken = getCsrfToken();
    try {
        const response = await fetch('/api/detect/', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            credentials: 'same-origin',
            body: JSON.stringify({ image: imgBase64 })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({error: `Server error: ${response.status}`}));
            throw new Error(errorData.error || `Server error: ${response.status}`);
        }
        
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            throw new Error('Invalid response type from server');
        }
        
        const data = await response.json();
        
        if (data.error) {
            console.error('Detection error:', data.error);
            showToast(`Detection error: ${data.error}`, 'error');
            return;
        }
        
        updateStatus(data);
        addLog(data);
    } catch (err) {
        console.error('Detection error:', err);
        showToast(`Detection failed: ${err.message}`, 'error');
    }
}

function updateStatus(data) {
    const faceCountEl = document.getElementById('faceCount');
    const statusCard = document.getElementById('statusCard');
    const statusMsgEl = document.getElementById('statusMessage');
    
    if (faceCountEl) faceCountEl.textContent = data.face_count;
    if (statusCard) statusCard.className = `status-card status-${data.risk_score || data.face_status}`;
    if (statusMsgEl) statusMsgEl.textContent = data.alert;
    
    if (data.phone_detected) {
        showToast(`Mobile detected! Conf: ${data.phone_confidence}`, 'error');
    } else if (data.face_status !== 'normal') {
        showToast(data.alert, 'error');
    }
}

function addLog(data) {
    if (!logList) return;
    const li = document.createElement('li');
    li.className = data.risk_score === 'high' ? 'log-alert log-item' : 'log-normal log-item';
    li.innerHTML = `<strong>${new Date().toLocaleTimeString()}</strong>: ${data.alert} (Faces: ${data.face_count}${data.phone_detected ? ', Mobile' : ''})`;
    logList.insertBefore(li, logList.firstChild);
    
    while (logList.children.length > 10) logList.removeChild(logList.lastChild);
}

function updateButtonVisibility(detecting) {
    if (startBtn) {
        startBtn.style.display = detecting ? 'none' : 'flex';
        startBtn.disabled = detecting;
    }
    if (stopBtn) {
        stopBtn.style.display = detecting ? 'flex' : 'none';
        stopBtn.disabled = !detecting;
    }
}

if (startBtn) {
    startBtn.onclick = () => {
        if (!isDetecting) {
            isDetecting = true;
            updateButtonVisibility(true);
            detectFaces();
            detectionInterval = setInterval(detectFaces, 2000);
            showToast('Detection started');
        }
    };
}

if (stopBtn) {
    stopBtn.onclick = () => {
        isDetecting = false;
        clearInterval(detectionInterval);
        updateButtonVisibility(false);
        showToast('Detection stopped');
    };
}

// ================= ANALYTICS DASHBOARD =================
async function fetchAnalytics() {
    try {
        const response = await fetch('/api/analytics/', {
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({error: `Server error: ${response.status}`}));
            throw new Error(errorData.error || `Server error: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update KPIs
        updateKPIs(data.summary);
        
        // Update charts
        updateCharts(data);
        
        // Update metadata
        if (lastUpdateEl) lastUpdateEl.textContent = `Updated: ${new Date(data.updated).toLocaleString()}`;
        if (dataCountEl) dataCountEl.textContent = data.summary.total_sessions;
        
        showToast('Dashboard refreshed', 'success');
    } catch (err) {
        console.error('Analytics error:', err);
        showToast('Failed to load analytics', 'error');
    }
}

function updateKPIs(summary) {
    if (!kpiGrid) return;
    
    const kpis = [
        { class: 'total', icon: 'fas fa-sitemap', label: 'Total Sessions', value: summary.total_sessions },
        { class: 'normal', icon: 'fas fa-check-circle', label: 'Normal', value: summary.normal },
        { class: 'alert', icon: 'fas fa-user-slash', label: 'No Face', value: summary.no_face },
        { class: 'phone', icon: 'fas fa-mobile-alt', label: 'Mobile Detected', value: summary.mobile_detected },
        { class: 'cheating', icon: 'fas fa-exclamation-triangle', label: 'Cheating %', value: `${summary.cheating_pct}%` },
        { class: 'total', icon: 'fas fa-chart-line', label: 'Avg Phone Conf', value: summary.avg_phone_conf }
    ];
    
    kpiGrid.innerHTML = kpis.map(kpi => `
        <div class="kpi-card ${kpi.class}">
            <div class="kpi-icon">
                <i class="${kpi.icon}"></i>
            </div>
            <div class="kpi-value">${kpi.value}</div>
            <div class="kpi-label">${kpi.label}</div>
    `).join('');
}

function updateCharts(data) {
    // Pie Chart
    if (pieCtx && pieChart) pieChart.destroy();
    if (pieCtx) {
        pieChart = new Chart(pieCtx, {
            type: 'pie',
            data: {
                labels: data.pie.labels,
                datasets: [{
                    data: data.pie.data,
                    backgroundColor: ['#22c55e', '#ef4444', '#f97316', '#6b7280'],
                    borderWidth: 2,
                    borderColor: '#1e293b'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom', labels: { color: '#e2e8f0' } } },
                animation: { duration: 1000 }
            }
        });
    }
    
    // Bar Chart
    if (barCtx && barChart) barChart.destroy();
    if (barCtx) {
        barChart = new Chart(barCtx, {
            type: 'bar',
            data: {
                labels: data.bar.labels,
                datasets: [{
                    label: 'Counts',
                    data: data.bar.data,
                    backgroundColor: 'rgba(96, 165, 250, 0.7)',
                    borderColor: '#60a5fa',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, ticks: { color: '#e2e8f0' }, grid: { color: 'rgba(255,255,255,0.1)' } },
                    x: { ticks: { color: '#e2e8f0' }, grid: { color: 'rgba(255,255,255,0.1)' } }
                },
                plugins: { legend: { labels: { color: '#e2e8f0' } } },
                animation: { duration: 1000 }
            }
        });
    }
    
    // Line Chart
    if (lineCtx && lineChart) lineChart.destroy();
    if (lineCtx) {
        lineChart = new Chart(lineCtx, {
            type: 'line',
            data: {
                labels: data.line.labels,
                datasets: [
                    { label: 'Normal', data: data.line.datasets.normal, borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.1)', tension: 0.4, fill: true },
                    { label: 'No Face', data: data.line.datasets.no_face, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', tension: 0.4, fill: true },
                    { label: 'Mobile', data: data.line.datasets.mobile, borderColor: '#f97316', backgroundColor: 'rgba(249,115,22,0.1)', tension: 0.4, fill: true }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, ticks: { color: '#e2e8f0' }, grid: { color: 'rgba(255,255,255,0.1)' } },
                    x: { ticks: { color: '#e2e8f0' }, grid: { color: 'rgba(255,255,255,0.1)' } }
                },
                plugins: { legend: { labels: { color: '#e2e8f0' } } },
                animation: { duration: 1500 }
            }
        });
    }
}

// ================= UTILS =================
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    setTimeout(() => toast.classList.remove('show'), 4000);
}

// ================= INIT =================
let refreshTimer;
function startAutoRefresh() {
    // Avoid multiple timers
    if (refreshTimer) clearInterval(refreshTimer);
    fetchAnalytics(); // Initial load
    refreshTimer = setInterval(fetchAnalytics, 30000); // 30s
}

function stopAutoRefresh() {
    clearInterval(refreshTimer);
    refreshTimer = null;
}

// Global init
document.addEventListener('DOMContentLoaded', () => {
    initCamera();
    startAutoRefresh();
    
    // Sidebar toggle
    window.toggleSidebar = () => document.getElementById('sidebar')?.classList.toggle('open');
    
    // Refresh button
    document.getElementById('refreshBtn')?.addEventListener('click', fetchAnalytics);
    
    // Resume upload
    setupResumeUpload();
    
    // Tab switch detection
    setupTabSwitchDetection();
    
    // Load interview data on init (restores active session state)
    loadInterviews();
    loadResume();
});

// ================= TAB SWITCH DETECTION =================
function setupTabSwitchDetection() {
    document.addEventListener('visibilitychange', () => {
        if (!activeInterviewId) return; // Only during interviews
        
        if (document.hidden) {
            // User switched away from the tab
            const logData = {
                face_status: 'tab_switched',
                face_count: 0,
                phone_detected: false,
                phone_confidence: 0,
                risk_score: 'high',
                alert: '⚠️ Tab Switched - User left the page!',
                indicators: ['Tab Switch']
            };
            
            // Add to live log
            addLog(logData);
            
            // Show toast
            showToast('Warning: Tab switched during interview!', 'error');
            
            // Send to backend
            sendTabSwitchEvent();
        } else {
            // User returned
            showToast('Tab focus restored', 'success');
        }
    });
    
    // Also detect window blur/focus for better coverage
    window.addEventListener('blur', () => {
        if (!activeInterviewId) return;
        window._interviewBlurred = true;
    });
    
    window.addEventListener('focus', () => {
        if (!activeInterviewId) return;
        if (window._interviewBlurred) {
            window._interviewBlurred = false;
            const logData = {
                face_status: 'tab_returned',
                face_count: 0,
                phone_detected: false,
                phone_confidence: 0,
                risk_score: 'low',
                alert: 'Tab focus restored',
                indicators: []
            };
            addLog(logData);
        }
    });
}

async function sendTabSwitchEvent() {
    if (!activeInterviewId) return;
    
    try {
        await fetch('/api/detect/', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            credentials: 'same-origin',
            body: JSON.stringify({ 
                image: 'data:image/jpeg;base64,TAB_SWITCH',
                event_type: 'tab_switch',
                active_interview_id: activeInterviewId
            })
        });
    } catch (err) {
        console.error('Tab switch log failed:', err);
    }
}

// ================= INTERVIEW MANAGEMENT =================
let activeInterviewId = null;
let interviewTimerInterval = null;
let interviewStartTime = null;

async function startInterview() {
    try {
        const response = await fetch('/api/interview/start/', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({error: `Server error: ${response.status}`}));
            throw new Error(errorData.error || `Server error: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            showToast(data.error, 'error');
            return;
        }
        
        activeInterviewId = data.interview_id;
        interviewStartTime = new Date(data.start_time);
        
        document.getElementById('noActiveInterview').style.display = 'none';
        document.getElementById('activeInterview').style.display = 'block';
        document.getElementById('activeInterviewId').textContent = activeInterviewId;
        
        updateLiveSessionCard(true);
        startInterviewTimer();
        showToast('Interview started! Go to Live Detection to begin proctoring.', 'success');
        loadInterviews();
    } catch (err) {
        console.error('Start interview error:', err);
        showToast('Failed to start interview: ' + err.message, 'error');
    }
}

async function endInterview() {
    if (!activeInterviewId) {
        showToast('No active interview', 'error');
        return;
    }
    
    if (!confirm('Are you sure you want to end this interview? A report will be generated.')) {
        return;
    }
    
    try {
        const response = await fetch('/api/interview/end/', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({error: `Server error: ${response.status}`}));
            throw new Error(errorData.error || `Server error: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            showToast(data.error, 'error');
            return;
        }
        
        stopInterviewTimer();
        activeInterviewId = null;
        interviewStartTime = null;
        
        document.getElementById('noActiveInterview').style.display = 'block';
        document.getElementById('activeInterview').style.display = 'none';
        document.getElementById('interviewTimer').textContent = '00:00';
        updateLiveSessionCard(false);
        
        showToast(`Interview ended! Report: ${data.report.overall_risk.toUpperCase()} risk`, 'success');
        loadInterviews();
        
        // Show report modal
        if (data.report) {
            await viewReport(data.interview_id);
        }
    } catch (err) {
        console.error('End interview error:', err);
        showToast('Failed to end interview: ' + err.message, 'error');
    }
}

function startInterviewTimer() {
    stopInterviewTimer();
    interviewTimerInterval = setInterval(() => {
        if (!interviewStartTime) return;
        const elapsed = Math.floor((Date.now() - interviewStartTime.getTime()) / 1000);
        const mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
        const secs = (elapsed % 60).toString().padStart(2, '0');
        const timeStr = `${mins}:${secs}`;
        const timerEl = document.getElementById('interviewTimer');
        const liveTimerEl = document.getElementById('liveInterviewTimer');
        if (timerEl) timerEl.textContent = timeStr;
        if (liveTimerEl) liveTimerEl.textContent = timeStr;
    }, 1000);
}

function stopInterviewTimer() {
    if (interviewTimerInterval) {
        clearInterval(interviewTimerInterval);
        interviewTimerInterval = null;
    }
}

function updateLiveSessionCard(show) {
    const card = document.getElementById('liveSessionCard');
    const transCard = document.getElementById('transcriptionCard');
    const idEl = document.getElementById('liveInterviewId');
    if (card) card.style.display = show ? 'block' : 'none';
    if (transCard) transCard.style.display = show ? 'block' : 'none';
    if (idEl && activeInterviewId) idEl.textContent = activeInterviewId;
    
    // Stop transcription when interview ends
    if (!show && isTranscribing) {
        stopTranscription();
        const btn = document.getElementById('toggleTranscriptionBtn');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-microphone"></i> Start Transcription';
            btn.classList.remove('btn-danger');
            btn.classList.add('btn-primary');
        }
    }
}

function switchToLive() {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    document.querySelector('.nav-item[data-tab="live"]')?.classList.add('active');
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById('liveTab').classList.add('active');
    document.getElementById('pageTitle').textContent = 'Live Proctoring Dashboard';
    initCamera();
    updateLiveSessionCard(true);
}

async function endInterviewFromLive() {
    await endInterview();
    updateLiveSessionCard(false);
}

async function loadInterviews() {
    const listEl = document.getElementById('interviewList');
    if (!listEl) return;
    
    try {
        const response = await fetch('/api/interview/list/', {
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({error: `Server error: ${response.status}`}));
            throw new Error(errorData.error || `Server error: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            listEl.innerHTML = `<p style="text-align:center;opacity:0.6;padding:2rem;">${data.error}</p>`;
            return;
        }
        
        if (!data.interviews || data.interviews.length === 0) {
            listEl.innerHTML = `<p style="text-align:center;opacity:0.6;padding:2rem;">No interviews yet. Start your first one!</p>`;
            return;
        }
        
        // Check for active interview
        const active = data.interviews.find(i => i.status === 'active');
        if (active && !activeInterviewId) {
            activeInterviewId = active.id;
            interviewStartTime = new Date(active.start_time);
            document.getElementById('noActiveInterview').style.display = 'none';
            document.getElementById('activeInterview').style.display = 'block';
            document.getElementById('activeInterviewId').textContent = activeInterviewId;
            updateLiveSessionCard(true);
            startInterviewTimer();
        }
        
        listEl.innerHTML = data.interviews.map(interview => {
            const date = new Date(interview.start_time);
            const dateStr = date.toLocaleDateString();
            const timeStr = date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            const duration = interview.duration_seconds ? `${Math.floor(interview.duration_seconds / 60)}m ${interview.duration_seconds % 60}s` : 'In progress';
            
            let itemClass = 'interview-item';
            if (interview.status === 'active') itemClass += ' active-session';
            else if (interview.status === 'completed') itemClass += ' completed';
            if (interview.overall_risk === 'high') itemClass += ' high-risk';
            
            let riskBadge = '';
            if (interview.overall_risk) {
                const badgeClass = `badge-${interview.overall_risk}`;
                riskBadge = `<span class="status-badge ${badgeClass}">${interview.overall_risk.toUpperCase()}</span>`;
            }
            
            let actions = '';
            if (interview.status === 'completed' && interview.has_report) {
                actions = `
                    <div class="interview-actions">
                        <button class="btn btn-sm btn-primary" onclick="viewReport(${interview.id})">
                            <i class="fas fa-file-alt"></i> View Report
                        </button>
                        <button class="btn btn-sm btn-secondary" onclick="downloadReport(${interview.id})">
                            <i class="fas fa-download"></i> Download
                        </button>
                    </div>
                `;
            }
            
            return `
                <div class="${itemClass}">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
                        <strong>Interview #${interview.id}</strong>
                        <div style="display:flex;gap:0.5rem;align-items:center;">
                            ${interview.status === 'active' ? '<span class="status-badge badge-active">ACTIVE</span>' : ''}
                            ${riskBadge}
                        </div>
                    </div>
                    <div style="opacity:0.8;font-size:0.9rem;">
                        <i class="fas fa-calendar"></i> ${dateStr} at ${timeStr}
                        <span style="margin-left:1rem;"><i class="fas fa-clock"></i> ${duration}</span>
                        ${interview.has_resume ? '<span style="margin-left:1rem;color:#a855f7;"><i class="fas fa-file"></i> Resume</span>' : ''}
                    </div>
                    ${interview.cheating_percentage !== null ? `<div style="margin-top:0.5rem;font-size:0.85rem;">Cheating: ${interview.cheating_percentage}% | Detections: ${interview.duration_seconds > 0 ? Math.round(interview.duration_seconds / 2) : 0}</div>` : ''}
                    ${actions}
                </div>
            `;
        }).join('');
    } catch (err) {
        console.error('Load interviews error:', err);
        listEl.innerHTML = `<p style="text-align:center;opacity:0.6;padding:2rem;">Failed to load interviews: ${err.message}</p>`;
    }
}

async function viewReport(interviewId) {
    try {
        const response = await fetch(`/api/interview/${interviewId}/report/`, {
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({error: `Server error: ${response.status}`}));
            throw new Error(errorData.error || `Server error: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            showToast(data.error, 'error');
            return;
        }
        
        const reportBody = document.getElementById('reportBody');
        if (data.report && data.report.html) {
            reportBody.innerHTML = data.report.html;
        } else {
            reportBody.innerHTML = `
                <div style="text-align:center;padding:3rem;">
                    <h3 style="color:#ef4444;margin-bottom:1rem;">Report Not Available</h3>
                    <p>No detailed report was generated for this interview.</p>
                </div>
            `;
        }
        
        document.getElementById('reportModal').classList.add('active');
    } catch (err) {
        console.error('View report error:', err);
        showToast('Failed to load report: ' + err.message, 'error');
    }
}

function closeReportModal() {
    document.getElementById('reportModal').classList.remove('active');
}

async function downloadReport(interviewId) {
    try {
        const response = await fetch(`/api/interview/${interviewId}/report/`, {
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({error: `Server error: ${response.status}`}));
            throw new Error(errorData.error || `Server error: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error || !data.report) {
            showToast('Report not available', 'error');
            return;
        }
        
        // Create a blob and download
        const htmlContent = data.report.html || `<html><body><h1>Interview Report #${interviewId}</h1><pre>${JSON.stringify(data.report.data, null, 2)}</pre></body></html>`;
        const blob = new Blob([htmlContent], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `interview-report-${interviewId}.html`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast('Report downloaded!', 'success');
    } catch (err) {
        console.error('Download report error:', err);
        showToast('Failed to download report: ' + err.message, 'error');
    }
}

// ================= RESUME UPLOAD =================
function setupResumeUpload() {
    const fileInput = document.getElementById('resumeFile');
    if (!fileInput) return;
    
    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        const formData = new FormData();
        formData.append('resume', file);
        
        try {
            showToast('Uploading resume...', 'success');
            const response = await fetch('/api/resume/upload/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken()
                },
                credentials: 'same-origin',
                body: formData
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({error: `Server error: ${response.status}`}));
                throw new Error(errorData.error || `Server error: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                showToast(data.error, 'error');
                return;
            }
            
            showToast('Resume uploaded successfully!', 'success');
            updateResumeUI(data.filename, data.url);
        } catch (err) {
            console.error('Upload error:', err);
            showToast('Failed to upload resume: ' + err.message, 'error');
        } finally {
            // Clear input so the same file can be selected again
            fileInput.value = '';
        }
    });
}

function updateResumeUI(filename, url) {
    const uploadArea = document.getElementById('resumeUploadArea');
    const info = document.getElementById('resumeInfo');
    const filenameEl = document.getElementById('resumeFilename');
    const linkEl = document.getElementById('resumeLink');
    
    if (uploadArea) uploadArea.classList.add('has-file');
    if (info) info.style.display = 'flex';
    if (filenameEl) filenameEl.textContent = filename;
    if (linkEl) linkEl.href = url;
}

async function loadResume() {
    try {
        const response = await fetch('/api/resume/get/', {
            credentials: 'same-origin'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({error: `Server error: ${response.status}`}));
            throw new Error(errorData.error || `Server error: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.has_resume) {
            updateResumeUI(data.filename || 'Resume', data.url);
        }
    } catch (err) {
        console.error('Load resume error:', err);
    }
}

// ================= REAL-TIME TRANSCRIPTION & TRANSLATION =================
let recognition = null;
let isTranscribing = false;
let transcriptionBuffer = '';

function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        showToast('Speech recognition not supported in this browser. Use Chrome/Edge.', 'error');
        return null;
    }
    
    const rec = new SpeechRecognition();
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    
    rec.onresult = (event) => {
        let finalTranscript = '';
        let interimTranscript = '';
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += transcript + ' ';
            } else {
                interimTranscript += transcript;
            }
        }
        
        const outputEl = document.getElementById('transcriptionOutput');
        if (outputEl) {
            if (finalTranscript) {
                transcriptionBuffer += finalTranscript;
                outputEl.innerHTML = `<div style="margin-bottom:0.5rem;">${transcriptionBuffer}</div><div style="opacity:0.6;">${interimTranscript}</div>`;
                // Auto-translate final text
                translateText(finalTranscript.trim());
            } else {
                outputEl.innerHTML = `<div style="margin-bottom:0.5rem;">${transcriptionBuffer}</div><div style="opacity:0.6;">${interimTranscript}</div>`;
            }
            outputEl.scrollTop = outputEl.scrollHeight;
        }
    };
    
    rec.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        if (event.error === 'not-allowed') {
            showToast('Microphone permission denied for transcription', 'error');
            stopTranscription();
        } else if (event.error === 'no-speech') {
            // Auto-restart on no-speech
            if (isTranscribing) {
                try { rec.start(); } catch(e) {}
            }
        }
    };
    
    rec.onend = () => {
        // Auto-restart if still transcribing
        if (isTranscribing) {
            try { rec.start(); } catch(e) {}
        }
    };
    
    return rec;
}

async function translateText(text) {
    if (!text) return;
    
    const targetLang = document.getElementById('targetLang')?.value || 'en';
    const sourceLang = document.getElementById('sourceLang')?.value || 'en-US';
    const sourceCode = sourceLang.split('-')[0];
    
    // Don't translate if source and target are the same
    if (sourceCode === targetLang) return;
    
    const translationOutput = document.getElementById('translationOutput');
    if (translationOutput) translationOutput.style.display = 'block';
    
    try {
        // Use MyMemory API (free, no key required for reasonable usage)
        const encodedText = encodeURIComponent(text);
        const response = await fetch(`https://api.mymemory.translated.net/get?q=${encodedText}&langpair=${sourceCode}|${targetLang}`, {
            method: 'GET'
        });
        
        if (!response.ok) throw new Error('Translation API error');
        
        const data = await response.json();
        
        if (data.responseData && data.responseData.translatedText) {
            const translated = data.responseData.translatedText;
            const transOutput = document.getElementById('translationOutput');
            if (transOutput) {
                const existing = transOutput.dataset.content || '';
                const newContent = existing + translated + ' ';
                transOutput.dataset.content = newContent;
                transOutput.innerHTML = `<div style="color:#60a5fa;font-weight:600;margin-bottom:0.25rem;">Translation (${targetLang.toUpperCase()}):</div><div>${newContent}</div>`;
                transOutput.scrollTop = transOutput.scrollHeight;
            }
        }
    } catch (err) {
        console.error('Translation error:', err);
    }
}

function toggleTranscription() {
    const btn = document.getElementById('toggleTranscriptionBtn');
    
    if (isTranscribing) {
        stopTranscription();
        if (btn) {
            btn.innerHTML = '<i class="fas fa-microphone"></i> Start Transcription';
            btn.classList.remove('btn-danger');
            btn.classList.add('btn-primary');
        }
        showToast('Transcription stopped', 'success');
    } else {
        startTranscription();
        if (btn) {
            btn.innerHTML = '<i class="fas fa-stop"></i> Stop Transcription';
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-danger');
        }
        showToast('Transcription started - speak now', 'success');
    }
}

function startTranscription() {
    const sourceLang = document.getElementById('sourceLang')?.value || 'en-US';
    
    if (!recognition) {
        recognition = initSpeechRecognition();
    }
    
    if (!recognition) return;
    
    recognition.lang = sourceLang;
    transcriptionBuffer = '';
    isTranscribing = true;
    
    // Clear previous output
    const outputEl = document.getElementById('transcriptionOutput');
    const transOutput = document.getElementById('translationOutput');
    if (outputEl) outputEl.innerHTML = '<span style="opacity:0.5;">Listening...</span>';
    if (transOutput) {
        transOutput.innerHTML = '<span style="opacity:0.5;">Translation will appear here...</span>';
        transOutput.dataset.content = '';
        transOutput.style.display = 'none';
    }
    
    try {
        recognition.start();
    } catch (err) {
        console.error('Failed to start recognition:', err);
        showToast('Failed to start transcription', 'error');
        isTranscribing = false;
    }
}

function stopTranscription() {
    isTranscribing = false;
    if (recognition) {
        try {
            recognition.stop();
        } catch (err) {
            console.error('Error stopping recognition:', err);
        }
    }
}

// ================= SESSION LOGS =================
async function loadSessionLogs() {
    const listEl = document.getElementById('sessionLogsList');
    if (!listEl) return;

    const dateFilter = document.getElementById('logDateFilter')?.value || '';
    const statusFilter = document.getElementById('logStatusFilter')?.value || '';

    try {
        let url = '/api/logs/';
        const params = [];
        if (dateFilter) params.push(`date=${encodeURIComponent(dateFilter)}`);
        if (statusFilter) params.push(`status=${encodeURIComponent(statusFilter)}`);
        if (params.length) url += '?' + params.join('&');

        const response = await fetch(url, {
            credentials: 'same-origin'
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({error: `Server error: ${response.status}`}));
            throw new Error(errorData.error || `Server error: ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
            listEl.innerHTML = `<p style="text-align:center;opacity:0.6;padding:2rem;">${data.error}</p>`;
            return;
        }

        if (!data.logs || data.logs.length === 0) {
            listEl.innerHTML = `<p style="text-align:center;opacity:0.6;padding:2rem;">No session logs found.</p>`;
            return;
        }

        listEl.innerHTML = data.logs.map(log => {
            const date = new Date(log.timestamp);
            const dateStr = date.toLocaleDateString();
            const timeStr = date.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'});

            const riskColors = {
                'high': '#ef4444',
                'medium': '#f97316',
                'low': '#22c55e'
            };
            const borderColor = riskColors[log.risk_score] || '#6b7280';

            return `
                <div class="interview-item" style="border-left-color: ${borderColor};">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
                        <strong>Log #${log.id}</strong>
                        <span class="status-badge badge-${log.risk_score}">${log.risk_score.toUpperCase()}</span>
                    </div>
                    <div style="opacity:0.8;font-size:0.9rem;">
                        <i class="fas fa-calendar"></i> ${dateStr} at ${timeStr}
                        <span style="margin-left:1rem;"><i class="fas fa-user"></i> Faces: ${log.face_count}</span>
                        ${log.phone_detected ? '<span style="margin-left:1rem;color:#f97316;"><i class="fas fa-mobile-alt"></i> Phone Detected</span>' : ''}
                    </div>
                    <div style="margin-top:0.5rem;font-size:0.85rem;opacity:0.7;">
                        Status: ${log.status.replace(/_/g, ' ').toUpperCase()}
                        ${log.phone_confidence > 0 ? `| Confidence: ${log.phone_confidence.toFixed(2)}` : ''}
                    </div>
                </div>
            `;
        }).join('');
    } catch (err) {
        console.error('Load session logs error:', err);
        listEl.innerHTML = `<p style="text-align:center;opacity:0.6;padding:2rem;">Failed to load session logs: ${err.message}</p>`;
    }
}

