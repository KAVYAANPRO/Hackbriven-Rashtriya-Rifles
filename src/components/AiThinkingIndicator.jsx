export function AiThinkingIndicator({ message = 'IdeaFeed is thinking…', className }) {
  return (
    <div className={`ai-thinking ${className || ''}`}>
      <div className="ai-thinking-dots">
        <span /><span /><span />
      </div>
      <p className="ai-thinking-message">{message}</p>
    </div>
  );
}
