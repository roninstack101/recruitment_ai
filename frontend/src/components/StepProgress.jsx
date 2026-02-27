import { Check } from 'lucide-react';
import './StepProgress.css';

const STEPS = [
    { icon: '📋', label: 'Job Details' },
    { icon: '❓', label: 'Questions' },
    { icon: '✏️', label: 'Draft JD' },
    { icon: '🏁', label: 'Export' },
];

export default function StepProgress({ current }) {
    return (
        <div className="step-progress">
            {STEPS.map((step, idx) => {
                const num = idx + 1;
                const isDone = num < current;
                const isActive = num === current;

                return (
                    <div key={num} className="step-item">
                        {idx > 0 && (
                            <div className={`step-line ${isDone ? 'done' : ''}`} />
                        )}
                        <div
                            className={`step-circle ${isDone ? 'done' : ''} ${isActive ? 'active' : ''}`}
                        >
                            {isDone ? <Check size={18} /> : step.icon}
                        </div>
                        <span
                            className={`step-label ${isDone || isActive ? 'highlight' : ''}`}
                        >
                            {step.label}
                        </span>
                    </div>
                );
            })}
        </div>
    );
}
