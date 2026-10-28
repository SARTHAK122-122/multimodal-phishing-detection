import {
  ArrowDown, ArrowRight, ArrowUpRight, FileSearch, Globe, Mail,
  MessageSquare, QrCode, ShieldCheck, Sparkles,
} from 'lucide-react'

const REPO_URL = 'https://github.com/SARTHAK122-122/multimodal-phishing-detection'

const SCANNERS = [
  {
    icon: Globe,
    title: 'Websites & URLs',
    description: 'Inspect URL signals, page content and suspicious behavior.',
    label: 'URL + page evidence',
  },
  {
    icon: Mail,
    title: 'Email',
    description: 'Review message content, sender details and embedded links.',
    label: 'Message + links',
  },
  {
    icon: MessageSquare,
    title: 'SMS',
    description: 'Check suspicious texts, sender context and linked destinations.',
    label: 'Text + links',
  },
  {
    icon: QrCode,
    title: 'QR codes',
    description: 'Decode a QR destination and analyze it without visiting the link.',
    label: 'Image + destination',
  },
]

export default function PublicDemoPage() {
  return (
    <div className="public-demo">
      <header className="demo-nav">
        <a className="demo-brand" href="#top" aria-label="PhishGuard AI home">
          <span className="demo-brand-icon"><ShieldCheck size={20} /></span>
          <span>PhishGuard <b>AI</b></span>
        </a>
        <nav className="demo-nav-links" aria-label="Main navigation">
          <a href="#capabilities">Capabilities</a>
          <a href="#approach">How it works</a>
          <a href="#results">Model results</a>
        </nav>
        <a className="demo-nav-cta" href={REPO_URL} target="_blank" rel="noreferrer">
          View source <ArrowUpRight size={16} />
        </a>
      </header>

      <main>
        <section className="demo-hero" id="top">
          <div className="demo-hero-copy">
            <div className="demo-status">
              <span className="demo-status-dot" />
              Public frontend preview <span aria-hidden="true">·</span> API not connected
            </div>
            <p className="demo-eyebrow"><Sparkles size={14} /> MULTIMODAL THREAT ANALYSIS</p>
            <h1>Know what looks suspicious.<br /><span>See exactly why.</span></h1>
            <p className="demo-intro">
              PhishGuard AI examines websites, emails, SMS and QR codes,
              then explains the evidence behind every verdict.
            </p>
            <div className="demo-actions">
              <a className="demo-button primary" href={REPO_URL} target="_blank" rel="noreferrer">
                Explore the project <ArrowRight size={17} />
              </a>
              <a className="demo-button secondary" href="#capabilities">
                Discover capabilities <ArrowDown size={16} />
              </a>
            </div>
            <div className="demo-highlights" aria-label="Project highlights">
              <span><ShieldCheck size={16} /> Evidence-first analysis</span>
              <span><FileSearch size={16} /> Explainable results</span>
            </div>
          </div>

          <div className="demo-visual" aria-label="PhishGuard analysis pipeline illustration">
            <div className="demo-visual-glow" />
            <div className="demo-orbit orbit-outer" />
            <div className="demo-orbit orbit-inner" />
            <div className="demo-visual-top">
              <span className="demo-window-dots"><i /><i /><i /></span>
              <span>ANALYSIS PIPELINE</span>
              <span className="demo-live-dot" />
            </div>
            <div className="demo-flow">
              <div className="demo-inputs">
                <span><Globe size={16} /> URL</span>
                <span><Mail size={16} /> Email</span>
                <span><MessageSquare size={16} /> SMS</span>
                <span><QrCode size={16} /> QR</span>
              </div>
              <div className="demo-flow-line"><span /></div>
              <div className="demo-core">
                <ShieldCheck size={30} />
                <b>Fusion engine</b>
                <small>signals · rules · evidence</small>
              </div>
              <div className="demo-flow-line"><span /></div>
              <div className="demo-output">
                <FileSearch size={19} />
                <span><b>Explainable verdict</b><small>Evidence + caveats</small></span>
                <ArrowRight size={16} />
              </div>
            </div>
            <div className="demo-visual-foot">
              <span>Signals stay transparent</span><span>●</span><span>No silent safe defaults</span>
            </div>
          </div>
        </section>

        <section className="demo-section demo-capabilities" id="capabilities">
          <div className="demo-section-heading">
            <div>
              <p className="demo-eyebrow">ONE PLATFORM · FOUR INPUTS</p>
              <h2>Protection across the places threats arrive</h2>
            </div>
            <p>Different attack surfaces need different signals. PhishGuard combines input-specific analysis into a clear, reviewable report.</p>
          </div>
          <div className="demo-capability-grid">
            {SCANNERS.map(({ icon: Icon, title, description, label }) => (
              <article className="demo-capability-card" key={title}>
                <span className="demo-capability-icon"><Icon size={20} /></span>
                <span className="demo-card-label">{label}</span>
                <h3>{title}</h3>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="demo-approach" id="approach">
          <div className="demo-section-heading">
            <div>
              <p className="demo-eyebrow">BUILT TO SHOW ITS WORK</p>
              <h2>From signal to explanation</h2>
            </div>
            <p>Transparent analysis makes it easier to understand a warning—and its limitations.</p>
          </div>
          <div className="demo-steps">
            <article><span>01</span><h3>Submit an input</h3><p>Choose a URL, message or QR image to analyze.</p></article>
            <article><span>02</span><h3>Analyze signals</h3><p>URL models and transparent content rules contribute relevant evidence.</p></article>
            <article><span>03</span><h3>Review the verdict</h3><p>See risk indicators, explanations and any missing-model caveats.</p></article>
          </div>
          <div className="demo-honesty">
            <ShieldCheck size={20} />
            <p><b>A verdict is guidance, not a guarantee.</b> Risk scores are not calibrated probabilities, and missing analysis is reported—not treated as proof that something is safe.</p>
          </div>
        </section>

        <section className="demo-results" id="results">
          <div className="demo-results-copy">
            <p className="demo-eyebrow">MEASURED, NOT MARKETING</p>
            <h2>Model performance, with context.</h2>
            <p>URL-model hold-out results from the project evaluation. These are dataset measurements, not a promise of real-world detection accuracy.</p>
            <a href={`${REPO_URL}#measured-results-how-measured`} target="_blank" rel="noreferrer">
              Read how these were measured <ArrowUpRight size={15} />
            </a>
          </div>
          <div className="demo-metrics">
            <div><span>Random Forest</span><strong>95.59%</strong><small>hold-out accuracy</small></div>
            <div><span>XGBoost</span><strong>95.83%</strong><small>hold-out accuracy</small></div>
            <p>URL models · v3 host-only features · measured 2026-10-11</p>
          </div>
        </section>

        <section className="demo-cta">
          <span className="demo-cta-icon"><ShieldCheck size={23} /></span>
          <div>
            <p className="demo-eyebrow">OPEN SOURCE · RESEARCH PROJECT</p>
            <h2>Explore the system behind the demo.</h2>
            <p>This GitHub Pages build is a frontend showcase. Live scanning and accounts need the project's API to be hosted and connected.</p>
          </div>
          <a className="demo-button primary" href={REPO_URL} target="_blank" rel="noreferrer">
            View repository <ArrowUpRight size={17} />
          </a>
        </section>
      </main>

      <footer className="demo-footer">
        <a className="demo-brand" href="#top"><span className="demo-brand-icon"><ShieldCheck size={18} /></span>PhishGuard <b>AI</b></a>
        <span>Built for safer clicks. Always verify suspicious requests independently.</span>
        <a href={`${REPO_URL}#quick-start`} target="_blank" rel="noreferrer">Run locally <ArrowUpRight size={14} /></a>
      </footer>
    </div>
  )
}
