import Image from "next/image";

const steps = [
  ["09:04:12", "Navigate", "/crm.html", "success"],
  ["09:04:13", "Search customer", "Acme Ltd", "success"],
  ["09:04:14", "Assert customer", "CRM-0042", "success"],
  ["09:04:16", "Checkpoint", "status = qualified", "checkpoint"],
  ["09:04:17", "Approval", "submit-crm", "approval"],
  ["09:04:19", "Submit", "external action approved", "success"],
  ["09:04:20", "Assertion", "Saved", "success"],
];

function StatusDot({ tone }: { tone: string }) {
  return <span className={`status-dot ${tone}`} aria-hidden="true" />;
}

function Metric({ value, label, detail }: { value: string; label: string; detail: string }) {
  return (
    <div className="metric-card">
      <p className="metric-value">{value}</p>
      <p className="metric-label">{label}</p>
      <p className="metric-detail">{detail}</p>
    </div>
  );
}

export default function Home() {
  return (
    <main>
      <nav className="topbar shell" aria-label="Primary navigation">
        <a className="brand" href="#overview"><span className="brand-mark">T</span>TraceBrowser</a>
        <div className="nav-links">
          <a href="#tasks">Tasks</a>
          <a href="#run-detail">Runs</a>
          <a href="#failures">Failures</a>
          <a href="#artifacts">Artifacts</a>
          <a href="https://github.com/ANKOHR/tracebrowser" target="_blank" rel="noreferrer">Source ↗</a>
          <span className="nav-status">PUBLIC SOURCE / CONTROLLED FIXTURES</span>
        </div>
      </nav>

      <section className="hero shell" id="overview">
        <div className="eyebrow"><span className="live-dot" /> CONTROLLED FIXTURE WORKSPACE <span className="slash">/</span> LOCAL EVIDENCE</div>
        <div className="hero-grid">
          <div>
            <h1>Browser work you can <em>replay.</em></h1>
            <p className="hero-copy">TraceBrowser turns browser tasks into versioned, bounded executions with screenshots, DOM evidence, assertions and recoverable checkpoints at every step.</p>
            <div className="hero-actions">
              <a className="button primary" href="#run-detail">Inspect flagship run <span>↓</span></a>
              <a className="button quiet" href="https://github.com/ANKOHR/tracebrowser" target="_blank" rel="noreferrer">Read source ↗</a>
            </div>
          </div>
          <div className="hero-note">
            <p className="note-label">RUNTIME POSTURE</p>
            <p className="note-title">Deterministic by default.</p>
            <p>Credential-free synthetic sites. Explicit selectors. No CAPTCHA bypass. A failed task cannot quietly become a success.</p>
            <div className="note-rule" />
            <div className="note-foot"><span>40</span> backend tests <span>·</span> <span>50</span> benchmark cases</div>
          </div>
        </div>
      </section>

      <section className="metrics shell" aria-label="Workspace metrics">
        <Metric value="3" label="Showcase runs" detail="CRM · portal · recovery" />
        <Metric value="100%" label="Local completion" detail="controlled synthetic fixtures" />
        <Metric value="0" label="False successes" detail="benchmark target held" />
        <Metric value="0" label="Credentials used" detail="no third-party sites" />
      </section>

      <section className="content-shell shell" id="tasks">
        <div className="section-heading"><div><p className="kicker">TASK LIBRARY</p><h2>Versioned workflows</h2></div><span className="muted-count">3 fixtures / v1</span></div>
        <div className="task-grid">
          <article className="task-card selected"><div className="task-icon orange">↗</div><div><h3>CRM data entry</h3><p>Search, qualify and approval-gate a synthetic customer update.</p></div><span className="arrow">→</span></article>
          <article className="task-card"><div className="task-icon teal">▦</div><div><h3>Portal extraction</h3><p>Navigate a read-only portal and export a normalized table.</p></div><span className="arrow">→</span></article>
          <article className="task-card"><div className="task-icon violet">⌁</div><div><h3>Broken UI recovery</h3><p>Use an authored fallback when a known selector changes.</p></div><span className="arrow">→</span></article>
        </div>
      </section>

      <section className="run-layout shell" id="run-detail">
        <div className="section-heading"><div><p className="kicker">RUN DETAIL / RUN_CRM_V1</p><h2>CRM data entry</h2></div><div className="run-status"><StatusDot tone="success" /> SUCCESS <span>·</span> 2.8s</div></div>
        <div className="run-summary">
          <div><p className="summary-label">TASK VERSION</p><p className="summary-value">crm-data-entry <span>v1</span></p></div>
          <div><p className="summary-label">EXECUTION</p><p className="summary-value">Playwright / headless</p></div>
          <div><p className="summary-label">POLICY</p><p className="summary-value">8 actions · 1 approval</p></div>
          <div><p className="summary-label">IDEMPOTENCY</p><p className="summary-value mono">showcase:crm:v1</p></div>
        </div>
        <div className="run-main">
          <div className="timeline">
            {steps.map(([time, title, detail, tone]) => (
              <div className="timeline-row" key={`${time}-${title}`}>
                <span className="timeline-time">{time}</span><StatusDot tone={tone} /><div className="timeline-copy"><strong>{title}</strong><span>{detail}</span></div><span className="timeline-latency">{title === "Approval" ? "1.0s" : "42ms"}</span>
              </div>
            ))}
          </div>
          <aside className="evidence-panel">
            <p className="kicker">SELECTED EVIDENCE</p>
            <h3>Submit / external action</h3>
            <div className="evidence-status"><StatusDot tone="approval" /> APPROVED BEFORE EXECUTION</div>
            <dl><div><dt>Selector</dt><dd className="mono">[data-testid=&apos;submit-crm&apos;]</dd></div><div><dt>Input</dt><dd>external_submission: true</dd></div><div><dt>Retries</dt><dd>0</dd></div><div><dt>DOM evidence</dt><dd>1,842 chars captured</dd></div></dl>
            <div className="evidence-caption">The browser process is disposable; the trace is not. Resume rebuilds the deterministic prefix before continuing.</div>
          </aside>
        </div>
      </section>

      <section className="artifact-section shell" id="artifacts">
        <div className="section-heading"><div><p className="kicker">ARTIFACTS</p><h2>Evidence, not just status</h2></div><span className="muted-count">PNG · DOM · JSON</span></div>
        <div className="artifact-grid">
          <article className="artifact-card"><Image src="/artifacts/crm-success.png" alt="Synthetic CRM success screen" width={1280} height={720} /><div className="artifact-meta"><div><strong>crm-success.png</strong><span>Final approved state</span></div><span className="artifact-tag">SCREENSHOT</span></div></article>
          <article className="artifact-card"><Image src="/artifacts/portal-extraction.png" alt="Synthetic portal table extraction screen" width={1280} height={720} /><div className="artifact-meta"><div><strong>portal-extraction.png</strong><span>Table assertion passed</span></div><span className="artifact-tag">SCREENSHOT</span></div></article>
          <article className="artifact-card"><Image src="/artifacts/broken-ui-recovered.png" alt="Synthetic broken UI fallback recovery screen" width={1280} height={720} /><div className="artifact-meta"><div><strong>broken-ui-recovered.png</strong><span>Explicit role fallback</span></div><span className="artifact-tag">SCREENSHOT</span></div></article>
        </div>
      </section>

      <section className="failure-section shell" id="failures">
        <div><p className="kicker">FAILURE HANDLING</p><h2>Make the boundary visible.</h2><p className="section-copy">TraceBrowser stops on missing selectors, failed assertions, blocked domains and budget violations. It records the failure class, bounded DOM and screenshot when the browser is still available.</p></div>
        <div className="failure-list"><div><StatusDot tone="error" /><span>SELECTOR_NOT_FOUND</span><small>no selector matched</small></div><div><StatusDot tone="error" /><span>ASSERTION_FAILED</span><small>expected text was absent</small></div><div><StatusDot tone="warning" /><span>BLOCKED_BY_POLICY</span><small>domain or budget boundary</small></div><div><StatusDot tone="neutral" /><span>AUTH_REQUIRED</span><small>transparent stop; no bypass</small></div></div>
      </section>

      <footer className="footer shell"><div><span className="brand-mark small">T</span><span>TraceBrowser</span></div><span>Reliable, replayable browser automation with evidence for every action.</span><a href="https://github.com/ANKOHR/tracebrowser" target="_blank" rel="noreferrer">Source + evidence ↗</a></footer>
    </main>
  );
}
