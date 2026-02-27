import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2 } from 'lucide-react';
import './JdChatCreator.css';

export default function JdChatCreator({ hasMemory = false, loading = false, onSendPrompt }) {
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState([
        {
            type: 'system',
            text: 'Hi! Describe the role you want to hire for and I\'ll create a professional JD.\n\nExamples:\n• "Senior Python Developer, Bangalore, 5+ yrs, Django & AWS"\n• "Marketing Manager, Mumbai, digital marketing experience"\n• "Entry-level Data Analyst, remote, fresher-friendly"',
        },
    ]);
    const endRef = useRef(null);
    const inputRef = useRef(null);

    useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
    useEffect(() => { if (!loading && inputRef.current) inputRef.current.focus(); }, [loading]);

    const handleSend = () => {
        const prompt = input.trim();
        if (!prompt || loading) return;
        setMessages(p => [...p, { type: 'user', text: prompt }]);
        setInput('');
        setMessages(p => [...p, { type: 'loading', text: 'Generating your JD…' }]);
        onSendPrompt(prompt, (result) => {
            setMessages(p => {
                const filtered = p.filter(m => m.type !== 'loading');
                return [...filtered, {
                    type: 'ai',
                    text: result.jd
                        ? `✅ Generated JD for "${result.role}"! Check the preview panel.`
                        : '❌ Something went wrong. Try a more detailed prompt.',
                }];
            });
        });
    };

    return (
        <div className="jdc">
            <div className="jdc-messages">
                {messages.map((msg, i) => (
                    <div key={i} className={`jdc-msg ${msg.type}`}>
                        <div className="jdc-avatar">
                            {msg.type === 'user' ? <User size={14} /> :
                                msg.type === 'loading' ? <Loader2 size={14} className="jdc-spin" /> :
                                    <Bot size={14} />}
                        </div>
                        <div className="jdc-bubble">
                            {msg.type === 'loading' ? (
                                <span className="jdc-typing">{msg.text}<span className="jdc-dots" /></span>
                            ) : (
                                msg.text.split('\n').map((line, j) => <p key={j}>{line}</p>)
                            )}
                        </div>
                    </div>
                ))}
                <div ref={endRef} />
            </div>
            <div className="jdc-bar">
                <input
                    ref={inputRef}
                    className="jdc-input"
                    placeholder="Describe the role you're hiring for…"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                    disabled={loading}
                />
                <button className="jdc-send" onClick={handleSend} disabled={!input.trim() || loading}>
                    {loading ? <Loader2 size={16} className="jdc-spin" /> : <Send size={16} />}
                </button>
            </div>
        </div>
    );
}
