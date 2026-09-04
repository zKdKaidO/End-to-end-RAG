interface ZkdWordmarkProps {
  size?: "sidebar" | "hero";
}

export function ZkdWordmark({ size = "sidebar" }: ZkdWordmarkProps) {
  return (
    <div className={`zkd-wordmark zkd-wordmark--${size}`} aria-label="zKd AI">
      <span className="zkd-wordmark__name">zKd</span>
      <span className="zkd-wordmark__ai">AI</span>
    </div>
  );
}