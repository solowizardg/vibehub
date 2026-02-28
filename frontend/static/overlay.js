/**
 * VibeHub Visual Editing Overlay
 * Injected into sandbox preview iframe for element selection
 */
(function () {
  'use strict';

  // Brand colors
  const COLORS = {
    primary: '#2563eb',
    primaryLight: 'rgba(37, 99, 235, 0.1)',
    white: '#ffffff',
  };

  // State
  let editMode = false;
  let hoveredElement = null;
  let tooltipElement = null;
  let highlightElement = null;

  /**
   * Initialize overlay system
   */
  function init() {
    console.log('[VibeHub Overlay] Initialized');

    // Listen for messages from parent
    window.addEventListener('message', handleMessage);

    // Notify parent that overlay is ready
    if (window.parent !== window) {
      window.parent.postMessage({ type: 'overlay_ready' }, '*');
      console.log('[VibeHub Overlay] Sent overlay_ready message to parent');
    }

    // Listen for mouse events on document
    document.addEventListener('mouseover', handleMouseOver, true);
    document.addEventListener('mouseout', handleMouseOut, true);
    document.addEventListener('click', handleClick, true);
  }

  /**
   * Handle postMessage from parent window
   */
  function handleMessage(event) {
    // Security: verify origin if needed in production
    // if (event.origin !== 'expected-origin') return;

    const { type, enabled } = event.data || {};

    if (type === 'set_edit_mode') {
      setEditMode(enabled);
    }
  }

  /**
   * Toggle edit mode
   */
  function setEditMode(enabled) {
    editMode = enabled;
    console.log('[VibeHub Overlay] Edit mode:', enabled);

    if (enabled) {
      document.body.style.cursor = 'pointer';
    } else {
      document.body.style.cursor = '';
      hideTooltip();
      hideHighlight();
    }
  }

  /**
   * Handle mouse over event
   */
  function handleMouseOver(event) {
    if (!editMode) return;

    const target = findComponentElement(event.target);
    if (!target) return;

    // Avoid redundant updates
    if (hoveredElement === target) return;

    hoveredElement = target;

    const component = target.getAttribute('data-vhub-component');
    showTooltip(target, component);
    showHighlight(target);
  }

  /**
   * Handle mouse out event
   */
  function handleMouseOut(event) {
    if (!editMode) return;

    const target = findComponentElement(event.target);
    if (!target) return;

    // Check if we're moving to a child or parent of the same component
    const relatedTarget = event.relatedTarget;
    if (relatedTarget && findComponentElement(relatedTarget) === hoveredElement) {
      return;
    }

    hoveredElement = null;
    hideTooltip();
    hideHighlight();
  }

  /**
   * Handle click event on component elements
   */
  function handleClick(event) {
    if (!editMode) return;

    const target = findComponentElement(event.target);
    if (!target) return;

    // Prevent default behavior (navigation, form submission, etc.)
    event.preventDefault();
    event.stopPropagation();

    const component = target.getAttribute('data-vhub-component');
    const filePath = target.getAttribute('data-vhub-file');
    const elementId = target.getAttribute('data-vhub-id');

    console.log('[VibeHub Overlay] Element selected:', { component, filePath, elementId });

    // Send message to parent
    if (window.parent !== window) {
      window.parent.postMessage({
        type: 'element_selected',
        component,
        filePath,
        elementId,
      }, '*');
    }

    // Visual feedback
    showClickFeedback(target);
  }

  /**
   * Find closest element with data-vhub-component attribute
   */
  function findComponentElement(element) {
    let current = element;
    while (current && current !== document.body) {
      if (current.hasAttribute && current.hasAttribute('data-vhub-component')) {
        return current;
      }
      current = current.parentElement;
    }
    return null;
  }

  /**
   * Show tooltip above element
   */
  function showTooltip(element, text) {
    if (!tooltipElement) {
      tooltipElement = document.createElement('div');
      tooltipElement.id = 'vhub-tooltip';
      tooltipElement.style.cssText = `
        position: fixed;
        background: ${COLORS.primary};
        color: ${COLORS.white};
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 12px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-weight: 500;
        z-index: 2147483647;
        pointer-events: none;
        white-space: nowrap;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: opacity 0.15s ease;
      `;
      document.body.appendChild(tooltipElement);
    }

    tooltipElement.textContent = text;
    tooltipElement.style.opacity = '1';

    positionTooltip(element);
  }

  /**
   * Position tooltip above element
   */
  function positionTooltip(element) {
    if (!tooltipElement) return;

    const rect = element.getBoundingClientRect();
    const tooltipRect = tooltipElement.getBoundingClientRect();

    let top = rect.top - tooltipRect.height - 8;
    let left = rect.left;

    // Adjust if tooltip goes off screen
    if (top < 0) {
      top = rect.bottom + 8;
    }
    if (left + tooltipRect.width > window.innerWidth) {
      left = window.innerWidth - tooltipRect.width - 8;
    }

    tooltipElement.style.top = `${top}px`;
    tooltipElement.style.left = `${left}px`;
  }

  /**
   * Hide tooltip
   */
  function hideTooltip() {
    if (tooltipElement) {
      tooltipElement.style.opacity = '0';
    }
  }

  /**
   * Show highlight overlay around element
   */
  function showHighlight(element) {
    if (!highlightElement) {
      highlightElement = document.createElement('div');
      highlightElement.id = 'vhub-highlight';
      highlightElement.style.cssText = `
        position: fixed;
        border: 2px solid ${COLORS.primary};
        background: ${COLORS.primaryLight};
        border-radius: 4px;
        z-index: 2147483646;
        pointer-events: none;
        transition: all 0.15s ease;
      `;
      document.body.appendChild(highlightElement);
    }

    const rect = element.getBoundingClientRect();

    highlightElement.style.opacity = '1';
    highlightElement.style.top = `${rect.top - 2}px`;
    highlightElement.style.left = `${rect.left - 2}px`;
    highlightElement.style.width = `${rect.width + 4}px`;
    highlightElement.style.height = `${rect.height + 4}px`;
  }

  /**
   * Hide highlight
   */
  function hideHighlight() {
    if (highlightElement) {
      highlightElement.style.opacity = '0';
    }
  }

  /**
   * Show brief visual feedback on click
   */
  function showClickFeedback(element) {
    const rect = element.getBoundingClientRect();

    const feedback = document.createElement('div');
    feedback.style.cssText = `
      position: fixed;
      top: ${rect.top - 2}px;
      left: ${rect.left - 2}px;
      width: ${rect.width + 4}px;
      height: ${rect.height + 4}px;
      border: 3px solid #10b981;
      background: rgba(16, 185, 129, 0.2);
      border-radius: 4px;
      z-index: 2147483645;
      pointer-events: none;
      animation: vhub-click-feedback 0.3s ease;
    `;

    // Add keyframes if not already added
    if (!document.getElementById('vhub-animations')) {
      const style = document.createElement('style');
      style.id = 'vhub-animations';
      style.textContent = `
        @keyframes vhub-click-feedback {
          0% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.02); opacity: 0.8; }
          100% { transform: scale(1); opacity: 0; }
        }
      `;
      document.head.appendChild(style);
    }

    document.body.appendChild(feedback);

    // Remove after animation
    setTimeout(() => {
      feedback.remove();
    }, 300);
  }

  // Handle window resize - reposition tooltip and highlight
  window.addEventListener('resize', () => {
    if (editMode && hoveredElement) {
      positionTooltip(hoveredElement);
      showHighlight(hoveredElement);
    }
  });

  // Handle scroll - hide tooltip and highlight (they're positioned fixed)
  window.addEventListener('scroll', () => {
    if (editMode) {
      hideTooltip();
      hideHighlight();
      hoveredElement = null;
    }
  }, true);

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
