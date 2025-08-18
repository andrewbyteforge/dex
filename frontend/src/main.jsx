import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import 'bootstrap/dist/css/bootstrap.min.css';

// Global diagnostics so a silent error can't blank the page without clues
window.addEventListener('error', (e) => {
  // eslint-disable-next-line no-console
  console.error('[window.error]', e.message, e.error);
});
window.addEventListener('unhandledrejection', (e) => {
  // eslint-disable-next-line no-console
  console.error('[unhandledrejection]', e.reason);
});

function mount() {
  const rootEl = document.getElementById('root');
  if (!rootEl) {
    // eslint-disable-next-line no-console
    console.error('[main] #root not found in index.html');
    const fallback = document.createElement('div');
    fallback.style.color = 'red';
    fallback.style.padding = '16px';
    fallback.textContent = 'Fatal: #root element not found';
    document.body.appendChild(fallback);
    return;
  }

  // Breadcrumbs so we know the script actually ran
  // eslint-disable-next-line no-console
  console.log('[main] mounting to #root', rootEl);

  try {
    ReactDOM.createRoot(rootEl).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    );
    // eslint-disable-next-line no-console
    console.log('[main] render() called');
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[main] render failed:', err);
    rootEl.innerHTML = `<pre style="color:red;white-space:pre-wrap">Render failed: ${String(
      (err && err.message) || err,
    )}</pre>`;
  }
}

// Kick things off
mount();
