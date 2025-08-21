/**
 * DEX Sniper Pro - PWA Installation Prompt Handler
 * 
 * Manages PWA installation prompts and provides a smooth
 * installation experience across different platforms.
 */

class PWAInstallPrompt {
  constructor() {
    this.deferredPrompt = null;
    this.isInstalled = false;
    this.isStandalone = false;
    this.platform = this.detectPlatform();
    
    this.init();
  }

  /**
   * Initialize PWA installation handlers
   */
  init() {
    // Check if app is already installed/standalone
    this.checkInstallationStatus();
    
    // Listen for beforeinstallprompt event
    window.addEventListener('beforeinstallprompt', (e) => {
      console.log('[PWA] beforeinstallprompt fired');
      
      // Prevent Chrome 67 and earlier from automatically showing the prompt
      e.preventDefault();
      
      // Store the event for later use
      this.deferredPrompt = e;
      
      // Show custom install UI
      this.showInstallBanner();
    });

    // Listen for app installed event
    window.addEventListener('appinstalled', (e) => {
      console.log('[PWA] App was installed');
      this.isInstalled = true;
      this.hideInstallBanner();
      this.showInstalledToast();
    });

    // Handle iOS installation instructions
    if (this.platform === 'ios' && !this.isStandalone) {
      this.showIOSInstallInstructions();
    }
  }

  /**
   * Detect the platform for platform-specific handling
   */
  detectPlatform() {
    const userAgent = navigator.userAgent.toLowerCase();
    
    if (/iphone|ipad|ipod/.test(userAgent)) {
      return 'ios';
    } else if (/android/.test(userAgent)) {
      return 'android';
    } else if (/windows/.test(userAgent)) {
      return 'windows';
    } else if (/mac/.test(userAgent)) {
      return 'mac';
    }
    
    return 'unknown';
  }

  /**
   * Check if the app is already installed or running in standalone mode
   */
  checkInstallationStatus() {
    // Check if running in standalone mode
    this.isStandalone = window.matchMedia('(display-mode: standalone)').matches ||
                      window.navigator.standalone === true;
    
    // Check if PWA is installed (Chrome/Edge)
    if ('getInstalledRelatedApps' in navigator) {
      navigator.getInstalledRelatedApps().then((relatedApps) => {
        this.isInstalled = relatedApps.length > 0;
      });
    }
  }

  /**
   * Show custom install banner
   */
  showInstallBanner() {
    if (this.isInstalled || this.isStandalone) return;
    
    // Remove existing banner
    this.hideInstallBanner();
    
    const banner = document.createElement('div');
    banner.id = 'pwa-install-banner';
    banner.className = 'pwa-install-banner';
    banner.innerHTML = `
      <div class="pwa-banner-content">
        <div class="pwa-banner-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="pwa-banner-text">
          <strong>Install DEX Sniper Pro</strong>
          <small>Get quick access and offline features</small>
        </div>
        <div class="pwa-banner-actions">
          <button id="pwa-install-btn" class="btn btn-primary btn-sm">Install</button>
          <button id="pwa-dismiss-btn" class="btn btn-outline-secondary btn-sm">Later</button>
        </div>
      </div>
    `;
    
    // Add styles
    const style = document.createElement('style');
    style.textContent = `
      .pwa-install-banner {
        position: fixed;
        bottom: 20px;
        left: 20px;
        right: 20px;
        background: white;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 1050;
        animation: slideUp 0.3s ease-out;
      }
      
      .pwa-banner-content {
        display: flex;
        align-items: center;
        padding: 16px;
        gap: 12px;
      }
      
      .pwa-banner-icon {
        color: #0d6efd;
        flex-shrink: 0;
      }
      
      .pwa-banner-text {
        flex-grow: 1;
        min-width: 0;
      }
      
      .pwa-banner-text strong {
        display: block;
        font-size: 14px;
        color: #212529;
      }
      
      .pwa-banner-text small {
        display: block;
        font-size: 12px;
        color: #6c757d;
        margin-top: 2px;
      }
      
      .pwa-banner-actions {
        display: flex;
        gap: 8px;
        flex-shrink: 0;
      }
      
      @keyframes slideUp {
        from {
          transform: translateY(100%);
          opacity: 0;
        }
        to {
          transform: translateY(0);
          opacity: 1;
        }
      }
      
      @media (max-width: 767px) {
        .pwa-install-banner {
          left: 10px;
          right: 10px;
          bottom: 90px; /* Account for mobile navigation */
        }
        
        .pwa-banner-content {
          padding: 12px;
        }
        
        .pwa-banner-actions {
          flex-direction: column;
        }
      }
    `;
    
    document.head.appendChild(style);
    document.body.appendChild(banner);
    
    // Add event listeners
    document.getElementById('pwa-install-btn').addEventListener('click', () => {
      this.triggerInstall();
    });
    
    document.getElementById('pwa-dismiss-btn').addEventListener('click', () => {
      this.hideInstallBanner();
      this.setInstallDismissed();
    });
  }

  /**
   * Hide install banner
   */
  hideInstallBanner() {
    const banner = document.getElementById('pwa-install-banner');
    if (banner) {
      banner.remove();
    }
  }

  /**
   * Trigger PWA installation
   */
  async triggerInstall() {
    if (!this.deferredPrompt) {
      console.warn('[PWA] No deferred prompt available');
      return;
    }

    // Show the install prompt
    this.deferredPrompt.prompt();

    // Wait for the user to respond to the prompt
    const { outcome } = await this.deferredPrompt.userChoice;
    console.log(`[PWA] User response to install prompt: ${outcome}`);

    if (outcome === 'accepted') {
      console.log('[PWA] User accepted the install prompt');
    } else {
      console.log('[PWA] User dismissed the install prompt');
    }

    // Clear the deferred prompt
    this.deferredPrompt = null;
    this.hideInstallBanner();
  }

  /**
   * Show iOS installation instructions
   */
  showIOSInstallInstructions() {
    if (this.getInstallDismissed()) return;
    
    // Show after a delay to not overwhelm user
    setTimeout(() => {
      const modal = document.createElement('div');
      modal.id = 'ios-install-modal';
      modal.className = 'modal fade';
      modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">Install DEX Sniper Pro</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body text-center">
              <div class="mb-3">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" stroke="currentColor" stroke-width="2" fill="none"/>
                  <line x1="12" y1="8" x2="12" y2="16" stroke="currentColor" stroke-width="2"/>
                  <line x1="8" y1="12" x2="16" y2="12" stroke="currentColor" stroke-width="2"/>
                </svg>
              </div>
              <p>To install this app on your iOS device:</p>
              <ol class="text-start">
                <li>Tap the Share button <strong>⎋</strong> in Safari</li>
                <li>Scroll down and tap <strong>"Add to Home Screen"</strong></li>
                <li>Tap <strong>"Add"</strong> to confirm</li>
              </ol>
              <p class="text-muted small">The app will appear on your home screen and work offline!</p>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-primary" data-bs-dismiss="modal">Got it</button>
            </div>
          </div>
        </div>
      `;
      
      document.body.appendChild(modal);
      
      // Show modal (requires Bootstrap JS)
      if (window.bootstrap) {
        const bsModal = new window.bootstrap.Modal(modal);
        bsModal.show();
        
        modal.addEventListener('hidden.bs.modal', () => {
          modal.remove();
          this.setInstallDismissed();
        });
      }
    }, 5000); // Show after 5 seconds
  }

  /**
   * Show installed success toast
   */
  showInstalledToast() {
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    toast.innerHTML = `
      <div class="toast show" role="alert">
        <div class="toast-header">
          <strong class="me-auto">DEX Sniper Pro</strong>
          <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">
          Successfully installed! You can now access the app from your home screen.
        </div>
      </div>
    `;
    
    document.body.appendChild(toast);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
      toast.remove();
    }, 5000);
  }

  /**
   * Check if install prompt was dismissed
   */
  getInstallDismissed() {
    return localStorage.getItem('pwa-install-dismissed') === 'true';
  }

  /**
   * Mark install prompt as dismissed
   */
  setInstallDismissed() {
    localStorage.setItem('pwa-install-dismissed', 'true');
  }

  /**
   * Reset install prompt (for testing)
   */
  resetInstallPrompt() {
    localStorage.removeItem('pwa-install-dismissed');
  }

  /**
   * Check if PWA features are supported
   */
  static isSupported() {
    return 'serviceWorker' in navigator && 'caches' in window;
  }

  /**
   * Get installation status
   */
  getStatus() {
    return {
      isInstalled: this.isInstalled,
      isStandalone: this.isStandalone,
      platform: this.platform,
      hasDeferred: !!this.deferredPrompt
    };
  }
}

export default PWAInstallPrompt;