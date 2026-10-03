import { cn } from '../../utils/classnames';

export function Textarea({
  label, error, hint, className, id, rows = 4, maxLength, showCount = false, ...props
}) {
  const textareaId = id || label?.toLowerCase().replace(/\s+/g, '-');
  const currentLength = props.value?.length ?? 0;

  return (
    <div className="input-field">
      {label && (
        <label htmlFor={textareaId} className="input-label">{label}</label>
      )}
      <textarea
        id={textareaId}
        rows={rows}
        maxLength={maxLength}
        className={cn('input', error && 'input-error', className)}
        aria-invalid={Boolean(error)}
        {...props}
      />
      <div className="textarea-footer">
        {error ? (
          <span className="input-error-text" role="alert">{error}</span>
        ) : hint ? (
          <span className="input-hint">{hint}</span>
        ) : (
          <span />
        )}
        {showCount && maxLength && (
          <span className={cn('char-count', currentLength >= maxLength && 'char-count-limit')}>
            {currentLength}/{maxLength}
          </span>
        )}
      </div>
    </div>
  );
}
