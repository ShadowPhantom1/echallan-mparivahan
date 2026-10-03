import { useEffect, useId, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';

type Props = {
  title: string;
  onClose: () => void;
  children: ReactNode;
  className?: string;
};

export default function Dialog({ title, onClose, children, className = '' }: Props) {
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    const background = Array.from(document.querySelectorAll<HTMLElement>('[data-dialog-background]'))
      .map((element) => ({ element, wasInert: element.hasAttribute('inert') }));
    document.body.style.overflow = 'hidden';
    const frame = requestAnimationFrame(() => {
      const preferred = panel.current?.querySelector<HTMLElement>('[data-autofocus]');
      (preferred ?? panel.current)?.focus();
      background.forEach(({ element }) => element.setAttribute('inert', ''));
    });

    // Keep keyboard focus inside the open dialog, then return it to its trigger.
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key !== 'Tab' || !panel.current) return;

      const focusable = Array.from(panel.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), select, textarea, [tabindex="0"]',
      )).filter((element) => element.getClientRects().length > 0);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first) {
        event.preventDefault();
        return;
      }
      if (!panel.current.contains(document.activeElement)) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panel.current)) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKey);
    return () => {
      cancelAnimationFrame(frame);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKey);
      background.forEach(({ element, wasInert }) => {
        if (!wasInert) element.removeAttribute('inert');
      });
      previousFocus?.focus({ preventScroll: true });
    };
  }, [onClose]);

  return (
    <div className="dialog-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <div
        ref={panel}
        className={`dialog-panel ${className}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <div className="dialog-heading">
          <h2 id={titleId}>{title}</h2>
          <button className="icon-button" onClick={onClose} aria-label="Close dialog">
            <X size={24} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}