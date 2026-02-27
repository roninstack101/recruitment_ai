import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    ArrowRight, Send, Download, RefreshCw,
    FileText, Sparkles, Brain, CheckCircle2, Briefcase, Calendar, Edit3,
} from 'lucide-react';
import StepProgress from '../components/StepProgress';
import JdPreview from '../components/JdPreview';
import * as api from '../services/api';
import './RecruiterPage.css';

const EXPERIENCE_OPTIONS = [
    'Fresher',
    '1–2 years',
    '3–5 years',
    '5–8 years',
    '8–12 years',
    '12+ years',
];

export default function RecruiterPage() {
    const navigate = useNavigate();
    const [step, setStep] = useState(1);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const user = api.getUser();
    const userId = user?.id || null;
    const department = user?.department || '';

    // ── Step 1 state ──
    const [jobName, setJobName] = useState('');
    const [experience, setExperience] = useState('');
    const [specificRequests, setSpecificRequests] = useState('');

    // ── Step 2 state ──
    const [questions, setQuestions] = useState([]);
    const [answers, setAnswers] = useState({});     // { q1: ['opt1','opt3'], q2: [...] }

    // ── Step 3 state ──
    const [profile, setProfile] = useState(null);
    const [finalJd, setFinalJd] = useState('');
    const [chatHistory, setChatHistory] = useState([]);
    const [chatInput, setChatInput] = useState('');
    const [sessionId] = useState(() => Date.now().toString());

    // ── Step 4 state ──
    const [closureDate, setClosureDate] = useState('');
    const [hasMemory, setHasMemory] = useState(false);

    useEffect(() => {
        if (userId) {
            api.getMemory(userId)
                .then((res) => { if (res.preferences_summary) setHasMemory(true); })
                .catch(() => { });
        }
    }, [userId]);

    // Auto-fill from job request (sessionStorage)
    useEffect(() => {
        const data = sessionStorage.getItem('jd_from_job_request');
        if (data) {
            try {
                const { role, closureDate } = JSON.parse(data);
                if (role) setJobName(role);
                if (closureDate) setClosureDate(closureDate);
                sessionStorage.removeItem('jd_from_job_request');
            } catch (_) { }
        }
    }, []);

    const handleError = (err) => {
        console.error(err);
        setError(err.message || 'Something went wrong');
        setLoading(false);
    };

    // ── Step 1 → 2: Generate clarifying questions ──
    const handleGenerateQuestions = async () => {
        if (!jobName.trim()) return;
        setLoading(true);
        setError('');
        try {
            const formData = {
                role: jobName.trim(),
                department: department,
                experience: experience,
                additional_info: specificRequests.trim(),
            };
            const res = await api.clarifyJd(formData);
            setQuestions(res.questions || []);
            setAnswers({});
            setStep(2);
        } catch (err) { handleError(err); }
        setLoading(false);
    };

    // ── Toggle answer for a question ──
    const toggleAnswer = (questionId, option) => {
        setAnswers(prev => {
            const current = prev[questionId] || [];
            const updated = current.includes(option)
                ? current.filter(o => o !== option)
                : [...current, option];
            return { ...prev, [questionId]: updated };
        });
    };

    // ── Step 2 → 3: Build profile + generate JD ──
    const handleGenerateJd = async () => {
        setLoading(true);
        setError('');
        try {
            const formData = {
                role: jobName.trim(),
                department: department,
                experience: experience,
                additional_info: specificRequests.trim(),
            };
            // Flatten answers for the profile builder
            const answersList = questions.map(q => ({
                question: q.question,
                selected: answers[q.id] || [],
            }));

            // Build profile + generate JD in parallel
            const [profileRes, jdRes] = await Promise.all([
                api.buildProfile({ form_data: formData, answers: answersList }),
                api.generateJd({ form_data: formData, profile: null }),
            ]);

            const builtProfile = profileRes.profile || null;
            setProfile(builtProfile);

            // If we got a profile, regenerate JD with it for better quality
            if (builtProfile) {
                const betterJd = await api.generateJd({ form_data: formData, profile: builtProfile });
                setFinalJd(betterJd.jd || jdRes.jd || '');
            } else {
                setFinalJd(jdRes.jd || '');
            }

            setStep(3);
        } catch (err) { handleError(err); }
        setLoading(false);
    };

    // ── Step 3: Refine JD via chat ──
    const applyRefinement = async () => {
        if (!chatInput.trim()) return;
        setLoading(true);
        setError('');
        try {
            const res = await api.chatRefineJd({
                jd: finalJd, instruction: chatInput.trim(),
                user_id: userId, role: jobName, session_id: sessionId,
            });
            setFinalJd(res.jd);
            setChatHistory(prev => [...prev, { instruction: chatInput.trim(), version: prev.length + 1 }]);
            setChatInput('');
        } catch (err) { handleError(err); }
        setLoading(false);
    };

    // ── Step 4: Export ──
    const downloadDocx = async () => {
        setLoading(true);
        setError('');
        try {
            const usedRole = jobName || 'Job_Description';
            const blob = await api.exportDocx(finalJd, usedRole);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${usedRole.replace(/\s/g, '_')}_JD.docx`;
            a.click();
            URL.revokeObjectURL(url);
            if (userId) {
                api.analyzeMemory({
                    user_id: userId, initial_prompt: `${jobName} - ${experience}`,
                    final_jd: finalJd, edit_history: chatHistory,
                }).catch(() => { });
            }
        } catch (err) { handleError(err); }
        setLoading(false);
    };

    const startOver = () => {
        setStep(1); setJobName(''); setExperience(''); setSpecificRequests('');
        setQuestions([]); setAnswers({}); setProfile(null);
        setFinalJd(''); setChatHistory([]); setChatInput('');
        setClosureDate(''); setError('');
    };

    return (
        <div className="recruiter-page">
            {/* ── Hero Header ── */}
            <div className="jd-hero">
                <div className="jd-hero-content">
                    <div className="jd-hero-icon">
                        <Sparkles size={24} />
                    </div>
                    <div>
                        <h1 className="jd-hero-title">JD Creator</h1>
                        <p className="jd-hero-sub">Generate professional job descriptions with AI in seconds</p>
                    </div>
                </div>
                {hasMemory && (
                    <div className="jd-memory-pill">
                        <Brain size={14} />
                        <span>AI remembers your preferences</span>
                    </div>
                )}
            </div>

            <StepProgress current={step} />

            {error && (
                <div className="jd-error">
                    ⚠️ {error}
                    <button onClick={() => setError('')}>✕</button>
                </div>
            )}

            {/* ════════ STEP 1: Job Details ════════ */}
            {step === 1 && (
                <div className="jd-step animate-fade-in-up">
                    <div className="jd-details-card">
                        <h3 className="jd-details-title">
                            <FileText size={18} /> Tell us about the role
                        </h3>
                        <div className="jd-details-form">
                            <div className="jd-form-group">
                                <label>Job Title *</label>
                                <input
                                    type="text"
                                    value={jobName}
                                    onChange={e => setJobName(e.target.value)}
                                    placeholder="e.g. Senior Software Engineer"
                                />
                            </div>
                            <div className="jd-form-group">
                                <label>Experience Level</label>
                                <select value={experience} onChange={e => setExperience(e.target.value)}>
                                    <option value="">Select experience level</option>
                                    {EXPERIENCE_OPTIONS.map(opt => (
                                        <option key={opt} value={opt}>{opt}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="jd-form-group full-width">
                                <label>Specific Requests <span className="jd-optional">(optional)</span></label>
                                <textarea
                                    value={specificRequests}
                                    onChange={e => setSpecificRequests(e.target.value)}
                                    placeholder="e.g. Must know React & Node.js, remote-friendly, leadership experience preferred"
                                    rows={3}
                                />
                            </div>
                        </div>
                        <div className="jd-step-actions">
                            <button
                                className="jd-btn primary"
                                disabled={!jobName.trim() || loading}
                                onClick={handleGenerateQuestions}
                            >
                                {loading ? (
                                    <><div className="jd-spinner" /> Generating…</>
                                ) : (
                                    <>Next: Clarifying Questions <ArrowRight size={15} /></>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ════════ STEP 2: Clarifying Questions ════════ */}
            {step === 2 && (
                <div className="jd-step animate-fade-in-up">
                    <div className="jd-questions-card">
                        <h3 className="jd-details-title">
                            <Sparkles size={18} /> Clarifying Questions
                        </h3>
                        <p className="jd-questions-hint">
                            Select all options that apply for each question. This helps the AI create a more accurate JD.
                        </p>

                        {questions.length === 0 ? (
                            <div className="jd-preview-empty">
                                <p>No questions were generated. Try going back and adding more details.</p>
                            </div>
                        ) : (
                            <div className="jd-questions-list">
                                {questions.map((q, idx) => (
                                    <div key={q.id} className="jd-question-item">
                                        <div className="jd-question-number">{idx + 1}</div>
                                        <div className="jd-question-body">
                                            <p className="jd-question-text">{q.question}</p>
                                            <div className="jd-question-options">
                                                {q.options.map((opt, oi) => {
                                                    const isSelected = (answers[q.id] || []).includes(opt);
                                                    return (
                                                        <button
                                                            key={oi}
                                                            className={`jd-option-btn ${isSelected ? 'selected' : ''}`}
                                                            onClick={() => toggleAnswer(q.id, opt)}
                                                        >
                                                            <span className="jd-option-check">
                                                                {isSelected ? '✓' : ''}
                                                            </span>
                                                            {opt}
                                                        </button>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        <div className="jd-step-actions">
                            <button className="jd-btn ghost" onClick={() => setStep(1)}>
                                ← Back
                            </button>
                            <button
                                className="jd-btn primary"
                                disabled={loading}
                                onClick={handleGenerateJd}
                            >
                                {loading ? (
                                    <><div className="jd-spinner" /> Generating JD…</>
                                ) : (
                                    <>Generate JD <ArrowRight size={15} /></>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ════════ STEP 3: Draft JD + Refine ════════ */}
            {step === 3 && (
                <div className="jd-step animate-fade-in-up">
                    <div className="jd-create-grid">
                        {/* Left: Refine chat */}
                        <div className="jd-create-chat-col">
                            <div className="jd-section-label">
                                <Send size={14} />
                                <span>Refine your JD</span>
                                {chatHistory.length > 0 && (
                                    <span className="jd-role-tag">v{chatHistory.length + 1}</span>
                                )}
                            </div>
                            <div className="jd-refine-card">
                                <p className="jd-refine-hint">
                                    Tell the AI what to change. Each instruction updates the draft.
                                </p>
                                {chatHistory.length > 0 && (
                                    <div className="jd-refine-history">
                                        {chatHistory.map((entry, i) => (
                                            <div key={i} className="jd-refine-entry">
                                                <div className="jd-refine-user">
                                                    <span className="jd-refine-badge">You</span>
                                                    {entry.instruction}
                                                </div>
                                                <div className="jd-refine-ai">
                                                    <CheckCircle2 size={13} /> Updated — v{entry.version + 1}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                                <div className="jd-refine-input-row">
                                    <input
                                        className="jd-refine-input"
                                        placeholder="e.g. Make it shorter / Add Python as a requirement"
                                        value={chatInput}
                                        onChange={e => setChatInput(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && applyRefinement()}
                                        disabled={loading}
                                    />
                                    <button
                                        className="jd-btn primary"
                                        onClick={applyRefinement}
                                        disabled={loading || !chatInput.trim()}
                                    >
                                        <Send size={14} /> Apply
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* Right: JD Preview */}
                        <div className="jd-create-preview-col">
                            <div className="jd-section-label">
                                <FileText size={14} />
                                <span>Draft JD</span>
                                <span className="jd-role-tag">{jobName}</span>
                            </div>
                            <div className="jd-preview-card">
                                {finalJd ? (
                                    <JdPreview markdown={finalJd} />
                                ) : (
                                    <div className="jd-preview-empty">
                                        <FileText size={36} />
                                        <p>Generating your JD…</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="jd-step-actions two-buttons">
                        <button className="jd-btn ghost" onClick={() => setStep(2)}>
                            ← Back to Questions
                        </button>
                        <button
                            className="jd-btn primary"
                            disabled={!finalJd || loading}
                            onClick={() => setStep(4)}
                        >
                            Finalize & Export <ArrowRight size={15} />
                        </button>
                    </div>
                </div>
            )}

            {/* ════════ STEP 4: Export ════════ */}
            {step === 4 && (
                <div className="jd-step animate-fade-in-up">
                    <div className="jd-export-card">
                        <div className="jd-export-header">
                            <CheckCircle2 size={20} />
                            <div>
                                <h3>Ready to export</h3>
                                <p>{jobName}{chatHistory.length > 0 ? ` · ${chatHistory.length} refinement(s)` : ''}</p>
                            </div>
                        </div>

                        <div className="jd-export-preview">
                            <JdPreview markdown={finalJd} />
                        </div>

                        <details className="jd-manual-edit">
                            <summary>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Edit3 size={16} /> <span>Manual Edit</span>
                                </div>
                                <span className="jd-edit-hint">Click to expand and edit Markdown</span>
                            </summary>
                            <textarea
                                className="jd-edit-textarea"
                                rows={12}
                                value={finalJd}
                                onChange={(e) => setFinalJd(e.target.value)}
                                placeholder="Edit the job description markdown here..."
                            />
                        </details>

                        <div className="jd-closure-date">
                            <label><Calendar size={14} /> Closure Date</label>
                            <input
                                type="date"
                                value={closureDate}
                                onChange={(e) => setClosureDate(e.target.value)}
                            />
                        </div>

                        <div className="jd-export-actions">
                            <div className="jd-export-btn-row">
                                <button
                                    className="jd-btn primary large"
                                    onClick={downloadDocx}
                                    disabled={loading}
                                >
                                    {loading ? (
                                        <><div className="jd-spinner" /> Generating…</>
                                    ) : (
                                        <><Download size={16} /> Download DOCX</>
                                    )}
                                </button>
                                <button
                                    className="jd-btn accent large"
                                    onClick={() => {
                                        sessionStorage.setItem('jd_for_request', JSON.stringify({
                                            role: jobName,
                                            department: department,
                                            jd: finalJd,
                                            closure_date: closureDate,
                                        }));
                                        if (userId) {
                                            api.analyzeMemory({
                                                user_id: userId, initial_prompt: `${jobName} - ${experience}`,
                                                final_jd: finalJd, edit_history: chatHistory,
                                            }).catch(() => { });
                                        }
                                        navigate('/team-lead');
                                    }}
                                >
                                    <Briefcase size={16} /> Use in Job Request
                                </button>
                            </div>
                            <button className="jd-btn ghost" onClick={startOver}>
                                <RefreshCw size={14} /> Start Over
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
