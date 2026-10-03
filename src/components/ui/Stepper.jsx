import { cn } from '../../utils/classnames';

export function Stepper({ steps, current, className }) {
  return (
    <div className={cn('stepper', className)}>
      {steps.map((step, i) => {
        const isDone = i < current;
        const isActive = i === current;
        return (
          <div key={i} className={cn('step', isDone && 'step-done', isActive && 'step-active')}>
            <div className="step-circle">
              {isDone ? '✓' : <span>{i + 1}</span>}
            </div>
            <div className="step-label">{step}</div>
            {i < steps.length - 1 && <div className="step-connector" />}
          </div>
        );
      })}
    </div>
  );
}
