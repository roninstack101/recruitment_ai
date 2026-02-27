import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Plus, Send, XCircle, Eye, Clock, CheckCircle2,
    Calendar, Briefcase, FileText, RefreshCw,
    AlertTriangle, ArrowRight, ChevronDown, ChevronUp, Upload, Edit, Pencil,
    Sparkles
} from 'lucide-react';
import * as api from '../services/api';
import './TeamLeadPage.css';

const STATUS_CONFIG = {
    draft: { label: 'Draft', color: '#f59e0b', bg: '#fef3c7', icon: FileText },
    pending_hr: { label: 'Pending HR', color: '#3b82f6', bg: '#dbeafe', icon: Clock },
    active: { label: 'Active', color: '#16a34a', bg: '#dcfce7', icon: CheckCircle2 },
    cancelled: { label: 'Cancelled', color: '#ef4444', bg: '#fee2e2', icon: XCircle },
    closed: { label: 'Closed', color: '#6b7280', bg: '#f3f4f6', icon: CheckCircle2 },
};

export default function TeamLeadPage() {
    const navigate = useNavigate();
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [expandedJob, setExpandedJob] = useState(null);
    const [error, setError] = useState('');
    const [actionLoading, setActionLoading] = useState(null);
    const [editingJobId, setEditingJobId] = useState(null);

    // ── Form state ──
    const [roleTitle, setRoleTitle] = useState('');
    const user = api.getUser();
    const [jdText, setJdText] = useState('');
    const [closureDate, setClosureDate] = useState('');

    useEffect(() => { loadJobs(); }, []);

    // Check for incoming JD from JD Creator
    useEffect(() => {
        const data = sessionStorage.getItem('jd_for_request');
        if (data) {
            try {
                const { role, department: dept, jd, closure_date } = JSON.parse(data);
                setRoleTitle(role || '');
                setJdText(jd || '');
                if (closure_date) setClosureDate(closure_date);
                setShowForm(true);
                sessionStorage.removeItem('jd_for_request');
            } catch (_) { }
        }
    }, []);

    async function loadJobs() {
        setLoading(true);
        try {
            const data = await api.listJobs();
            setJobs(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    async function handleCreate(e) {
        e.preventDefault();
        setActionLoading('create');
        try {
            await api.createJob({
                role_title: roleTitle,
                department: user?.department || null,
                jd_text: jdText || null,
                profile_json: null,
                budget: null,
                adjustable_budget: null,
                end_date: closureDate || null,
            });
            resetForm();
            setShowForm(false);
            await loadJobs();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    }

    async function handleUpdate(e) {
        e.preventDefault();
        setActionLoading('update');
        try {
            await api.updateJob(editingJobId, {
                role_title: roleTitle,
                department: user?.department || null,
                jd_text: jdText || null,
                budget: null,
                adjustable_budget: null,
                end_date: closureDate || null,
            });
            resetForm();
            setShowForm(false);
            await loadJobs();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    }

    async function handleFileUpload(e) {
        const file = e.target.files[0];
        if (!file) return;

        setActionLoading('upload');
        try {
            const data = await api.uploadJD(file);
            setJdText(data.text);
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
            e.target.value = ''; // Reset input
        }
    }

    async function handleSubmit(jobId) {
        setActionLoading(`submit-${jobId}`);
        try {
            await api.submitJob(jobId);
            await loadJobs();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    }

    async function handleCancel(jobId) {
        if (!confirm('Cancel this job request? HR will be notified.')) return;
        setActionLoading(`cancel-${jobId}`);
        try {
            await api.cancelJob(jobId);
            await loadJobs();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    }

    function resetForm() {
        setRoleTitle(''); setJdText(''); setClosureDate('');
        setEditingJobId(null);
        setError('');
    }

    function startEdit(job) {
        setEditingJobId(job.id);
        setRoleTitle(job.role_title);
        setJdText(job.jd_text || '');
        setClosureDate(job.end_date ? job.end_date.split('T')[0] : '');
        setShowForm(true);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    const stats = {
        total: jobs.length,
        draft: jobs.filter(j => j.status === 'draft').length,
        pending: jobs.filter(j => j.status === 'pending_hr').length,
        active: jobs.filter(j => j.status === 'active').length,
    };

    return (
        <div className="tl-page">
            <div className="tl-header">
                <div>
                    <h1>Team Lead Dashboard</h1>
                    <p className="tl-subtitle">Create and manage job requests</p>
                </div>
                <button
                    className="tl-btn primary"
                    onClick={() => { resetForm(); setShowForm(!showForm); }}
                >
                    <Plus size={18} />
                    New Job Request
                </button>
            </div>

            {/* Stats */}
            <div className="tl-stats">
                {[
                    { label: 'Total', value: stats.total, color: '#818cf8', bg: '#eef2ff' },
                    { label: 'Drafts', value: stats.draft, color: '#f59e0b', bg: '#fef3c7' },
                    { label: 'Pending HR', value: stats.pending, color: '#3b82f6', bg: '#dbeafe' },
                    { label: 'Active', value: stats.active, color: '#16a34a', bg: '#dcfce7' },
                ].map(s => (
                    <div key={s.label} className="tl-stat-card" style={{ borderLeftColor: s.color }}>
                        <span className="tl-stat-value" style={{ color: s.color }}>{s.value}</span>
                        <span className="tl-stat-label">{s.label}</span>
                    </div>
                ))}
            </div>

            {/* Error */}
            {error && (
                <div className="tl-error">
                    <AlertTriangle size={16} /> {error}
                    <button onClick={() => setError('')}>✕</button>
                </div>
            )}

            {/* Create/Edit Form */}
            {showForm && (
                <form className="tl-create-section" onSubmit={editingJobId ? handleUpdate : handleCreate}>
                    <h3>
                        {editingJobId ? <Pencil size={18} /> : <Plus size={18} />}
                        {editingJobId ? 'Edit Job Request' : 'New Job Request'}
                    </h3>

                    <div className="tl-form-grid">
                        <div className="tl-form-group">
                            <label><Briefcase size={14} /> Role Title *</label>
                            <input
                                value={roleTitle} onChange={e => setRoleTitle(e.target.value)}
                                placeholder="e.g. Senior Software Engineer" required
                            />
                        </div>
                        <div className="tl-form-group">
                            <label><Calendar size={14} /> Closure Date</label>
                            <input
                                type="date" value={closureDate}
                                onChange={e => setClosureDate(e.target.value)}
                            />
                        </div>
                        <div className="tl-form-group full-width">
                            <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span><FileText size={14} /> Job Description</span>
                                <div style={{ display: 'flex', gap: '6px' }}>
                                    <button
                                        type="button"
                                        className="tl-btn ghost small"
                                        style={{ fontSize: '0.75rem', padding: '4px 8px' }}
                                        onClick={() => {
                                            sessionStorage.setItem('jd_from_job_request', JSON.stringify({
                                                role: roleTitle,
                                                closureDate: closureDate
                                            }));
                                            navigate('/recruiter');
                                        }}
                                    >
                                        <Sparkles size={12} /> Create with AI
                                    </button>
                                    <div style={{ position: 'relative', overflow: 'hidden' }}>
                                        <button type="button" className="tl-btn ghost small" style={{ fontSize: '0.75rem', padding: '4px 8px' }}>
                                            <Upload size={12} /> {actionLoading === 'upload' ? 'Uploading...' : 'Upload DOCX/PDF'}
                                        </button>
                                        <input
                                            type="file"
                                            accept=".docx,.pdf"
                                            onChange={handleFileUpload}
                                            style={{ position: 'absolute', top: 0, left: 0, opacity: 0, width: '100%', height: '100%', cursor: 'pointer' }}
                                            disabled={actionLoading === 'upload'}
                                        />
                                    </div>
                                </div>
                            </label>
                            <textarea
                                value={jdText} onChange={e => setJdText(e.target.value)}
                                rows={5} placeholder="Paste or type the job description, or click 'Create with AI' above…"
                            />
                        </div>
                    </div>

                    <div className="tl-form-actions">
                        <button type="button" className="tl-btn ghost" onClick={() => { setShowForm(false); resetForm(); }}>
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className="tl-btn primary"
                            disabled={
                                actionLoading === 'create' || actionLoading === 'update'
                            }
                        >
                            {editingJobId
                                ? (actionLoading === 'update' ? 'Updating...' : 'Update Draft')
                                : (actionLoading === 'create' ? 'Creating...' : 'Create Draft')
                            }
                        </button>
                    </div>
                </form>
            )}

            {/* Job List */}
            <div className="tl-header" style={{ marginBottom: '14px' }}>
                <h2 className="tl-section-label">Your Job Requests</h2>
                <button className="tl-btn ghost" onClick={loadJobs}>
                    <RefreshCw size={14} /> Refresh
                </button>
            </div>

            {loading ? (
                <div className="tl-loading">Loading jobs…</div>
            ) : jobs.length === 0 ? (
                <div className="tl-empty">
                    <Briefcase size={40} />
                    <p>No job requests yet. Click <strong>"New Job Request"</strong> to get started.</p>
                </div>
            ) : (
                <div className="tl-job-list">
                    {jobs.map(job => {
                        const cfg = STATUS_CONFIG[job.status] || STATUS_CONFIG.draft;
                        const StatusIcon = cfg.icon;
                        const isExpanded = expandedJob === job.id;

                        return (
                            <div key={job.id} className="tl-job-card">
                                <div
                                    className="tl-job-row"
                                    onClick={() => setExpandedJob(isExpanded ? null : job.id)}
                                >
                                    <div className="tl-job-info">
                                        <h4>{job.role_title}</h4>
                                        <span className="tl-job-date">
                                            Created {new Date(job.created_at).toLocaleDateString()}
                                        </span>
                                    </div>

                                    <div className="tl-job-meta">
                                        {job.budget && (
                                            <span className="tl-chip budget">
                                                ₹{job.budget} LPA
                                            </span>
                                        )}
                                        {job.end_date && (
                                            <span className="tl-chip date">
                                                <Calendar size={12} /> {new Date(job.end_date).toLocaleDateString()}
                                            </span>
                                        )}
                                        <span
                                            className="tl-status-badge"
                                            style={{ color: cfg.color, background: cfg.bg }}
                                        >
                                            <StatusIcon size={14} /> {cfg.label}
                                        </span>
                                        {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                                    </div>
                                </div>

                                {isExpanded && (
                                    <div className="tl-job-expanded">
                                        {job.jd_text ? (
                                            <pre className="tl-jd-preview">{job.jd_text}</pre>
                                        ) : (
                                            <p className="tl-no-jd">No JD text yet. You can add one by editing this draft.</p>
                                        )}

                                        <div className="tl-job-actions">
                                            {job.status === 'draft' && (
                                                <>
                                                    <button
                                                        className="tl-btn primary small"
                                                        onClick={() => handleSubmit(job.id)}
                                                        disabled={actionLoading === `submit-${job.id}`}
                                                    >
                                                        <Send size={14} />
                                                        {actionLoading === `submit-${job.id}` ? 'Sending…' : 'Submit to HR'}
                                                    </button>
                                                    <button
                                                        className="tl-btn ghost small"
                                                        onClick={() => startEdit(job)}
                                                    >
                                                        <Edit size={14} /> Edit
                                                    </button>
                                                </>
                                            )}
                                            {!['cancelled', 'closed'].includes(job.status) && (
                                                <button
                                                    className="tl-btn danger small"
                                                    onClick={() => handleCancel(job.id)}
                                                    disabled={actionLoading === `cancel-${job.id}`}
                                                >
                                                    <XCircle size={14} />
                                                    {actionLoading === `cancel-${job.id}` ? 'Cancelling…' : 'Cancel Request'}
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
