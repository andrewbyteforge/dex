import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * useMobileDetection - Comprehensive mobile and device detection hook
 * 
 * Provides responsive design utilities with Bootstrap 5 breakpoints,
 * device capabilities detection, and performance-optimized resize handling.
 * 
 * @param {Object} options - Configuration options
 * @returns {Object} - Device detection state and utilities
 * 
 * @example
 * const { 
 *   isMobile, 
 *   isTablet, 
 *   isDesktop,
 *   hasTouch,
 *   orientation,
 *   screenSize 
 * } = useMobileDetection();
 */
const useMobileDetection = (options = {}) => {
  const {
    // Bootstrap 5 breakpoints (can be customized)
    breakpoints = {
      xs: 0,      // Extra small devices
      sm: 576,    // Small devices (landscape phones)
      md: 768,    // Medium devices (tablets)
      lg: 992,    // Large devices (desktops)
      xl: 1200,   // Extra large devices
      xxl: 1400   // Extra extra large devices
    },
    // Debounce resize events for performance
    debounceMs = 150,
    // Enable detailed device detection
    enableDeviceDetection = true,
    // Enable orientation detection
    enableOrientationDetection = true
  } = options;

  // Core responsive state
  const [screenSize, setScreenSize] = useState({
    width: typeof window !== 'undefined' ? window.innerWidth : 1024,
    height: typeof window !== 'undefined' ? window.innerHeight : 768
  });

  const [currentBreakpoint, setCurrentBreakpoint] = useState('lg');
  const [orientation, setOrientation] = useState('landscape');
  const [deviceInfo, setDeviceInfo] = useState({
    hasTouch: false,
    isMobile: false,
    isTablet: false,
    isDesktop: true,
    devicePixelRatio: 1,
    maxTouchPoints: 0
  });

  // Performance optimization refs
  const resizeTimeoutRef = useRef(null);
  const lastUpdateRef = useRef(0);

  // Determine current breakpoint from width
  const getBreakpoint = useCallback((width) => {
    const sortedBreakpoints = Object.entries(breakpoints)
      .sort(([, a], [, b]) => b - a); // Sort descending

    for (const [name, minWidth] of sortedBreakpoints) {
      if (width >= minWidth) {
        return name;
      }
    }
    return 'xs';
  }, [breakpoints]);

  // Detect device capabilities
  const detectDeviceCapabilities = useCallback(() => {
    if (typeof window === 'undefined') {
      return {
        hasTouch: false,
        isMobile: false,
        isTablet: false,
        isDesktop: true,
        devicePixelRatio: 1,
        maxTouchPoints: 0,
        userAgent: '',
        platform: ''
      };
    }

    const { navigator, screen } = window;
    const userAgent = navigator.userAgent || '';
    const platform = navigator.platform || '';

    // Touch detection
    const hasTouch = (
      'ontouchstart' in window ||
      navigator.maxTouchPoints > 0 ||
      navigator.msMaxTouchPoints > 0
    );

    // Device pixel ratio
    const devicePixelRatio = window.devicePixelRatio || 1;
    const maxTouchPoints = navigator.maxTouchPoints || 0;

    // User agent based detection (fallback)
    const isMobileUA = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(userAgent);
    const isTabletUA = /iPad|Android(?!.*Mobile)|Tablet/i.test(userAgent);
    const isIOSUA = /iPad|iPhone|iPod/.test(userAgent);
    const isAndroidUA = /Android/.test(userAgent);

    // Screen size based detection (primary)
    const width = screenSize.width;
    const isMobileScreen = width < breakpoints.md; // < 768px
    const isTabletScreen = width >= breakpoints.md && width < breakpoints.lg; // 768-991px
    const isDesktopScreen = width >= breakpoints.lg; // >= 992px

    // Combine detection methods
    const isMobile = isMobileScreen || (hasTouch && maxTouchPoints <= 1 && width < 900);
    const isTablet = isTabletScreen || (hasTouch && maxTouchPoints > 1 && !isMobile);
    const isDesktop = isDesktopScreen && !isMobile && !isTablet;

    return {
      hasTouch,
      isMobile,
      isTablet,
      isDesktop,
      devicePixelRatio,
      maxTouchPoints,
      userAgent,
      platform,
      isIOSUA,
      isAndroidUA,
      isMobileUA,
      isTabletUA
    };
  }, [screenSize.width, breakpoints]);

  // Update screen size and derived state
  const updateScreenInfo = useCallback(() => {
    const now = Date.now();
    
    // Throttle updates for performance
    if (now - lastUpdateRef.current < debounceMs / 2) {
      return;
    }
    lastUpdateRef.current = now;

    const newSize = {
      width: window.innerWidth,
      height: window.innerHeight
    };

    setScreenSize(newSize);
    setCurrentBreakpoint(getBreakpoint(newSize.width));

    if (enableOrientationDetection) {
      setOrientation(newSize.width > newSize.height ? 'landscape' : 'portrait');
    }

    if (enableDeviceDetection) {
      setDeviceInfo(detectDeviceCapabilities());
    }
  }, [debounceMs, getBreakpoint, enableOrientationDetection, enableDeviceDetection, detectDeviceCapabilities]);

  // Debounced resize handler
  const handleResize = useCallback(() => {
    if (resizeTimeoutRef.current) {
      clearTimeout(resizeTimeoutRef.current);
    }

    resizeTimeoutRef.current = setTimeout(() => {
      updateScreenInfo();
    }, debounceMs);
  }, [updateScreenInfo, debounceMs]);

  // Initialize and setup event listeners
  useEffect(() => {
    if (typeof window === 'undefined') return;

    // Initial detection
    updateScreenInfo();

    // Setup event listeners
    window.addEventListener('resize', handleResize, { passive: true });
    
    if (enableOrientationDetection && 'orientationchange' in window) {
      window.addEventListener('orientationchange', handleResize, { passive: true });
    }

    return () => {
      window.removeEventListener('resize', handleResize);
      
      if (enableOrientationDetection && 'orientationchange' in window) {
        window.removeEventListener('orientationchange', handleResize);
      }
      
      if (resizeTimeoutRef.current) {
        clearTimeout(resizeTimeoutRef.current);
      }
    };
  }, [handleResize, updateScreenInfo, enableOrientationDetection]);

  // Utility functions
  const isBreakpoint = useCallback((breakpoint) => {
    return currentBreakpoint === breakpoint;
  }, [currentBreakpoint]);

  const isBreakpointUp = useCallback((breakpoint) => {
    const currentWidth = screenSize.width;
    return currentWidth >= breakpoints[breakpoint];
  }, [screenSize.width, breakpoints]);

  const isBreakpointDown = useCallback((breakpoint) => {
    const currentWidth = screenSize.width;
    return currentWidth < breakpoints[breakpoint];
  }, [screenSize.width, breakpoints]);

  const isBreakpointBetween = useCallback((min, max) => {
    const currentWidth = screenSize.width;
    return currentWidth >= breakpoints[min] && currentWidth < breakpoints[max];
  }, [screenSize.width, breakpoints]);

  // Get responsive value based on current breakpoint
  const getResponsiveValue = useCallback((values) => {
    // values can be: { xs: 1, sm: 2, md: 3, lg: 4, xl: 5, xxl: 6 }
    // or array: [xs, sm, md, lg, xl, xxl]
    
    if (Array.isArray(values)) {
      const breakpointNames = ['xs', 'sm', 'md', 'lg', 'xl', 'xxl'];
      const valueMap = {};
      breakpointNames.forEach((name, index) => {
        if (values[index] !== undefined) {
          valueMap[name] = values[index];
        }
      });
      values = valueMap;
    }

    // Find the appropriate value for current breakpoint
    const breakpointOrder = ['xxl', 'xl', 'lg', 'md', 'sm', 'xs'];
    const currentIndex = breakpointOrder.indexOf(currentBreakpoint);
    
    // Look for value at current breakpoint or fall back to smaller ones
    for (let i = currentIndex; i < breakpointOrder.length; i++) {
      const breakpointName = breakpointOrder[i];
      if (values[breakpointName] !== undefined) {
        return values[breakpointName];
      }
    }
    
    // Fallback to first available value
    return Object.values(values)[0];
  }, [currentBreakpoint]);

  // CSS media query generator
  const getMediaQuery = useCallback((breakpoint, direction = 'up') => {
    const width = breakpoints[breakpoint];
    
    if (direction === 'up') {
      return `(min-width: ${width}px)`;
    } else if (direction === 'down') {
      return `(max-width: ${width - 1}px)`;
    }
    
    return `(min-width: ${width}px)`;
  }, [breakpoints]);

  return {
    // Core responsive state
    screenSize,
    currentBreakpoint,
    orientation,
    
    // Device detection
    ...deviceInfo,
    
    // Convenience flags
    isMobile: deviceInfo.isMobile,
    isTablet: deviceInfo.isTablet,
    isDesktop: deviceInfo.isDesktop,
    hasTouch: deviceInfo.hasTouch,
    
    // Breakpoint utilities
    isBreakpoint,
    isBreakpointUp,
    isBreakpointDown,
    isBreakpointBetween,
    
    // Responsive utilities
    getResponsiveValue,
    getMediaQuery,
    
    // Bootstrap 5 compatible flags
    isXs: currentBreakpoint === 'xs',
    isSm: currentBreakpoint === 'sm',
    isMd: currentBreakpoint === 'md',
    isLg: currentBreakpoint === 'lg',
    isXl: currentBreakpoint === 'xl',
    isXxl: currentBreakpoint === 'xxl',
    
    // Size comparisons
    isSmallScreen: deviceInfo.isMobile,
    isMediumScreen: deviceInfo.isTablet,
    isLargeScreen: deviceInfo.isDesktop,
    
    // Orientation flags
    isPortrait: orientation === 'portrait',
    isLandscape: orientation === 'landscape',
    
    // Configuration
    breakpoints
  };
};

export default useMobileDetection;