/**
 * VibeHub Visual Editor Overlay
 * Injected into sandbox preview to enable click-to-select components
 */
(function() {
  'use strict';

  // Prevent double injection
  if (window.__VIBEHUB_OVERLAY__) return;
  window.__VIBEHUB_OVERLAY__ = true;

  let selectedElement = null;
  let highlightBox = null;
  let isEnabled = true;

  // Create highlight box
  function createHighlightBox() {
    const box = document.createElement('div');
    box.id = '__vibehub_highlight__';
    box.style.cssText = `
      position: fixed;
      pointer-events: none;
      z-index: 999999;
      border: 2px solid #3b82f6;
      border-radius: 4px;
      background: rgba(59, 130, 246, 0.1);
      box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.2);
      transition: all 0.15s ease;
      display: none;
    `;

    // Add label
    const label = document.createElement('div');
    label.id = '__vibehub_label__';
    label.style.cssText = `
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
    box.appendChild(label);

    document.body.appendChild(box);
    return box;
  }

  // Update highlight position
  function updateHighlight(el) {
    if (!highlightBox) highlightBox = createHighlightBox();
    if (!el) {
      highlightBox.style.display = 'none';
      return;
    }

    const rect = el.getBoundingClientRect();
    highlightBox.style.display = 'block';
    highlightBox.style.top = rect.top + 'px';
    highlightBox.style.left = rect.left + 'px';
    highlightBox.style.width = rect.width + 'px';
    highlightBox.style.height = rect.height + 'px';

    // Update label
    const label = highlightBox.querySelector('#__vibehub_label__');
    if (label) {
      const componentName = el.getAttribute('data-vibehub-component') || el.tagName.toLowerCase();
      const filePath = el.getAttribute('data-vibehub-file') || 'unknown';
      label.textContent = `${componentName} (${filePath})`;
    }
  }

  // Get element info for selection
  function getElementInfo(el) {
    return {
      tagName: el.tagName,
      component: el.getAttribute('data-vibehub-component') || null,
      filePath: el.getAttribute('data-vibehub-file') || null,
      className: el.className,
      id: el.id,
      textContent: el.textContent?.slice(0, 200) || null,
    };
  }

  // Handle mouse over
  function handleMouseOver(e) {
    if (!isEnabled) return;
    const target = e.target;
    if (target.id?.startsWith('__vibehub')) return;
    updateHighlight(target);
  }

  // Handle click
  function handleClick(e) {
    if (!isEnabled) return;
    const target = e.target;
    if (target.id?.startsWith('__vibehub')) return;

    e.preventDefault();
    e.stopPropagation();

    selectedElement = target;
    updateHighlight(target);

    // Send message to parent
    if (window.parent !== window) {
      window.parent.postMessage({
        type: 'VIBEHUB_ELEMENT_SELECTED',
        element: getElementInfo(target),
      }, '*');
    }
  }

  // Handle scroll (hide highlight during scroll)
  let scrollTimeout;
  function handleScroll() {
    if (!highlightBox) return;
    highlightBox.style.display = 'none';
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(() => {
      if (selectedElement) {
        updateHighlight(selectedElement);
      }
    }, 100);
  }

  // Listen for messages from parent
  window.addEventListener('message', (e) => {
    if (e.data?.type === 'VIBEHUB_ENABLE_SELECTION') {
      isEnabled = true;
    } else if (e.data?.type === 'VIBEHUB_DISABLE_SELECTION') {
      isEnabled = false;
      if (highlightBox) highlightBox.style.display = 'none';
    } else if (e.data?.type === 'VIBEHUB_HIGHLIGHT_ELEMENT') {
      const { filePath, componentName } = e.data;
      // Find element by data attributes
      const selector = `[data-vibehub-file="${filePath}"]` +
        (componentName ? `[data-vibehub-component="${componentName}"]` : '');
      const el = document.querySelector(selector);
      if (el) {
        selectedElement = el;
        updateHighlight(el);
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  });

  // Attach event listeners
  document.addEventListener('mouseover', handleMouseOver, true);
  document.addEventListener('click', handleClick, true);
  window.addEventListener('scroll', handleScroll, true);

  // Notify parent that overlay is ready
  if (window.parent !== window) {
    window.parent.postMessage({ type: 'VIBEHUB_OVERLAY_READY' }, '*');
  }

  console.log('[VibeHub] Visual editor overlay initialized');
})();
