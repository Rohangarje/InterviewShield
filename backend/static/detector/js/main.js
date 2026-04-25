const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
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
async function initCamera() {
    try {
        console.log('Initializing camera...');
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } } 
        });
        video.srcObject = stream;
        video.onloadedmetadata = () => {
            video.play().catch(err => {
                console.error('Video play error:', err);
                showToast('Camera play error: ' + err.message, 'error');
            });
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            showToast('✅ Camera ready!', 'success');
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
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.8);
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
    const csrfToken = getCsrfToken();
    try {
        const response = await fetch('/api/detect/', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ image: imgBase64 })
        });
        
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
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
        showToast(`📱 Mobile detected! Conf: ${data.phone_confidence}`, 'error');
    } else if (data.face_status !== 'normal') {
        showToast(data.alert, 'error');
    }
}

function addLog(data) {
    if (!logList) return;
    const li = document.createElement('li');
    li.className = data.risk_score === 'high' ? 'log-alert log-item' : 'log-normal log-item';
    li.innerHTML = `<strong>${new Date().toLocaleTimeString()}</strong>: ${data.alert} (Faces: ${data.face_count}${data.phone_detected ? ', 📱' : ''})`;
    logList.insertBefore(li, logList.firstChild);
    
    while (logList.children.length > 10) logList.removeChild(logList.lastChild);
}

startBtn.onclick = () => {
    if (!isDetecting) {
        isDetecting = true;
        startBtn.disabled = true;
        stopBtn.disabled = false;
        detectFaces();
        detectionInterval = setInterval(detectFaces, 2000);
        showToast('Detection started');
    }
};

stopBtn.onclick = () => {
    isDetecting = false;
    clearInterval(detectionInterval);
    startBtn.disabled = false;
    stopBtn.disabled = true;
    showToast('Detection stopped');
};

// ================= ANALYTICS DASHBOARD =================
async function fetchAnalytics() {
    try {
        const response = await fetch('/api/analytics/');
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
        </div>
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
    fetchAnalytics(); // Initial load
    refreshTimer = setInterval(fetchAnalytics, 30000); // 30s
}

function stopAutoRefresh() {
    clearInterval(refreshTimer);
}

// Global init
document.addEventListener('DOMContentLoaded', () => {
    startAutoRefresh();
    
    // Sidebar toggle
    window.toggleSidebar = () => document.getElementById('sidebar')?.classList.toggle('open');
    
    // Refresh button
    document.getElementById('refreshBtn')?.addEventListener('click', fetchAnalytics);
});
