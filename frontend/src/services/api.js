const API_BASE = import.meta.env.VITE_API_URL || '';

// ── Auth Token Management ──

function getToken() {
    return localStorage.getItem('token');
}

export function setToken(token) {
    localStorage.setItem('token', token);
}

export function clearToken() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
}

export function getUser() {
    const u = localStorage.getItem('user');
    return u ? JSON.parse(u) : null;
}

export function setUser(user) {
    localStorage.setItem('user', JSON.stringify(user));
}


// ── Base Request Helper ──

async function request(url, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    // Handle FormData (remove Content-Type to let browser set boundary)
    if (options.body instanceof FormData) {
        delete headers['Content-Type'];
    }

    const res = await fetch(`${API_BASE}${url}`, { ...options, headers });

    if (!res.ok) {
        if (res.status === 401) {
            clearToken();
            window.location.href = '/login';
            throw new Error('Session expired');
        }
        const text = await res.text();
        throw new Error(`API Error ${res.status}: ${text}`);
    }

    return res.json();
}

async function authFetch(url, options = {}) {
    const token = getToken();
    const headers = { ...(options.headers || {}) };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}${url}`, { ...options, headers });

    if (!res.ok) {
        if (res.status === 401) {
            clearToken();
            window.location.href = '/login';
            throw new Error('Session expired');
        }
        const text = await res.text();
        throw new Error(`API Error ${res.status}: ${text}`);
    }
    return res;
}


// ── Auth ──

export async function login(email, password) {
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
    });
    if (!res.ok) {
        const text = await res.text();
        throw new Error(`Login failed: ${text}`);
    }
    const data = await res.json();
    setToken(data.access_token);
    setUser(data.user);
    return data;
}

export async function register(name, email, password, role, department = '') {
    return request('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ name, email, password, role, department }),
    });
}

export async function fetchMe() {
    return request('/auth/me');
}


// ── Job Requests ──

export async function createJob(payload) {
    return request('/jobs/', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

export async function listJobs() {
    return request('/jobs/');
}

export async function getJob(jobId) {
    return request(`/jobs/${jobId}`);
}

export async function updateJob(jobId, payload) {
    return request(`/jobs/${jobId}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
    });
}

export async function submitJob(jobId, payload = {}) {
    return request(`/jobs/${jobId}/submit`, {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

export async function cancelJob(jobId) {
    return request(`/jobs/${jobId}/cancel`, { method: 'POST' });
}

export async function uploadJD(file) {
    const formData = new FormData();
    formData.append('file', file);
    return request('jobs/parse-content', {
        method: 'POST',
        body: formData,
    });
}

export async function incomingJobs() {
    return request('/jobs/incoming/pending');
}

export async function activateJob(jobId) {
    return request(`/jobs/${jobId}/activate`, {
        method: 'POST',
        body: JSON.stringify({}),
    });
}

export async function getAnalytics() {
    return request('/analytics/pipeline');
}

export async function getAllCandidates() {
    return request('/jobs/all-candidates');
}

export async function hrEditJob(jobId, payload) {
    return request(`/jobs/${jobId}/hr-edit`, {
        method: 'PUT',
        body: JSON.stringify(payload),
    });
}

export async function fetchNotifications() {
    return request('/notifications/');
}

export async function fetchUnreadCount() {
    return request('/notifications/unread-count');
}

export async function markNotifRead(notifId) {
    return request(`/notifications/${notifId}/read`, { method: 'POST' });
}

export async function markAllRead() {
    return request('/notifications/read-all', { method: 'POST' });
}


// ── JD Pipeline ──

export async function fetchSavedForms() {
    return request('/jd/jd/forms');
}

export async function saveForm(formData) {
    return request('/jd/jd/forms', {
        method: 'POST',
        body: JSON.stringify(formData),
    });
}

export async function deleteForm(formId) {
    return request(`/jd/jd/forms/${formId}`, { method: 'DELETE' });
}

export async function updateFormJd(formId, generatedJd) {
    return request(`/jd/jd/forms/${formId}/jd`, {
        method: 'PUT',
        body: JSON.stringify({ generated_jd: generatedJd }),
    });
}

export async function updateFormProfile(formId, generatedProfile) {
    return request(`/jd/jd/forms/${formId}/profile`, {
        method: 'PUT',
        body: JSON.stringify({ generated_profile: generatedProfile }),
    });
}

export async function fetchRoles() {
    return request('/jd/jd/roles');
}

export async function clarifyJd(formData) {
    return request('/jd/jd/clarify', {
        method: 'POST',
        body: JSON.stringify(formData),
    });
}

export async function buildProfile(payload) {
    return request('/jd/jd/profile', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

export async function generateJd(payload) {
    return request('/jd/jd/generate', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

export async function suggestRoles(profile, instruction = null) {
    return request('/jd/jd/suggest-roles', {
        method: 'POST',
        body: JSON.stringify({ profile, instruction }),
    });
}

export async function refineJd(payload) {
    return request('/jd/jd/refine', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

// ── Chat-based JD Creation ──

export async function chatCreateJd(prompt, userId = null, sessionId = null, department = '') {
    return request('/jd/jd/chat-create', {
        method: 'POST',
        body: JSON.stringify({ prompt, user_id: userId, session_id: sessionId, department }),
    });
}

export async function chatRefineJd(payload) {
    return request('/jd/jd/chat-refine', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

// ── Memory System ──

export async function getMemory(userId) {
    return request(`/jd/jd/memory?user_id=${userId}`);
}

export async function analyzeMemory(payload) {
    return request('/jd/jd/memory/analyze', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
}

export async function exportDocx(jdText, role) {
    const res = await authFetch('/jd/jd/export-docx', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jd: jdText, role }),
    });
    return res.blob();
}

export async function runPipeline(formData) {
    const res = await authFetch('/pipeline/run_pipeline', {
        method: 'POST',
        body: formData,
    });
    return res.json();
}


// ── CV Analysis Pipeline ──

export async function buildPersonas(profile) {
    return request('/cv/personas', {
        method: 'POST',
        body: JSON.stringify({ profile }),
    });
}

export async function evaluateCVs(resumeFile, personas) {
    const formData = new FormData();
    formData.append('resumes', resumeFile);
    formData.append('personas', JSON.stringify(personas));

    const res = await authFetch('/cv/evaluate', {
        method: 'POST',
        body: formData,
    });
    return res.json();
}

export async function rankCandidates(evaluations, topN = 10) {
    return request('/cv/rank', {
        method: 'POST',
        body: JSON.stringify({ evaluations, top_n: topN }),
    });
}

export async function runFullCVPipeline(resumeFile, profile, topN = 10) {
    const formData = new FormData();
    formData.append('resumes', resumeFile);
    formData.append('profile', JSON.stringify(profile));
    formData.append('top_n', topN.toString());

    const res = await authFetch('/cv/full', {
        method: 'POST',
        body: formData,
    });
    return res.json();
}


// ── Keka Hire Integration ──

export async function testKekaConnection() {
    const res = await authFetch('/keka/test-connection');
    return res.json();
}

export async function listKekaJobs(status = null) {
    const url = status ? `/keka/jobs?status=${status}` : '/keka/jobs';
    const res = await authFetch(url);
    return res.json();
}

export async function listKekaCandidates(kekaJobId) {
    const res = await authFetch(`/keka/jobs/${kekaJobId}/candidates`);
    return res.json();
}

export async function importKekaCandidates(kekaJobId, localJobId, candidateIds = null) {
    const res = await authFetch(`/keka/import-candidates/${kekaJobId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            local_job_id: localJobId,
            candidate_ids: candidateIds,
        }),
    });
    return res.json();
}
