import { useState } from 'react';
import { ImageOff } from 'lucide-react';
import { screenshots } from '../data/app';

type Props = {
  index: number;
  className?: string;
  eager?: boolean;
  full?: boolean;
};

export default function ScreenshotImage({ index, className = '', eager = false, full = false }: Props) {
  const [attempt, setAttempt] = useState(0);
  const screenshot = screenshots[index];

  if (attempt > 1 || (attempt === 1 && !screenshot.fallback)) {
    return (
      <div className={`image-unavailable ${className}`} role="img" aria-label={`${screenshot.alt}: image unavailable`}>
        <ImageOff size={24} aria-hidden="true" />
        <span>Screenshot unavailable</span>
      </div>
    );
  }

  return (
    <img
      className={className}
      src={attempt === 0 ? (full ? screenshot.fullSrc : screenshot.src) : screenshot.fallback}
      alt={screenshot.alt}
      draggable={false}
      loading={eager ? 'eager' : 'lazy'}
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setAttempt((previous) => previous + 1)}
    />
  );
}