import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * useTouch - Advanced touch gesture detection and handling hook
 * 
 * Provides comprehensive touch event handling for swipes, taps, pinch/zoom,
 * and multi-touch gestures optimized for trading interfaces.
 * 
 * @param {HTMLElement} element - Target element for touch events
 * @param {Object} options - Configuration options
 * @returns {Object} - Touch state and event handlers
 * 
 * @example
 * const { onTouchStart, onTouchMove, onTouchEnd, swipeDirection, isDragging } = useTouch(elementRef.current, {
 *   onSwipeLeft: () => nextTab(),
 *   onSwipeRight: () => prevTab(),
 *   onTap: () => handleTap(),
 *   enablePinch: true
 * });
 */
const useTouch = (element, options = {}) => {
  const {
    // Swipe detection thresholds
    swipeThreshold = 50,           // Minimum distance for swipe
    swipeVelocityThreshold = 0.3,  // Minimum velocity for swipe
    tapTimeout = 300,              // Maximum time for tap detection
    tapThreshold = 10,             // Maximum movement for tap
    longPressTimeout = 500,        // Time for long press detection
    
    // Multi-touch settings
    enablePinch = false,
    pinchThreshold = 10,           // Minimum distance change for pinch
    
    // Callbacks
    onSwipeLeft = null,
    onSwipeRight = null,
    onSwipeUp = null,
    onSwipeDown = null,
    onTap = null,
    onDoubleTap = null,
    onLongPress = null,
    onPinch = null,
    onPinchStart = null,
    onPinchEnd = null,
    onDragStart = null,
    onDrag = null,
    onDragEnd = null,
    
    // Behavior options
    preventDefault = true,
    stopPropagation = false,
    passive = false,
    enableDrag = false,
    dragThreshold = 5
  } = options;

  // Touch state
  const [touchState, setTouchState] = useState({
    isActive: false,
    isDragging: false,
    isPinching: false,
    swipeDirection: null,
    lastTap: null,
    touchCount: 0
  });

  // Touch tracking refs
  const touchStartRef = useRef(null);
  const touchCurrentRef = useRef(null);
  const touchHistoryRef = useRef([]);
  const tapTimeoutRef = useRef(null);
  const longPressTimeoutRef = useRef(null);
  const lastTapRef = useRef(null);
  const initialDistanceRef = useRef(null);
  const isDraggingRef = useRef(false);

  // Calculate distance between two touch points
  const getDistance = useCallback((touch1, touch2) => {
    const dx = touch1.clientX - touch2.clientX;
    const dy = touch1.clientY - touch2.clientY;
    return Math.sqrt(dx * dx + dy * dy);
  }, []);

  // Calculate swipe velocity
  const getVelocity = useCallback((start, end, timeElapsed) => {
    const distance = Math.sqrt(
      Math.pow(end.clientX - start.clientX, 2) + 
      Math.pow(end.clientY - start.clientY, 2)
    );
    return distance / timeElapsed;
  }, []);

  // Determine swipe direction
  const getSwipeDirection = useCallback((start, end) => {
    const dx = end.clientX - start.clientX;
    const dy = end.clientY - start.clientY;
    const absDx = Math.abs(dx);
    const absDy = Math.abs(dy);

    // Require minimum distance
    if (Math.max(absDx, absDy) < swipeThreshold) {
      return null;
    }

    // Determine primary direction
    if (absDx > absDy) {
      return dx > 0 ? 'right' : 'left';
    } else {
      return dy > 0 ? 'down' : 'up';
    }
  }, [swipeThreshold]);

  // Handle touch start
  const handleTouchStart = useCallback((event) => {
    if (!element) return;

    if (preventDefault && !passive) {
      event.preventDefault();
    }
    if (stopPropagation) {
      event.stopPropagation();
    }

    const touch = event.touches[0];
    const timestamp = Date.now();

    touchStartRef.current = {
      clientX: touch.clientX,
      clientY: touch.clientY,
      timestamp
    };

    touchCurrentRef.current = { ...touchStartRef.current };
    touchHistoryRef.current = [touchStartRef.current];
    isDraggingRef.current = false;

    setTouchState(prev => ({
      ...prev,
      isActive: true,
      touchCount: event.touches.length,
      swipeDirection: null
    }));

    // Setup long press detection
    if (onLongPress) {
      longPressTimeoutRef.current = setTimeout(() => {
        if (touchStartRef.current) {
          onLongPress(touchStartRef.current);
        }
      }, longPressTimeout);
    }

    // Handle multi-touch for pinch
    if (enablePinch && event.touches.length === 2) {
      initialDistanceRef.current = getDistance(event.touches[0], event.touches[1]);
      setTouchState(prev => ({ ...prev, isPinching: true }));
      
      if (onPinchStart) {
        onPinchStart({
          distance: initialDistanceRef.current,
          center: {
            x: (event.touches[0].clientX + event.touches[1].clientX) / 2,
            y: (event.touches[0].clientY + event.touches[1].clientY) / 2
          }
        });
      }
    }
  }, [
    element, preventDefault, passive, stopPropagation, onLongPress, 
    longPressTimeout, enablePinch, getDistance, onPinchStart
  ]);

  // Handle touch move
  const handleTouchMove = useCallback((event) => {
    if (!element || !touchStartRef.current) return;

    if (preventDefault && !passive) {
      event.preventDefault();
    }
    if (stopPropagation) {
      event.stopPropagation();
    }

    const touch = event.touches[0];
    const timestamp = Date.now();

    touchCurrentRef.current = {
      clientX: touch.clientX,
      clientY: touch.clientY,
      timestamp
    };

    // Update touch history for velocity calculation
    touchHistoryRef.current.push(touchCurrentRef.current);
    if (touchHistoryRef.current.length > 10) {
      touchHistoryRef.current.shift();
    }

    // Check for drag start
    if (enableDrag && !isDraggingRef.current) {
      const dragDistance = Math.sqrt(
        Math.pow(touch.clientX - touchStartRef.current.clientX, 2) +
        Math.pow(touch.clientY - touchStartRef.current.clientY, 2)
      );

      if (dragDistance > dragThreshold) {
        isDraggingRef.current = true;
        setTouchState(prev => ({ ...prev, isDragging: true }));
        
        if (onDragStart) {
          onDragStart({
            startX: touchStartRef.current.clientX,
            startY: touchStartRef.current.clientY,
            currentX: touch.clientX,
            currentY: touch.clientY
          });
        }
      }
    }

    // Handle ongoing drag
    if (enableDrag && isDraggingRef.current && onDrag) {
      onDrag({
        startX: touchStartRef.current.clientX,
        startY: touchStartRef.current.clientY,
        currentX: touch.clientX,
        currentY: touch.clientY,
        deltaX: touch.clientX - touchStartRef.current.clientX,
        deltaY: touch.clientY - touchStartRef.current.clientY
      });
    }

    // Handle pinch gesture
    if (enablePinch && event.touches.length === 2 && initialDistanceRef.current) {
      const currentDistance = getDistance(event.touches[0], event.touches[1]);
      const deltaDistance = currentDistance - initialDistanceRef.current;

      if (Math.abs(deltaDistance) > pinchThreshold && onPinch) {
        onPinch({
          scale: currentDistance / initialDistanceRef.current,
          deltaDistance,
          center: {
            x: (event.touches[0].clientX + event.touches[1].clientX) / 2,
            y: (event.touches[0].clientY + event.touches[1].clientY) / 2
          }
        });
      }
    }

    // Cancel long press if moved too much
    if (longPressTimeoutRef.current) {
      const moveDistance = Math.sqrt(
        Math.pow(touch.clientX - touchStartRef.current.clientX, 2) +
        Math.pow(touch.clientY - touchStartRef.current.clientY, 2)
      );

      if (moveDistance > tapThreshold) {
        clearTimeout(longPressTimeoutRef.current);
        longPressTimeoutRef.current = null;
      }
    }
  }, [
    element, preventDefault, passive, stopPropagation, enableDrag, dragThreshold,
    onDragStart, onDrag, enablePinch, getDistance, pinchThreshold, onPinch,
    tapThreshold
  ]);

  // Handle touch end
  const handleTouchEnd = useCallback((event) => {
    if (!element || !touchStartRef.current) return;

    if (preventDefault && !passive) {
      event.preventDefault();
    }
    if (stopPropagation) {
      event.stopPropagation();
    }

    const endTime = Date.now();
    const touchDuration = endTime - touchStartRef.current.timestamp;
    const lastTouch = touchCurrentRef.current || touchStartRef.current;

    // Clear timeouts
    if (longPressTimeoutRef.current) {
      clearTimeout(longPressTimeoutRef.current);
      longPressTimeoutRef.current = null;
    }

    // Handle drag end
    if (enableDrag && isDraggingRef.current && onDragEnd) {
      onDragEnd({
        startX: touchStartRef.current.clientX,
        startY: touchStartRef.current.clientY,
        endX: lastTouch.clientX,
        endY: lastTouch.clientY,
        deltaX: lastTouch.clientX - touchStartRef.current.clientX,
        deltaY: lastTouch.clientY - touchStartRef.current.clientY,
        duration: touchDuration
      });
    }

    // Handle pinch end
    if (enablePinch && touchState.isPinching && onPinchEnd) {
      onPinchEnd({
        finalScale: initialDistanceRef.current ? 
          getDistance(event.changedTouches[0], event.changedTouches[1] || event.changedTouches[0]) / initialDistanceRef.current : 1
      });
    }

    // Detect swipe
    if (!isDraggingRef.current && touchDuration < 1000) { // Max 1 second for swipe
      const swipeDirection = getSwipeDirection(touchStartRef.current, lastTouch);
      
      if (swipeDirection) {
        // Check velocity
        const velocity = getVelocity(touchStartRef.current, lastTouch, touchDuration);
        
        if (velocity >= swipeVelocityThreshold) {
          setTouchState(prev => ({ ...prev, swipeDirection }));
          
          // Call appropriate swipe callback
          switch (swipeDirection) {
            case 'left':
              onSwipeLeft?.(touchStartRef.current, lastTouch);
              break;
            case 'right':
              onSwipeRight?.(touchStartRef.current, lastTouch);
              break;
            case 'up':
              onSwipeUp?.(touchStartRef.current, lastTouch);
              break;
            case 'down':
              onSwipeDown?.(touchStartRef.current, lastTouch);
              break;
          }
        }
      }
    }

    // Detect tap
    if (!isDraggingRef.current && touchDuration < tapTimeout) {
      const tapDistance = Math.sqrt(
        Math.pow(lastTouch.clientX - touchStartRef.current.clientX, 2) +
        Math.pow(lastTouch.clientY - touchStartRef.current.clientY, 2)
      );

      if (tapDistance < tapThreshold) {
        const currentTap = {
          x: lastTouch.clientX,
          y: lastTouch.clientY,
          timestamp: endTime
        };

        // Check for double tap
        if (onDoubleTap && lastTapRef.current) {
          const timeBetweenTaps = endTime - lastTapRef.current.timestamp;
          const distanceBetweenTaps = Math.sqrt(
            Math.pow(currentTap.x - lastTapRef.current.x, 2) +
            Math.pow(currentTap.y - lastTapRef.current.y, 2)
          );

          if (timeBetweenTaps < 500 && distanceBetweenTaps < 50) {
            onDoubleTap(currentTap);
            lastTapRef.current = null; // Prevent triple tap
            return;
          }
        }

        // Single tap (with delay to check for double tap)
        if (onTap) {
          if (onDoubleTap) {
            // Delay single tap to check for double tap
            tapTimeoutRef.current = setTimeout(() => {
              onTap(currentTap);
            }, 250);
          } else {
            // Immediate tap if no double tap handler
            onTap(currentTap);
          }
        }

        lastTapRef.current = currentTap;
      }
    }

    // Reset state
    setTouchState(prev => ({
      ...prev,
      isActive: false,
      isDragging: false,
      isPinching: false,
      touchCount: event.touches.length
    }));

    touchStartRef.current = null;
    touchCurrentRef.current = null;
    touchHistoryRef.current = [];
    isDraggingRef.current = false;
    initialDistanceRef.current = null;
  }, [
    element, preventDefault, passive, stopPropagation, enableDrag, onDragEnd,
    enablePinch, touchState.isPinching, onPinchEnd, getDistance, getSwipeDirection,
    getVelocity, swipeVelocityThreshold, onSwipeLeft, onSwipeRight, onSwipeUp, onSwipeDown,
    tapTimeout, tapThreshold, onDoubleTap, onTap
  ]);

  // Setup event listeners
  useEffect(() => {
    if (!element) return;

    const options = { passive, capture: false };

    element.addEventListener('touchstart', handleTouchStart, options);
    element.addEventListener('touchmove', handleTouchMove, options);
    element.addEventListener('touchend', handleTouchEnd, options);
    element.addEventListener('touchcancel', handleTouchEnd, options);

    return () => {
      element.removeEventListener('touchstart', handleTouchStart, options);
      element.removeEventListener('touchmove', handleTouchMove, options);
      element.removeEventListener('touchend', handleTouchEnd, options);
      element.removeEventListener('touchcancel', handleTouchEnd, options);

      // Clear any pending timeouts
      if (tapTimeoutRef.current) {
        clearTimeout(tapTimeoutRef.current);
      }
      if (longPressTimeoutRef.current) {
        clearTimeout(longPressTimeoutRef.current);
      }
    };
  }, [element, handleTouchStart, handleTouchMove, handleTouchEnd, passive]);

  return {
    // State
    ...touchState,
    
    // Event handlers (can be used directly on elements)
    onTouchStart: handleTouchStart,
    onTouchMove: handleTouchMove,
    onTouchEnd: handleTouchEnd,
    
    // Utilities
    isSupported: 'ontouchstart' in window,
    
    // Touch info
    currentTouch: touchCurrentRef.current,
    startTouch: touchStartRef.current
  };
};

export default useTouch;