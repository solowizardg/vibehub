/**
 * VibeHub Overlay Script
 * Injected into sandbox preview pages to enable visual element selection
 */

(function () {
  'use strict';

  // Only run in iframe context (has parent)
  if (window.self === window.top) {
    return;
  }

  // Check if overlay is already initialized
  if (window.__VIBEHUB_OVERLAY__) {
    return;
  }
  window.__VIBEHUB_OVERLAY__ = true;

  // State
  let isActive = true;
  let hoveredElement = null;
  let selectedElement = null;

  // Create highlight overlay element
  const highlightBox = document.createElement('div');
  highlightBox.id = '__vibehub-highlight__';
  highlightBox.style.cssText = `
    position: fixed;
    pointer-events: none;
    z-index: 2147483647;
    border: 2px solid #3b82f6;
    border-radius: 4px;
    background: rgba(59, 130, 246, 0.1);
    box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.2);
    transition: all 0.1s ease-out;
    display: none;
  `;

  // Create label for highlight
  const highlightLabel = document.createElement('div');
  highlightLabel.style.cssText = `
    position: absolute;
    top: -24px;
    left: 0;
    background: #3b82f6;
    color: white;
    font-size: 11px;
    font-family: monospace;
    padding: 2px 8px;
    border-radius: 4px 4px 0 0;
    white-space: nowrap;
    pointer-events: none;
  `;
  highlightBox.appendChild(highlightLabel);

  document.body.appendChild(highlightBox);

  // Utility: Get element info
  function getElementInfo(element) {
    const vhubId = element.getAttribute('data-vhub-id');
    const vhubFile = element.getAttribute('data-vhub-file');

    if (!vhubId || !vhubFile) {
      return null;
    }

    return {
      vhubId,
      vhubFile,
      tagName: element.tagName.toLowerCase(),
      innerText: element.innerText?.slice(0, 100) || '',
      className: element.className || '',
    };
  }

  // Update highlight position
  function updateHighlight(element, isSelected = false) {
    if (!element) {
      highlightBox.style.display = 'none';
      return;
    }

    const rect = element.getBoundingClientRect();
    const scrollX = window.scrollX || window.pageXOffset;
    const scrollY = window.scrollY || window.pageYOffset;

    highlightBox.style.left = `${rect.left + scrollX}px`;
    highlightBox.style.top = `${rect.top + scrollY}px`;
    highlightBox.style.width = `${rect.width}px`;
    highlightBox.style.height = `${rect.height}px`;

    const info = getElementInfo(element);
    if (info) {
      highlightLabel.textContent = `${info.vhubId} (${info.tagName})`;
    } else {
      highlightLabel.textContent = element.tagName.toLowerCase();
    }

    if (isSelected) {
      highlightBox.style.borderColor = '#10b981';
      highlightBox.style.background = 'rgba(16, 185, 129, 0.1)';
      highlightBox.style.boxShadow = '0 0 0 4px rgba(16, 185, 129, 0.2)';
      highlightLabel.style.background = '#10b981';
    } else {
      highlightBox.style.borderColor = '#3b82f6';
      highlightBox.style.background = 'rgba(59, 130, 246, 0.1)';
      highlightBox.style.boxShadow = '0 0 0 4px rgba(59, 130, 246, 0.2)';
      highlightLabel.style.background = '#3b82f6';
    }

    highlightBox.style.display = 'block';
  }

  // Find closest element with data-vhub-id
  function findTrackableElement(element) {
    let current = element;
    while (current && current !== document.body) {
      if (current.hasAttribute && current.hasAttribute('data-vhub-id')) {
        return current;
      }
      current = current.parentElement;
    }
    return null;
  }

  // Mouse move handler
  function handleMouseMove(e) {
    if (!isActive) return;

    const target = findTrackableElement(e.target);
    if (target !== hoveredElement) {
      hoveredElement = target;
      if (hoveredElement && hoveredElement !== selectedElement) {
        updateHighlight(hoveredElement, false);
      } else if (!hoveredElement && !selectedElement) {
        highlightBox.style.display = 'none';
      }
    }
  }

  // Click handler
  function handleClick(e) {
    if (!isActive) return;

    const target = findTrackableElement(e.target);
    if (!target) return;

    e.preventDefault();
    e.stopPropagation();

    selectedElement = target;
    updateHighlight(selectedElement, true);

    const info = getElementInfo(selectedElement);
    if (info) {
      // Send message to parent window
      window.parent.postMessage({
        type: 'VIBEHUB_ELEMENT_SELECTED',
        element: info,
      }, '*');
    }
  }

  // Listen for messages from parent
  function handleMessage(e) {
    const { data } = e;

    if (!data || typeof data !== 'object') return;

    switch (data.type) {
      case 'VIBEHUB_OVERLAY_ACTIVATE':
        isActive = true;
        break;

      case 'VIBEHUB_OVERLAY_DEACTIVATE':
        isActive = false;
        highlightBox.style.display = 'none';
        break;

      case 'VIBEHUB_CLEAR_SELECTION':
        selectedElement = null;
        highlightBox.style.display = 'none';
        break;

      case 'VIBEHUB_PING':
        window.parent.postMessage({ type: 'VIBEHUB_PONG' }, '*');
        break;
    }
  }

  // Add event listeners
  document.addEventListener('mousemove', handleMouseMove, { capture: true });
  document.addEventListener('click', handleClick, { capture: true });
  window.addEventListener('message', handleMessage);

  // Handle scroll updates
  window.addEventListener('scroll', () => {
    if (selectedElement) {
      updateHighlight(selectedElement, true);
    } else if (hoveredElement) {
      updateHighlight(hoveredElement, false);
    }
  }, { passive: true });

  // Notify parent that overlay is ready
  window.parent.postMessage({ type: 'VIBEHUB_OVERLAY_READY' }, '*');

  console.log('[VibeHub] Overlay script initialized');
})();
