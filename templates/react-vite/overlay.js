// VibeHub Visual Editing Overlay
// 此脚本在沙盒中运行，负责转发组件点击事件到父窗口

(function() {
  'use strict';

  console.log('[VibeHub Overlay] Initializing...');

  // 当前模式
  let currentMode = 'preview';
  let selectedElement = null;

  // 监听来自父窗口的消息
  window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'SET_MODE') {
      currentMode = e.data.mode;
      console.log('[VibeHub Overlay] Mode changed to:', currentMode);

      // 更新光标样式
      document.body.style.cursor = currentMode === 'select' ? 'pointer' : '';
    }
  });

  // 点击事件处理
  document.addEventListener('click', function(e) {
    if (currentMode !== 'select') return;

    // 阻止默认行为（防止导航）
    e.preventDefault();
    e.stopPropagation();

    // 查找最近的带 data-vibehub-component 的元素
    const component = e.target.closest('[data-vibehub-component]');

    if (component) {
      // 获取元素位置
      const rect = component.getBoundingClientRect();

      // 发送给父窗口
      window.parent.postMessage({
        type: 'COMPONENT_CLICKED',
        componentId: component.dataset.vibehubId || '',
        componentName: component.dataset.vibehubComponent,
        filePath: component.dataset.vibehubFile || '',
        rect: {
          x: rect.x,
          y: rect.y,
          width: rect.width,
          height: rect.height
        }
      }, '*');

      console.log('[VibeHub Overlay] Component selected:', component.dataset.vibehubComponent);
    }
  }, true);

  // 悬停效果
  let hoveredElement = null;

  document.addEventListener('mouseover', function(e) {
    if (currentMode !== 'select') return;

    const component = e.target.closest('[data-vibehub-component]');

    if (component && component !== hoveredElement) {
      // 移除之前的悬停样式
      if (hoveredElement) {
        hoveredElement.style.outline = '';
      }

      // 添加悬停样式
      component.style.outline = '2px dashed #3b82f6';
      hoveredElement = component;
    }
  });

  document.addEventListener('mouseout', function(e) {
    if (hoveredElement && !hoveredElement.contains(e.relatedTarget)) {
      hoveredElement.style.outline = '';
      hoveredElement = null;
    }
  });

  console.log('[VibeHub Overlay] Ready');
})();
