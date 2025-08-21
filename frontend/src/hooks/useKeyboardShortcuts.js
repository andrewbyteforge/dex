import { useEffect, useRef, useCallback } from 'react';

/**
 * useKeyboardShortcuts - Custom hook for power user keyboard navigation
 * 
 * Provides keyboard shortcuts for quick navigation and actions.
 * Automatically disables shortcuts when user is typing in inputs.
 * 
 * @param {Object} shortcuts - Object mapping key combinations to callback functions
 * @param {Object} options - Configuration options
 * @returns {Object} - Hook utilities and state
 * 
 * @example
 * const { registerShortcut, isShortcutsEnabled } = useKeyboardShortcuts({
 *   't': () => setActiveTab('trade'),
 *   'a': () => setActiveTab('autotrade'),
 *   'ctrl+k': () => openCommandPalette(),
 *   'escape': () => closeAllModals()
 * });
 */
const useKeyboardShortcuts = (shortcuts = {}, options = {}) => {
  const {
    enabled = true,
    preventDefault = true,
    disableInInputs = true,
    caseSensitive = false,
    showTooltips = true
  } = options;

  const shortcutsRef = useRef(shortcuts);
  const isEnabledRef = useRef(enabled);
  const activeShortcuts = useRef(new Map());

  // Update refs when props change
  useEffect(() => {
    shortcutsRef.current = shortcuts;
    isEnabledRef.current = enabled;
  }, [shortcuts, enabled]);

  // Check if user is currently typing in an input field
  const isTypingInInput = useCallback(() => {
    if (!disableInInputs) return false;
    
    const activeElement = document.activeElement;
    const inputTypes = ['input', 'textarea', 'select'];
    const isContentEditable = activeElement?.contentEditable === 'true';
    const isInputField = inputTypes.includes(activeElement?.tagName?.toLowerCase());
    
    return isInputField || isContentEditable;
  }, [disableInInputs]);

  // Convert key event to string representation
  const getKeyString = useCallback((event) => {
    const parts = [];
    
    if (event.ctrlKey || event.metaKey) parts.push('ctrl');
    if (event.altKey) parts.push('alt');
    if (event.shiftKey) parts.push('shift');
    
    const key = caseSensitive ? event.key : event.key.toLowerCase();
    
    // Handle special keys
    const specialKeys = {
      ' ': 'space',
      'ArrowUp': 'up',
      'ArrowDown': 'down',
      'ArrowLeft': 'left',
      'ArrowRight': 'right',
      'Enter': 'enter',
      'Escape': 'escape',
      'Tab': 'tab',
      'Backspace': 'backspace',
      'Delete': 'delete'
    };
    
    const finalKey = specialKeys[key] || key;
    parts.push(finalKey);
    
    return parts.join('+');
  }, [caseSensitive]);

  // Handle keydown events
  const handleKeyDown = useCallback((event) => {
    if (!isEnabledRef.current || isTypingInInput()) {
      return;
    }

    const keyString = getKeyString(event);
    const shortcut = shortcutsRef.current[keyString];

    if (shortcut && typeof shortcut === 'function') {
      if (preventDefault) {
        event.preventDefault();
        event.stopPropagation();
      }
      
      try {
        shortcut(event);
        
        // Track usage for analytics
        activeShortcuts.current.set(keyString, {
          lastUsed: Date.now(),
          count: (activeShortcuts.current.get(keyString)?.count || 0) + 1
        });
      } catch (error) {
        console.error(`[useKeyboardShortcuts] Error executing shortcut "${keyString}":`, error);
      }
    }
  }, [getKeyString, preventDefault, isTypingInInput]);

  // Register keyboard event listeners
  useEffect(() => {
    if (!enabled) return;

    document.addEventListener('keydown', handleKeyDown, true);
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown, true);
    };
  }, [enabled, handleKeyDown]);

  // Register a new shortcut dynamically
  const registerShortcut = useCallback((keyString, callback) => {
    shortcutsRef.current = {
      ...shortcutsRef.current,
      [keyString]: callback
    };
  }, []);

  // Unregister a shortcut
  const unregisterShortcut = useCallback((keyString) => {
    const newShortcuts = { ...shortcutsRef.current };
    delete newShortcuts[keyString];
    shortcutsRef.current = newShortcuts;
  }, []);

  // Get formatted shortcut display string
  const getShortcutDisplay = useCallback((keyString) => {
    return keyString
      .split('+')
      .map(part => {
        const displayMap = {
          'ctrl': '⌘', // or 'Ctrl' on Windows
          'alt': '⌥',  // or 'Alt' on Windows
          'shift': '⇧',
          'space': 'Space',
          'enter': 'Enter',
          'escape': 'Esc',
          'up': '↑',
          'down': '↓',
          'left': '←',
          'right': '→'
        };
        return displayMap[part] || part.toUpperCase();
      })
      .join('+');
  }, []);

  // Get all registered shortcuts with usage stats
  const getShortcutStats = useCallback(() => {
    const shortcuts = Object.keys(shortcutsRef.current);
    return shortcuts.map(key => ({
      key,
      display: getShortcutDisplay(key),
      usage: activeShortcuts.current.get(key) || { count: 0, lastUsed: null }
    }));
  }, [getShortcutDisplay]);

  // Generate tooltip content for components
  const getTooltipText = useCallback((keyString, description = '') => {
    if (!showTooltips) return description;
    
    const display = getShortcutDisplay(keyString);
    return description ? `${description} (${display})` : display;
  }, [getShortcutDisplay, showTooltips]);

  return {
    // State
    isShortcutsEnabled: enabled && !isTypingInInput(),
    
    // Methods
    registerShortcut,
    unregisterShortcut,
    getShortcutDisplay,
    getShortcutStats,
    getTooltipText,
    
    // Utilities
    isTypingInInput
  };
};

// Predefined shortcut sets for common use cases
export const TRADING_SHORTCUTS = {
  't': 'Switch to Trade tab',
  'a': 'Switch to Autotrade tab', 
  's': 'Switch to Stats/Analytics tab',
  'o': 'Switch to Orders tab',
  'ctrl+k': 'Open command palette',
  'ctrl+,': 'Open settings',
  'escape': 'Close modals/cancel',
  'ctrl+r': 'Refresh quotes',
  'ctrl+enter': 'Execute trade',
  'space': 'Pause/resume autotrade'
};

export const NAVIGATION_SHORTCUTS = {
  'h': 'Go to home/trade',
  'j': 'Next item',
  'k': 'Previous item',
  'g g': 'Go to top',
  'g e': 'Go to end',
  '/': 'Search/filter',
  '?': 'Show help'
};

export default useKeyboardShortcuts;