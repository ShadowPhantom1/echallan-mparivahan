import { useState } from 'react';
import { app } from '../data/app';

export default function AppIcon({ className = '' }: { className?: string }) {
  const [failed, setFailed] = useState(false);

  return (
    <img
      className={`app-icon ${className}`}
      src={failed ? '/mparivahan-icon.svg' : app.icon}
      onError={() => setFailed(true)}
      alt="NextGen mParivahan app icon"
      width="112"
      height="112"
      decoding="async"
      referrerPolicy="no-referrer"
    />
  );
}