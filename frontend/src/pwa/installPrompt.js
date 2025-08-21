/**
 * PWA Installation Prompt Handler
 * 
 * Manages the installation prompt for Progressive Web App functionality,
 * providing a seamless installation experience for DEX Sniper Pro.
 * 
 * Features:
 * - Smart prompt timing based on user engagement
 * - Cross-platform installation support
 * - Installation analytics and tracking
 * - Customizable installation UI
 */

class PWAInstallManager {
  constructor(options = {}) {
    this.options = {
      // Timing configuration
      minSessionTime: 30000,        // 30 seconds minimum before showing prompt
      minPageViews: 3,              // Minimum page interactions
      maxPromptAttempts: 3,         // Maximum times to show prompt
      promptCooldown: 86400000,     // 24 hours between prompts
      
      // User engagement thresholds
      minTradeAttempts: 1,          // User tried to trade at least once
      minTimeSpent: 120000,         // 2 minutes total time spent
      
      // UI configuration
      showInlinePrompt: true,       // Show custom installation banner
      showToast: true,              // Show toast notifications
      customButtonSelector: null,   // Custom install button selector
      
      // Analytics
      enableAnalytics: true,
      analyticsCallback: null,
      
      // Callbacks
      onInstallPromptShow: null,
      onInstallSuccess: null,
      onInstallError: null,
      onInstallDismiss: null,
      
      ...options
    };

    // State management
    this.state = {
      deferredPrompt: null,
      isInstallable: false,
      isInstalled: false,
      promptShown: false,
      userEngagement: {
        sessionStart: Date.now(),
        pageViews: 0,
        tradeAttempts: 0,
        timeSpent: 0,
        lastActivity: Date.now()
      }
    };

    // Storage keys
    this.storageKeys = {
      promptAttempts: 'pwa_prompt_attempts',
      lastPromptTime: 'pwa_last_prompt',
      installDeclined: 'pwa_install_declined',
      userEngagement: 'pwa_user_engagement'
    };

    this.init();
  }

  /**
   * Initialize the PWA install manager
   */
  init() {
    this.loadStoredData();
    this.setupEventListeners();
    this.trackUserEngagement();
    
    // Check if already installed
    this.checkInstallationStatus();
    
    console.log('[PWA Install] Manager initialized');
  }

  /**
   * Load stored user data and preferences
   */
  loadStoredData() {
    try {
      const storedEngagement = localStorage.getItem(this.storageKeys.userEngagement);
      if (storedEngagement) {
        const parsed = JSON.parse(storedEngagement);
        this.state.userEngagement = {
          ...this.state.userEngagement,
          ...parsed,
          sessionStart: Date.now() // Reset session start
        };
      }
    } catch (error) {
      console.warn('[PWA Install] Failed to load stored data:', error);
    }
  }

  /**
   * Save user engagement data
   */
  saveEngagementData() {
    try {
      localStorage.setItem(
        this.storageKeys.userEngagement,
        JSON.stringify({
          ...this.state.userEngagement,
          timeSpent: this.getTotalTimeSpent()
        })
      );
    } catch (error) {
      console.warn('[PWA Install] Failed to save engagement data:', error);
    }
  }

  /**
   * Setup event listeners for PWA events
   */
  setupEventListeners() {
    // Listen for beforeinstallprompt event
    window.addEventListener('beforeinstallprompt', (event) => {
      console.log('[PWA Install] Install prompt available');
      
      // Prevent the mini-infobar from appearing
      event.preventDefault();
      
      // Store the event for later use
      this.state.deferredPrompt = event;
      this.state.isInstallable = true;
      
      // Check if we should show the prompt
      this.evaluateInstallPrompt();
    });

    // Listen for app installation
    window.addEventListener('appinstalled', (event) => {
      console.log('[PWA Install] App installed successfully');
      
      this.state.isInstalled = true;
      this.state.deferredPrompt = null;
      
      // Clear stored prompt data
      this.clearPromptData();
      
      // Analytics tracking
      this.trackEvent('pwa_installed', {
        method: 'browser_prompt',
        engagement_score: this.calculateEngagementScore()
      });
      
      // Callback
      if (this.options.onInstallSuccess) {
        this.options.onInstallSuccess(event);
      }
    });

    // Track page visibility changes
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.state.userEngagement.lastActivity = Date.now();
        this.saveEngagementData();
      } else {
        this.state.userEngagement.sessionStart = Date.now();
      }
    });

    // Track page navigation
    window.addEventListener('popstate', () => {
      this.trackPageView();
    });

    // Custom install button handling
    if (this.options.customButtonSelector) {
      const customButton = document.querySelector(this.options.customButtonSelector);
      if (customButton) {
        customButton.addEventListener('click', () => {
          this.showInstallPrompt();
        });
      }
    }
  }

  /**
   * Track user engagement metrics
   */
  trackUserEngagement() {
    // Track page views
    this.trackPageView();
    
    // Track trade attempts (would integrate with trading components)
    this.setupTradeTracking();
    
    // Periodic engagement updates
    this.engagementInterval = setInterval(() => {
      this.updateEngagement();
    }, 10000); // Update every 10 seconds
  }

  /**
   * Track page view
   */
  trackPageView() {
    this.state.userEngagement.pageViews++;
    this.state.userEngagement.lastActivity = Date.now();
    
    console.log('[PWA Install] Page view tracked:', this.state.userEngagement.pageViews);
  }

  /**
   * Track trade attempts (integration point for trading components)
   */
  setupTradeTracking() {
    // This would integrate with your trading components
    // For now, we'll listen for custom events
    
    window.addEventListener('trade_attempt', () => {
      this.state.userEngagement.tradeAttempts++;
      console.log('[PWA Install] Trade attempt tracked:', this.state.userEngagement.tradeAttempts);
    });
    
    window.addEventListener('quote_request', () => {
      this.state.userEngagement.lastActivity = Date.now();
    });
  }

  /**
   * Update engagement metrics
   */
  updateEngagement() {
    if (!document.hidden) {
      this.state.userEngagement.timeSpent = this.getTotalTimeSpent();
      this.state.userEngagement.lastActivity = Date.now();
    }
  }

  /**
   * Get total time spent in the app
   */
  getTotalTimeSpent() {
    const sessionTime = Date.now() - this.state.userEngagement.sessionStart;
    return this.state.userEngagement.timeSpent + sessionTime;
  }

  /**
   * Calculate user engagement score
   */
  calculateEngagementScore() {
    const {
      pageViews,
      tradeAttempts,
      timeSpent
    } = this.state.userEngagement;
    
    // Weighted scoring system
    const score = (
      (pageViews * 10) +
      (tradeAttempts * 50) +
      (timeSpent / 1000) // Convert ms to seconds
    );
    
    return Math.min(score, 1000); // Cap at 1000
  }

  /**
   * Check if already installed
   */
  checkInstallationStatus() {
    // Check if running in standalone mode
    if (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) {
      this.state.isInstalled = true;
      console.log('[PWA Install] App is running in standalone mode');
      return;
    }
    
    // Check for iOS installation
    if (window.navigator && window.navigator.standalone) {
      this.state.isInstalled = true;
      console.log('[PWA Install] App is installed on iOS');
      return;
    }
    
    // Check for Android installation indicators
    if (document.referrer.includes('android-app://')) {
      this.state.isInstalled = true;
      console.log('[PWA Install] App is installed on Android');
      return;
    }
  }

  /**
   * Evaluate whether to show install prompt
   */
  evaluateInstallPrompt() {
    if (!this.state.isInstallable || this.state.isInstalled || this.state.promptShown) {
      return false;
    }

    // Check if user has declined too many times
    const promptAttempts = this.getPromptAttempts();
    if (promptAttempts >= this.options.maxPromptAttempts) {
      console.log('[PWA Install] Max prompt attempts reached');
      return false;
    }

    // Check cooldown period
    const lastPromptTime = this.getLastPromptTime();
    if (lastPromptTime && (Date.now() - lastPromptTime) < this.options.promptCooldown) {
      console.log('[PWA Install] Still in cooldown period');
      return false;
    }

    // Check user engagement
    if (!this.meetsEngagementCriteria()) {
      console.log('[PWA Install] Engagement criteria not met');
      return false;
    }

    // Show the prompt
    this.schedulePromptDisplay();
    return true;
  }

  /**
   * Check if user meets engagement criteria
   */
  meetsEngagementCriteria() {
    const {
      pageViews,
      tradeAttempts,
      timeSpent
    } = this.state.userEngagement;
    
    const sessionTime = Date.now() - this.state.userEngagement.sessionStart;
    
    return (
      sessionTime >= this.options.minSessionTime &&
      pageViews >= this.options.minPageViews &&
      (tradeAttempts >= this.options.minTradeAttempts || timeSpent >= this.options.minTimeSpent)
    );
  }

  /**
   * Schedule prompt display with delay
   */
  schedulePromptDisplay() {
    setTimeout(() => {
      if (this.options.showInlinePrompt) {
        this.showInlinePrompt();
      }
      
      if (this.options.showToast) {
        this.showToastPrompt();
      }
    }, 2000); // 2 second delay for better UX
  }

  /**
   * Show inline installation prompt
   */
  showInlinePrompt() {
    const promptContainer = this.createPromptElement();
    
    // Insert at top of page
    const body = document.body;
    if (body.firstChild) {
      body.insertBefore(promptContainer, body.firstChild);
    } else {
      body.appendChild(promptContainer);
    }
    
    // Auto-hide after 10 seconds
    setTimeout(() => {
      if (promptContainer.parentNode) {
        promptContainer.remove();
      }
    }, 10000);
    
    this.trackEvent('pwa_prompt_shown', { type: 'inline' });
  }

  /**
   * Create prompt UI element
   */
  createPromptElement() {
    const container = document.createElement('div');
    container.className = 'pwa-install-prompt';
    container.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      background: linear-gradient(135deg, #0d6efd, #6610f2);
      color: white;
      padding: 12px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      z-index: 9999;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    `;
    
    const message = document.createElement('div');
    message.style.cssText = 'flex: 1; margin-right: 16px;';
    message.innerHTML = `
      <strong>📱 Install DEX Sniper Pro</strong><br>
      <small>Get instant access and offline functionality</small>
    `;
    
    const actions = document.createElement('div');
    actions.style.cssText = 'display: flex; gap: 8px; align-items: center;';
    
    const installButton = document.createElement('button');
    installButton.textContent = 'Install';
    installButton.style.cssText = `
      background: white;
      color: #0d6efd;
      border: none;
      padding: 8px 16px;
      border-radius: 4px;
      font-weight: 600;
      cursor: pointer;
      font-size: 14px;
    `;
    
    const dismissButton = document.createElement('button');
    dismissButton.textContent = '✕';
    dismissButton.style.cssText = `
      background: transparent;
      color: white;
      border: 1px solid rgba(255,255,255,0.3);
      padding: 8px 12px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
    `;
    
    // Event handlers
    installButton.addEventListener('click', () => {
      this.showInstallPrompt();
      container.remove();
    });
    
    dismissButton.addEventListener('click', () => {
      this.dismissPrompt();
      container.remove();
    });
    
    actions.appendChild(installButton);
    actions.appendChild(dismissButton);
    container.appendChild(message);
    container.appendChild(actions);
    
    return container;
  }

  /**
   * Show toast notification prompt
   */
  showToastPrompt() {
    // This would integrate with your notification system
    console.log('[PWA Install] Toast prompt would be shown here');
  }

  /**
   * Show the browser's native install prompt
   */
  async showInstallPrompt() {
    if (!this.state.deferredPrompt) {
      console.warn('[PWA Install] No deferred prompt available');
      return false;
    }

    try {
      // Show the prompt
      this.state.deferredPrompt.prompt();
      
      // Wait for the user's response
      const choiceResult = await this.state.deferredPrompt.userChoice;
      
      console.log('[PWA Install] User choice:', choiceResult.outcome);
      
      if (choiceResult.outcome === 'accepted') {
        this.trackEvent('pwa_prompt_accepted');
        if (this.options.onInstallSuccess) {
          this.options.onInstallSuccess();
        }
      } else {
        this.trackEvent('pwa_prompt_dismissed');
        this.handlePromptDismissal();
      }
      
      // Clear the deferred prompt
      this.state.deferredPrompt = null;
      this.state.promptShown = true;
      
      return choiceResult.outcome === 'accepted';
    } catch (error) {
      console.error('[PWA Install] Error showing prompt:', error);
      this.trackEvent('pwa_prompt_error', { error: error.message });
      
      if (this.options.onInstallError) {
        this.options.onInstallError(error);
      }
      
      return false;
    }
  }

  /**
   * Handle prompt dismissal
   */
  dismissPrompt() {
    this.handlePromptDismissal();
    this.trackEvent('pwa_prompt_dismissed', { method: 'manual' });
    
    if (this.options.onInstallDismiss) {
      this.options.onInstallDismiss();
    }
  }

  /**
   * Handle prompt dismissal logic
   */
  handlePromptDismissal() {
    // Increment prompt attempts
    const attempts = this.getPromptAttempts() + 1;
    localStorage.setItem(this.storageKeys.promptAttempts, attempts.toString());
    
    // Set last prompt time
    localStorage.setItem(this.storageKeys.lastPromptTime, Date.now().toString());
    
    this.state.promptShown = true;
  }

  /**
   * Get number of prompt attempts
   */
  getPromptAttempts() {
    try {
      return parseInt(localStorage.getItem(this.storageKeys.promptAttempts) || '0', 10);
    } catch {
      return 0;
    }
  }

  /**
   * Get last prompt time
   */
  getLastPromptTime() {
    try {
      const time = localStorage.getItem(this.storageKeys.lastPromptTime);
      return time ? parseInt(time, 10) : null;
    } catch {
      return null;
    }
  }

  /**
   * Clear prompt-related data
   */
  clearPromptData() {
    Object.values(this.storageKeys).forEach(key => {
      try {
        localStorage.removeItem(key);
      } catch (error) {
        console.warn('[PWA Install] Failed to clear storage key:', key);
      }
    });
  }

  /**
   * Track analytics events
   */
  trackEvent(eventName, properties = {}) {
    if (!this.options.enableAnalytics) return;
    
    const eventData = {
      event: eventName,
      timestamp: Date.now(),
      engagement_score: this.calculateEngagementScore(),
      ...properties
    };
    
    console.log('[PWA Install] Analytics:', eventData);
    
    if (this.options.analyticsCallback) {
      this.options.analyticsCallback(eventData);
    }
  }

  /**
   * Manual trigger for installation prompt
   */
  triggerInstallPrompt() {
    if (this.state.isInstallable && !this.state.isInstalled) {
      return this.showInstallPrompt();
    }
    return false;
  }

  /**
   * Check if installation is available
   */
  isInstallAvailable() {
    return this.state.isInstallable && !this.state.isInstalled;
  }

  /**
   * Get current state
   */
  getState() {
    return {
      ...this.state,
      engagementScore: this.calculateEngagementScore(),
      promptAttempts: this.getPromptAttempts()
    };
  }

  /**
   * Cleanup
   */
  destroy() {
    if (this.engagementInterval) {
      clearInterval(this.engagementInterval);
    }
    
    this.saveEngagementData();
    console.log('[PWA Install] Manager destroyed');
  }
}

// Export for use in React components
export default PWAInstallManager;

// Helper hook for React integration
export function usePWAInstall(options = {}) {
  const [manager, setManager] = React.useState(null);
  const [installState, setInstallState] = React.useState({
    isInstallable: false,
    isInstalled: false,
    promptShown: false
  });

  React.useEffect(() => {
    const pwaManager = new PWAInstallManager({
      ...options,
      onInstallPromptShow: () => {
        setInstallState(prev => ({ ...prev, promptShown: true }));
        options.onInstallPromptShow?.();
      },
      onInstallSuccess: () => {
        setInstallState(prev => ({ ...prev, isInstalled: true }));
        options.onInstallSuccess?.();
      }
    });

    setManager(pwaManager);

    // Update state periodically
    const stateInterval = setInterval(() => {
      const state = pwaManager.getState();
      setInstallState({
        isInstallable: state.isInstallable,
        isInstalled: state.isInstalled,
        promptShown: state.promptShown
      });
    }, 1000);

    return () => {
      clearInterval(stateInterval);
      pwaManager.destroy();
    };
  }, []);

  return {
    ...installState,
    triggerInstall: () => manager?.triggerInstallPrompt(),
    isInstallAvailable: () => manager?.isInstallAvailable(),
    getEngagementScore: () => manager?.calculateEngagementScore()
  };
}