import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import {
  ArrowLeft, ArrowRight, Bookmark, BookmarkCheck, BookmarkPlus, BookMarked,
  Check, CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, Copy, Download,
  Gamepad2, Globe, Info, Landmark, LayoutGrid, LockKeyhole, Mail,
  MoreVertical, Search, Share2, Star, ThumbsUp, Trash2, UserRound, X as XIcon,
} from 'lucide-react';
import AppIcon from './components/AppIcon';
import Dialog from './components/Dialog';
import ScreenshotImage from './components/ScreenshotImage';
import { app, screenshots, vehicleDetails, stats, reviews, type Review } from './data/app';
import { fetchApk, formatBytes, saveApk, type DownloadProgress } from './utils/downloadApk';

function Stars({ value, size = 14 }: { value: number; size?: number }) {
  return (
    <span className="inline-stars" role="img" aria-label={`${value} out of 5 stars`}>
      {[0, 1, 2, 3, 4].map((index) => (
        <span key={index} className="star-glyph" style={{ width: size, height: size }}>
          <Star size={size} strokeWidth={0} fill="currentColor" className="empty-star" aria-hidden="true" />
          <span className="star-fill" style={{ width: `${Math.min(1, Math.max(0, value - index)) * 100}%` }}>
            <Star size={size} strokeWidth={0} fill="currentColor" aria-hidden="true" />
          </span>
        </span>
      ))}
    </span>
  );
}

function ReviewCard({ review, onNotice }: { review: Review; onNotice: (message: string) => void }) {
  const [vote, setVote] = useState<'yes' | 'no' | null>(() => {
    const stored = readString(`review-vote-${review.id}`);
    return stored === 'yes' || stored === 'no' ? stored : null;
  });

  function voteHelpful(answer: 'yes' | 'no') {
    const next = vote === answer ? null : answer;
    setVote(next);
    writeString(`review-vote-${review.id}`, next ?? '');
    onNotice('Review feedback saved in this browser only');
  }

  async function copyReview() {
    try {
      await navigator.clipboard.writeText(`${review.name}\n${review.date}\n${review.text}`);
      onNotice('Review excerpt copied');
    } catch {
      onNotice('Clipboard unavailable. Select the review text to copy it.');
    }
  }
  return (
    <article className="review-card">
      <div className="review-head">
        <span className="review-avatar" style={{ background: review.color }}>{review.initial}</span>
        <div className="review-meta">
          <strong>{review.name}</strong>
        </div>
        <button className="icon-button review-more" aria-label={`Copy review by ${review.name}`} onClick={copyReview}><Copy size={17} /></button>
      </div>
      <div className="review-rating-row">
        {review.rating !== undefined && <Stars value={review.rating} />}
        <span className="review-date">{review.date}</span>
      </div>
      <p className="review-text">{review.text}</p>
      {review.reply && (
        <div className="review-reply">
          <div className="reply-head"><strong>National Informatics Centre.</strong>{review.replyDate && <span>{review.replyDate}</span>}</div>
          <p>{review.reply}</p>
        </div>
      )}
      <div className="review-helpful">
        {review.helpful !== undefined && <span>{review.helpful.toLocaleString('en-IN')} people found this review helpful in the source listing</span>}
        <div className="helpful-buttons">
          <span>Did you find this helpful?</span>
          <button className={vote === 'yes' ? 'helpful-yes active' : 'helpful-yes'} aria-pressed={vote === 'yes'} onClick={() => voteHelpful('yes')}><ThumbsUp size={14} />Yes</button>
          <button className={vote === 'no' ? 'helpful-no active' : 'helpful-no'} aria-pressed={vote === 'no'} onClick={() => voteHelpful('no')}>No</button>
        </div>
      </div>
    </article>
  );
}

type DialogName = 'gallery' | 'about' | 'age' | 'government' | 'safety'
  | 'developer' | 'search' | 'you' | 'share' | 'category'
  | 'downloads' | 'devices' | 'install-help' | 'reviews-info' | null;

type DownloadStage = 'idle' | 'pending' | 'downloading' | 'downloaded' | 'error';

function readString(key: string) {
  try {
    return localStorage.getItem(key) ?? '';
  } catch {
    return '';
  }
}

function writeString(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Controls still work when browser storage is unavailable.
  }
}

const dialogTitles: Record<Exclude<DialogName, null>, string> = {
  gallery: 'App screenshots',
  about: 'About this app',
  age: 'Content rating',
  government: 'Government app',
  safety: 'Data safety',
  developer: 'About the developer',
  search: 'Search apps',
  you: 'Your app library',
  share: 'Share this app',
  category: 'App category',
  downloads: 'Downloads',
  devices: 'Download options',
  'install-help': 'Open the downloaded APK',
  'reviews-info': 'About ratings and reviews',
};

export default function App() {
  const [saved, setSaved] = useState(() => readString('mparivahan-saved') === 'true');
  const [downloadStage, setDownloadStage] = useState<DownloadStage>('idle');
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgress>({ received: 0, total: null });
  const [downloadError, setDownloadError] = useState('');
  const [dialog, setDialog] = useState<DialogName>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [toast, setToast] = useState('');
  const [screenshotIndex, setScreenshotIndex] = useState(0);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('Productivity');
  const [contactOpen, setContactOpen] = useState(false);
  const [activeNav, setActiveNav] = useState('Search');

  const galleryRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuTriggerRef = useRef<HTMLButtonElement>(null);
  const shareInputRef = useRef<HTMLInputElement>(null);
  const downloadController = useRef<AbortController | null>(null);

  const closeDialog = useCallback(() => setDialog(null), []);
  const openDialog = useCallback((name: DialogName) => {
    if (menuRef.current?.contains(document.activeElement)) menuTriggerRef.current?.focus();
    setMenuOpen(false);
    setDialog(name);
  }, []);

  useEffect(() => writeString('mparivahan-saved', String(saved)), [saved]);
  useEffect(() => {
    try { localStorage.removeItem('mparivahan-install-stage'); } catch { /* No native installation state is stored. */ }
    return () => downloadController.current?.abort();
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(''), 3200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  useEffect(() => {
    if (!menuOpen) return;
    menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    const handleOutside = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    const handleMenuKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
        menuTriggerRef.current?.focus();
      }
      if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
        event.preventDefault();
        const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') ?? []);
        const index = items.findIndex((item) => item === document.activeElement);
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
        items[next]?.focus();
      }
    };
    document.addEventListener('pointerdown', handleOutside);
    document.addEventListener('keydown', handleMenuKey);
    return () => {
      document.removeEventListener('pointerdown', handleOutside);
      document.removeEventListener('keydown', handleMenuKey);
    };
  }, [menuOpen]);

  useEffect(() => {
    if (dialog !== 'gallery') return;
    const handleArrow = (event: KeyboardEvent) => {
      if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
        event.preventDefault();
        const direction = event.key === 'ArrowRight' ? 1 : -1;
        setScreenshotIndex((previous) => (previous + direction + screenshots.length) % screenshots.length);
      }
    };
    document.addEventListener('keydown', handleArrow);
    return () => document.removeEventListener('keydown', handleArrow);
  }, [dialog]);

  const updateGalleryControls = useCallback(() => {
    const element = galleryRef.current;
    if (!element) return;
    setCanScrollLeft(element.scrollLeft > 4);
    setCanScrollRight(element.scrollLeft + element.clientWidth < element.scrollWidth - 4);
  }, []);

  useEffect(() => {
    const element = galleryRef.current;
    if (!element) return;
    const observer = new ResizeObserver(updateGalleryControls);
    observer.observe(element);
    updateGalleryControls();
    return () => observer.disconnect();
  }, [updateGalleryControls]);

  async function startDownload() {
    if (downloadController.current) return;
    const controller = new AbortController();
    downloadController.current = controller;
    setMenuOpen(false);
    setDownloadError('');
    setDownloadProgress({ received: 0, total: null });
    setDownloadStage('pending');
    try {
      const blob = await fetchApk(app.apkUrl, controller.signal, (next) => {
        if (!controller.signal.aborted) {
          setDownloadStage('downloading');
          setDownloadProgress(next);
        }
      });
      if (controller.signal.aborted) return;
      saveApk(blob, app.apkFileName);
      setDownloadStage('downloaded');
      setToast('APK prepared. Confirm the save in your browser.');
    } catch (error) {
      if (controller.signal.aborted) return;
      setDownloadError(error instanceof TypeError ? 'Could not download the APK. Check your connection and try again.' : error instanceof Error ? error.message : 'Download unavailable. Please try again.');
      setDownloadStage('error');
    } finally {
      if (downloadController.current === controller) downloadController.current = null;
    }
  }

  function cancelDownload() {
    downloadController.current?.abort();
    downloadController.current = null;
    setDownloadStage('idle');
    setDownloadProgress({ received: 0, total: null });
    setToast('Download cancelled');
  }

  async function handleOpenApk() {
    // Try to re-download and share (opens "Open with" dialog on Android)
    if (downloadController.current) return;
    const controller = new AbortController();
    downloadController.current = controller;
    setDownloadError('');
    setDownloadProgress({ received: 0, total: null });
    setDownloadStage('pending');
    try {
      const blob = await fetchApk(app.apkUrl, controller.signal, (next) => {
        if (!controller.signal.aborted) {
          setDownloadStage('downloading');
          setDownloadProgress(next);
        }
      });
      if (controller.signal.aborted) return;
      
      // Try Web Share API with file (shows "Open with" on Android)
      const file = new File([blob], app.apkFileName, { type: 'application/vnd.android.package-archive' });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: app.name, text: app.tagline });
        setToast('Opening APK...');
      } else {
        // Fallback: save and show help
        saveApk(blob, app.apkFileName);
        setDownloadStage('downloaded');
        setToast('APK saved. Tap to open from downloads.');
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      // Fallback to help dialog
      openDialog('install-help');
    } finally {
      if (downloadController.current === controller) downloadController.current = null;
    }
  }

  function toggleSaved() {
    setSaved((previous) => !previous);
    setToast(saved ? 'Removed from your saved apps' : 'Added to your saved apps');
  }

  function scrollGallery(direction: number) {
    const element = galleryRef.current;
    if (!element) return;
    element.scrollBy({
      left: direction * element.clientWidth * 0.72,
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    });
  }

  function moveScreenshot(direction: number) {
    setScreenshotIndex((previous) => (previous + direction + screenshots.length) % screenshots.length);
  }

  async function shareApp() {
    menuTriggerRef.current?.focus();
    setMenuOpen(false);
    if (navigator.share) {
      try {
        await navigator.share({ title: app.name, text: app.tagline, url: window.location.href });
        return;
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return;
      }
    }
    setDialog('share');
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setToast('App link copied');
    } catch {
      shareInputRef.current?.focus();
      shareInputRef.current?.select();
      setToast('Select and copy the highlighted link');
    }
  }

  function showAppListing() {
    closeDialog();
    setActiveNav('Apps');
    window.scrollTo({ top: 0, behavior: 'auto' });
  }

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    if (searchMatches) showAppListing();
  }

  const searchableText = 'nextgen mparivahan national informatics centre nic vehicle transport driving licence license rc dl government productivity auto vehicles';
  const searchMatches = query.trim().toLowerCase().split(/\s+/).every((word) => searchableText.includes(word));
  const busy = downloadStage === 'pending' || downloadStage === 'downloading';
  const progress = downloadProgress.total ? Math.min(100, Math.floor(downloadProgress.received / downloadProgress.total * 100)) : null;

  return (
    <div className="app-shell">
      <main className="listing" id="main-content" data-dialog-background>
        <header className="toolbar" aria-label="App actions">
          <button className="icon-button back-button" aria-label="Back to app search" onClick={() => {
            setQuery('');
            openDialog('search');
          }}>
            <ArrowLeft size={27} strokeWidth={1.9} />
          </button>
          <div className="toolbar-actions">
            <button
              className={`icon-button save-button ${saved ? 'is-saved' : ''}`}
              aria-label={saved ? 'Remove app from saved apps' : 'Save this app'}
              aria-pressed={saved}
              onClick={toggleSaved}
            >
              {saved ? <BookmarkCheck size={26} /> : <BookmarkPlus size={26} />}
            </button>
            <div className="overflow-menu" ref={menuRef}>
              <button ref={menuTriggerRef} className="icon-button" aria-label="More options" aria-expanded={menuOpen} aria-haspopup="menu" onClick={() => setMenuOpen((previous) => !previous)}>
                <MoreVertical size={27} />
              </button>
              {menuOpen && (
                <div className="menu-panel" role="menu" onBlur={(event) => {
                  if (!menuRef.current?.contains(event.relatedTarget)) setMenuOpen(false);
                }}>
                  <button role="menuitem" onClick={shareApp}><Share2 size={18} />Share</button>
                </div>
              )}
            </div>
          </div>
        </header>

        <section className="app-overview" aria-labelledby="app-title">
          <div className="app-identity">
            <AppIcon className="hero-app-icon" />
            <div className="identity-copy">
              <h1 id="app-title">{app.name}</h1>
              <button className="developer-link" onClick={() => openDialog('developer')}>{app.developer}</button>
            </div>
          </div>

          <div className="app-metadata" role="group" tabIndex={0} aria-label="App information: rating, content rating, Government and Downloads. Scroll horizontally on small screens.">
            <button className="metadata-item" onClick={() => document.getElementById('ratings')?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' })} aria-label="3.7 stars, 7 lakh reviews. View ratings.">
              <span className="metadata-value rating-value">{app.rating}<Star size={18} fill="currentColor" strokeWidth={0} /></span>
              <span className="metadata-label">{app.reviews} reviews</span>
            </button>
            <button className="metadata-item" onClick={() => openDialog('age')} aria-label="Rated for ages 3 and up. More information.">
              <span className="age-rating" aria-hidden="true">3+</span>
              <span className="metadata-label">Rated for 3+ <Info size={13} /></span>
            </button>
            <button className="metadata-item" onClick={() => openDialog('government')}>
              <Landmark className="government-icon" size={28} strokeWidth={1.8} />
              <span className="metadata-label">Government</span>
            </button>
            <button className="metadata-item downloads-metadata" onClick={() => openDialog('downloads')} aria-label={`${stats.downloads} downloads, reference figure`}>
              <span className="metadata-value">{stats.downloads}</span>
              <span className="metadata-label">Downloads</span>
            </button>
          </div>

          <div className="install-area">
            {(downloadStage === 'idle' || downloadStage === 'error') && (
              <div className="install-controls">
                <button className="install-button" onClick={startDownload} aria-label={`Download the ${app.name} APK`}>{downloadStage === 'error' ? 'Try again' : 'Install'}</button>
                <button className="device-button" aria-label="Download and installation options" aria-haspopup="dialog" onClick={() => openDialog('devices')}><ChevronDown size={24} /></button>
              </div>
            )}

            {downloadStage === 'pending' && (
              <div className="install-progress-wrap">
                <div className="progress-header">
                  <span>Preparing download...</span>
                  <button className="progress-cancel" aria-label="Cancel download" onClick={cancelDownload}><XIcon size={20} /></button>
                </div>
                <div className="progress-bar" role="progressbar" aria-label="Download pending">
                  <span className="progress-fill indeterminate" />
                </div>
              </div>
            )}

            {downloadStage === 'downloading' && (
              <div className="install-progress-wrap">
                <div className="progress-header">
                  <span>{progress !== null ? `${progress}% of ${formatBytes(downloadProgress.total!)}` : `${formatBytes(downloadProgress.received)} received`}</span>
                  <button className="progress-cancel" aria-label="Cancel download" onClick={cancelDownload}><XIcon size={20} /></button>
                </div>
                <div className="progress-bar" role="progressbar" aria-valuenow={progress ?? undefined} aria-valuemin={0} aria-valuemax={100} aria-label="Downloading APK">
                  <span className={`progress-fill ${progress === null ? 'indeterminate' : ''}`} style={progress !== null ? { width: `${progress}%` } : undefined} />
                </div>
              </div>
            )}

            {downloadStage === 'downloaded' && (
              <div className="installed-controls">
                <button className="install-button open-button primary" onClick={handleOpenApk}>
                  <CheckCircle2 size={20} />
                  <span>Open</span>
                </button>
                <button className="install-button ghost" onClick={startDownload}>Download again</button>
              </div>
            )}

            {downloadStage === 'error' && <p className="download-error" role="alert">{downloadError}</p>}
            <p className="install-caption">
              {downloadStage === 'downloaded'
                ? 'Save the APK, then open it on your Android phone.'
                : busy
                  ? 'Downloading the APK to your browser...'
                  : 'Download APK. Install on your phone.'}
            </p>
          </div>
        </section>

        <section className="screenshot-gallery" aria-label="App screenshots">
          <div className="gallery-track" ref={galleryRef} onScroll={updateGalleryControls} tabIndex={0} aria-label="Scroll to see all seven app screenshots">
            {screenshots.map((screenshot, index) => (
              <button className="screenshot-button" key={screenshot.src} aria-label={`Enlarge screenshot ${index + 1}: ${screenshot.alt}`} onClick={() => {
                setScreenshotIndex(index);
                openDialog('gallery');
              }}>
                <ScreenshotImage index={index} eager={index < 5} />
              </button>
            ))}
          </div>
          {canScrollLeft && <button className="gallery-arrow gallery-arrow-left" aria-label="Previous screenshots" onClick={() => scrollGallery(-1)}><ChevronLeft size={25} /></button>}
          {canScrollRight && <button className="gallery-arrow gallery-arrow-right" aria-label="More screenshots" onClick={() => scrollGallery(1)}><ChevronRight size={25} /></button>}
        </section>

        <section className="about-section" aria-labelledby="about-title">
          <h2 id="about-title"><button className="section-heading-button" onClick={() => openDialog('about')}>
            <span>About this app</span>
            <span className="section-arrow"><ArrowRight size={26} strokeWidth={1.8} /></span>
          </button></h2>
          <p className="app-tagline">Complete Transport Solution<span className="tagline-last"> for Citizen</span></p>
          <div className="category-buttons" aria-label="App categories">
            {['Productivity', 'Auto & vehicles'].map((name) => (
              <button key={name} onClick={() => {
                setCategory(name);
                openDialog('category');
              }}>{name}</button>
            ))}
          </div>
        </section>

        <section className="details-section safety-section" aria-labelledby="safety-title">
          <h2 id="safety-title"><button className="section-heading-button" onClick={() => openDialog('safety')}>
            <span>Data safety</span>
            <ArrowRight size={24} strokeWidth={1.8} />
          </button></h2>
          <p className="section-description">Information declared for the official app. An uploaded APK must be verified separately.</p>
          <div className="safety-list">
            <div><Share2 size={21} /><span>No data shared with third parties</span></div>
            <div><Info size={21} /><span>This app may collect location, personal info and other data</span></div>
            <div><LockKeyhole size={21} /><span>Data is encrypted in transit</span></div>
            <div><Trash2 size={21} /><span>You can request that data be deleted</span></div>
          </div>
          <button className="text-link section-detail-link" onClick={() => openDialog('safety')}>See details<ArrowRight size={17} /></button>
        </section>

        <section className="details-section ratings-section" id="ratings" aria-labelledby="ratings-title">
          <h2 id="ratings-title">Ratings and reviews</h2>
          <button className="ratings-source" onClick={() => openDialog('reviews-info')}>Reference ratings and published review excerpts<Info size={13} /></button>
          <div className="ratings-summary">
            <div className="rating-score-block">
              <span className="large-rating">{stats.rating}</span>
              <div className="rating-stars"><Stars value={Number(stats.rating)} size={16} /></div>
              <span className="review-count">{stats.ratingCount} reviews</span>
            </div>
            <div className="ratings-bars">
              {stats.ratingBars.map(({ stars, pct }) => (
                <div className="rating-row" key={stars}>
                  <span>{stars}</span>
                  <div className="rating-track"><span style={{ width: `${pct}%` }} /></div>
                </div>
              ))}
            </div>
          </div>

          <div className="reviews-list">
            {reviews.map((review) => <ReviewCard key={review.id} review={review} onNotice={setToast} />)}
          </div>
        </section>

        <section className="developer-section" aria-label="Developer contact">
          <h2><button className="contact-toggle" aria-expanded={contactOpen} aria-controls="developer-contact" onClick={() => setContactOpen((previous) => !previous)}>
            <span>App support</span><ChevronDown size={24} className={contactOpen ? 'rotated' : ''} />
          </button></h2>
          {contactOpen && (
            <div className="contact-links" id="developer-contact">
              <a href={app.website} target="_blank" rel="noopener noreferrer"><Globe size={21} /><span><strong>Website</strong><span>parivahan.gov.in</span></span><ArrowRight size={16} /></a>
              <a href={`mailto:${app.supportEmail}`}><Mail size={21} /><span><strong>Email</strong><span>{app.supportEmail}</span></span><ArrowRight size={17} /></a>
            </div>
          )}
        </section>
        <footer className="page-footer"></footer>
      </main>

      <nav className="bottom-navigation" aria-label="Main navigation" data-dialog-background>
        <div className="navigation-inner">
          <button className={`navigation-item ${activeNav === 'Games' ? 'navigation-active' : ''}`} onClick={() => { setActiveNav('Games'); setCategory('Games'); openDialog('category'); }}><span className="navigation-icon"><Gamepad2 size={27} /></span><span>Games</span></button>
          <button className={`navigation-item ${activeNav === 'Apps' ? 'navigation-active' : ''}`} onClick={showAppListing}><span className="navigation-icon"><LayoutGrid size={26} /></span><span>Apps</span></button>
          <button className={`navigation-item ${activeNav === 'Search' ? 'navigation-active' : ''}`} aria-current={activeNav === 'Search' ? 'page' : undefined} onClick={() => {
            setActiveNav('Search');
            setQuery('');
            openDialog('search');
          }}><span className="navigation-icon"><Search size={29} strokeWidth={1.8} /></span><span>Search</span></button>
          <button className={`navigation-item ${activeNav === 'Books' ? 'navigation-active' : ''}`} onClick={() => { setActiveNav('Books'); setCategory('Books'); openDialog('category'); }}><span className="navigation-icon"><BookMarked size={27} /></span><span>Books</span></button>
          <button className={`navigation-item ${activeNav === 'You' ? 'navigation-active' : ''}`} onClick={() => { setActiveNav('You'); openDialog('you'); }}><span className="navigation-icon"><UserRound size={28} /></span><span>You</span></button>
        </div>
      </nav>

      {toast && <div className="toast" role="status"><Check size={18} /><span>{toast}</span></div>}

      {dialog && (
        <Dialog key={dialog} title={dialog === 'category' ? category : dialogTitles[dialog]} onClose={closeDialog} className={dialog === 'gallery' ? 'gallery-dialog' : ''}>
          {dialog === 'gallery' && (
            <div className="screenshot-viewer">
              <div className="viewer-stage">
                <button className="viewer-arrow" aria-label="Previous screenshot" onClick={() => moveScreenshot(-1)}><ChevronLeft size={29} /></button>
                <ScreenshotImage key={screenshotIndex} index={screenshotIndex} className="viewer-image" eager full />
                <button className="viewer-arrow" aria-label="Next screenshot" onClick={() => moveScreenshot(1)}><ChevronRight size={29} /></button>
              </div>
              <div className="viewer-footer">
                <p>{screenshotIndex + 1} of {screenshots.length}</p>
                <div className="viewer-dots">
                  {screenshots.map((screenshot, index) => <button key={screenshot.src} aria-label={`View screenshot ${index + 1}`} aria-pressed={index === screenshotIndex} className={index === screenshotIndex ? 'active-dot' : ''} onClick={() => setScreenshotIndex(index)} />)}
                </div>
                <span className="viewer-keyboard-hint">Use arrow keys to browse</span>
              </div>
            </div>
          )}

          {dialog === 'about' && (
            <div className="dialog-content about-dialog-content">
              <div className="dialog-app-identity"><AppIcon /><div><h3>{app.name}</h3><p>{app.tagline}</p></div></div>
              <p>Access transport information, services and utilities from your phone. NextGen mParivahan brings vehicle and driving licence information together in one place.</p>
              <h3>Know your vehicle</h3>
              <p>Search a vehicle registered in India to view important details:</p>
              <ul>{vehicleDetails.map((detail) => <li key={detail}>{detail}</li>)}</ul>
              <h3>Your documents, on your phone</h3>
              <p>Verify driving licence details, create virtual RC and DL documents, access encrypted QR codes and find transport information.</p>
            </div>
          )}

          {dialog === 'age' && (
            <div className="dialog-content information-dialog">
              <span className="age-rating large-age-rating">3+</span><h3>Rated for 3+</h3>
              <p>Content rated 3+ is generally suitable for all age groups.</p>
            </div>
          )}

          {dialog === 'government' && (
            <div className="dialog-content information-dialog">
              <Landmark className="information-icon" size={43} strokeWidth={1.6} /><h3>Published by National Informatics Centre</h3>
              <p>NextGen mParivahan is a Government of India transport services app.</p>
              <p>This independent preview is not operated by NIC. The publisher of any uploaded APK must be verified separately.</p>
            </div>
          )}

          {dialog === 'safety' && (
            <div className="dialog-content">
              <p className="dialog-description">How this app collects and handles your data. Practices can vary by app version, usage and region.</p>
              <div className="safety-list modal-safety-list">
                <div><Share2 size={23} /><span><strong>No data shared with third parties</strong><small>According to the developer's declaration.</small></span></div>
                <div><Info size={23} /><span><strong>Some data may be collected</strong><small>Location, personal info and other data types.</small></span></div>
                <div><LockKeyhole size={23} /><span><strong>Encrypted in transit</strong><small>Data is transferred over a secure connection.</small></span></div>
                <div><Trash2 size={23} /><span><strong>Deletion requests available</strong><small>You can request deletion of your data.</small></span></div>
              </div>
            </div>
          )}

          {dialog === 'developer' && (
            <div className="dialog-content information-dialog">
              <Landmark className="information-icon" size={43} strokeWidth={1.6} /><h3>{app.developer}</h3>
              <p>National Informatics Centre is the publisher of the NextGen mParivahan app.</p>
            </div>
          )}

          {dialog === 'search' && (
            <div className="dialog-content">
              <form className="search-form" onSubmit={handleSearch}><Search size={21} /><input data-autofocus aria-label="Search this app listing" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search apps & games" autoComplete="off" /></form>
              <p className="search-label">In this app listing</p>
              {searchMatches ? (
                <button className="app-result" onClick={showAppListing}><AppIcon /><span><strong>{app.name}</strong><small>{app.developer}</small><small className="result-rating">{app.rating} <Star size={11} fill="currentColor" /> <span>Productivity</span></small></span><ChevronRight size={22} /></button>
              ) : <div className="empty-state"><Search size={34} strokeWidth={1.5} /><h3>No matching app</h3><p>Try "mParivahan", "vehicle" or "driving licence".</p></div>}
            </div>
          )}

          {dialog === 'you' && (
            <div className="dialog-content">
              <p className="dialog-description">Your preferences are saved in this browser. No account or sign-in is required.</p>
              <h3 className="small-heading">Saved apps</h3>
              {saved ? (
                <div className="saved-app-row"><AppIcon /><span><strong>{app.name}</strong><small>{app.developer}</small></span><button className="icon-button" aria-label="Remove saved app" onClick={toggleSaved}><BookmarkCheck size={23} /></button></div>
              ) : (
                <div className="empty-saved"><Bookmark size={25} /><p>No saved apps yet.</p><button className="text-link" onClick={toggleSaved}>Save NextGen mParivahan</button></div>
              )}
              <h3 className="small-heading">Downloads this visit</h3>
              {downloadStage === 'downloaded' ? (
                <div className="saved-app-row"><AppIcon /><span><strong>{app.name}</strong><small className="installed-tag"><CheckCircle2 size={13} /> APK prepared for saving</small></span><button className="text-link" onClick={() => openDialog('install-help')}>Open APK</button></div>
              ) : (
                <div className="empty-saved"><Download size={25} /><p>No APK prepared this visit.</p></div>
              )}
            </div>
          )}

          {dialog === 'share' && (
            <div className="dialog-content">
              <div className="dialog-app-identity"><AppIcon /><div><h3>{app.name}</h3><p>{app.tagline}</p></div></div>
              <label className="share-label" htmlFor="app-share-link">App link</label>
              <div className="share-input-row"><input id="app-share-link" ref={shareInputRef} value={typeof window !== 'undefined' ? window.location.href : ''} readOnly onFocus={(event) => event.target.select()} /><button className="icon-button" aria-label="Copy app link" onClick={copyLink}><Copy size={21} /></button></div>
              <button className="primary-action" onClick={copyLink}><Copy size={17} />Copy link</button>
            </div>
          )}

          {dialog === 'category' && (
            <div className="dialog-content">
              {category === 'Games' || category === 'Books' ? <div className="empty-state"><Search size={34} strokeWidth={1.5} /><h3>No {category.toLowerCase()} in this listing</h3><p>This independent page contains the mParivahan app only.</p><button className="text-link section-detail-link" onClick={showAppListing}>Back to app<ArrowRight size={16} /></button></div> : <><p className="dialog-description">NextGen mParivahan brings transport services and digital vehicle documents to your phone.</p><button className="app-result" onClick={showAppListing}><AppIcon /><span><strong>{app.name}</strong><small>{app.developer}</small></span><ChevronRight size={22} /></button></>}
            </div>
          )}

          {dialog === 'downloads' && <div className="dialog-content information-dialog"><Download className="information-icon" size={40} /><h3>{stats.downloads} Downloads</h3><p>This is the reference figure requested for the layout. It is not a count of APK downloads from this page, and is not live store data.</p><p>The official listing may show a different, newer figure.</p></div>}
          {dialog === 'reviews-info' && <div className="dialog-content information-dialog"><Info className="information-icon" size={40} /><h3>Reference information, not live ratings</h3><p>The overall rating and star-distribution chart reproduce the reference design. The distribution is illustrative and is not verified analytics.</p><p>Displayed comments are published excerpts from the official listing. Individual star ratings were not available, so they are not invented here. Helpful votes stay in your browser and are not sent to the app store.</p></div>}
          {dialog === 'devices' && <div className="dialog-content"><div className="dialog-app-identity"><AppIcon /><div><h3>{app.name}</h3><p>Direct APK download for Android</p></div></div><p className="dialog-description">Your browser chooses where to save the APK. An authorized, signed app file must be uploaded before downloading will work.</p><button className="primary-action" disabled={busy} onClick={() => { closeDialog(); void startDownload(); }}><Download size={18} />Download APK</button></div>}
          {dialog === 'install-help' && <div className="dialog-content information-dialog"><Download className="information-icon" size={40} /><h3>Continue on your Android phone</h3><ol className="installation-steps"><li>Finish saving the APK in your browser.</li><li>Open your download notification or Downloads folder.</li><li>Tap {app.apkFileName} and check the app's publisher.</li><li>If you trust the source, approve Android's installation prompt.</li></ol><p>After installation, open the app from your phone's app drawer. This website cannot confirm installation or launch the app without a verified app-opening link.</p><div style={{marginTop: 20}}><a href={app.playStoreUrl} target="_blank" rel="noopener noreferrer" className="primary-action" style={{display: 'inline-flex', width: 'auto', textDecoration: 'none', color: 'inherit'}}><Globe size={18} /><span style={{marginLeft: 10}}>Open on Google Play Store</span></a></div></div>}
        </Dialog>
      )}
    </div>
  );
}
