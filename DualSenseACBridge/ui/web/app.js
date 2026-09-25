/**
 * DualSense AC Bridge frontend controller.
 * Manages configuration state, bidirectional IPC with Python host, and telemetry status polling.
 */

const state = {
  lang: 'en',
  config: {},
  sections: [],
  items: [],
  texts: {},
  showAdvanced: false,
  undoStack: [],
  sliderStartVals: {},
  entryStartVals: {},
  isActive: true
};

// Hook pywebview lifecycle
window.addEventListener('pywebviewready', () => {
  initApp();
});

// Fallback if pywebviewready fired before script execution
if (window.pywebview && window.pywebview.api) {
  initApp();
}

async function initApp() {
  try {
    const data = await window.pywebview.api.get_initial_data();
    state.config = data.config || {};
    state.lang = data.lang || 'en';
    state.sections = data.sections || [];
    state.items = data.items || [];
    state.texts = data.texts || {};
    state.isActive = data.is_active !== undefined ? data.is_active : true;

    // Apply language
    updateLanguageUI(state.lang);

    // Render settings
    renderSettings();

    // Start live status polling loop
    startStatusPolling();
  } catch (err) {
    console.error('Failed to initialize app from Python API:', err);
  }
}

function switchTab(tabId) {
  const dashView = document.getElementById('view-dashboard');
  const cfgView = document.getElementById('view-settings');
  const dashBtn = document.getElementById('tab-btn-dashboard');
  const cfgBtn = document.getElementById('tab-btn-settings');

  if (tabId === 'dashboard') {
    dashView.classList.remove('hidden');
    cfgView.classList.add('hidden');
    dashBtn.classList.add('active');
    cfgBtn.classList.remove('active');
  } else {
    cfgView.classList.remove('hidden');
    dashView.classList.add('hidden');
    cfgBtn.classList.add('active');
    dashBtn.classList.remove('active');
  }
}

function t(key) {
  const dict = state.texts[state.lang] || state.texts['en'] || {};
  return dict[key] || key;
}

function getItemLabel(item) {
  return state.lang === 'uk' ? (item.name_uk || item.name_en) : (item.name_en || item.name_uk);
}

function getItemInfo(item) {
  return state.lang === 'uk' ? (item.info_uk || item.info_en) : (item.info_en || item.info_uk);
}

function getSectionTitle(sec) {
  return state.lang === 'uk' ? sec.title_uk : sec.title_en;
}

function setLanguage(lang) {
  if (lang !== 'en' && lang !== 'uk') return;
  state.lang = lang;
  updateLanguageUI(lang);
  renderSettings();

  // Inform Python backend
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.set_language(lang);
  }
}

function updateLanguageUI(lang) {
  const flagEn = document.getElementById('flag-en');
  const flagUa = document.getElementById('flag-ua');
  if (lang === 'en') {
    flagEn.classList.add('active');
    flagUa.classList.remove('active');
  } else {
    flagUa.classList.add('active');
    flagEn.classList.remove('active');
  }

  document.getElementById('tab-btn-dashboard').textContent = t('tab_main');
  document.getElementById('tab-btn-settings').textContent = t('tab_config');

  document.getElementById('app-subheading').textContent = t('app_subtitle');
  document.getElementById('lbl-status-ctrl').textContent = t('card_controller');
  document.getElementById('lbl-status-game').textContent = t('card_game');
  document.getElementById('lbl-status-svc').textContent = t('card_service');
  document.getElementById('lbl-tray-hint').textContent = t('tray_hint');

  const btnToggle = document.getElementById('btn-toggle-service');
  btnToggle.textContent = state.isActive ? t('btn_stop') : t('btn_start');

  document.getElementById('lbl-cfg-lang-title').textContent = t('cfg_lang_title');
  document.getElementById('lbl-cfg-lang-val').textContent = t('cfg_lang_active');
  document.getElementById('btn-save-cfg').textContent = t('cfg_btn_save');
  document.getElementById('btn-undo').textContent = t('cfg_btn_undo');
  document.getElementById('btn-adv-toggle').textContent = state.showAdvanced ? t('cfg_btn_adv_hide') : t('cfg_btn_adv_show');
}

function renderSettings() {
  const container = document.getElementById('settings-container');
  if (!container) return;
  container.innerHTML = '';

  state.sections.forEach(sec => {
    const secItems = state.items.filter(it => it.section === sec.id);
    if (!secItems.length) return;

    const secCard = document.createElement('div');
    secCard.className = 'card settings-section';

    // Identify Master Switch (if any)
    const masterItem = secItems.find(it => it.is_master);
    const otherItems = secItems.filter(it => !it.is_master);

    // Section Title (only if there is no master switch)
    if (!masterItem) {
      const titleEl = document.createElement('div');
      titleEl.className = 'section-title';
      titleEl.textContent = getSectionTitle(sec);
      secCard.appendChild(titleEl);
    }

    let isMasterEnabled = true;
    let masterGroup = null;

    if (masterItem) {
      isMasterEnabled = state.config[masterItem.key] !== undefined ? Boolean(state.config[masterItem.key]) : true;
      masterGroup = document.createElement('div');
      masterGroup.className = 'master-group' + (!isMasterEnabled ? ' disabled' : '');
      masterGroup.id = `master-group-${sec.id}`;
      
      const masterRow = renderMasterCard(masterItem, isMasterEnabled);
      masterGroup.appendChild(masterRow);
    }

    // Dependent child container
    const childContainer = document.createElement('div');
    childContainer.className = 'child-settings' + (!isMasterEnabled ? ' dimmed' : '');
    childContainer.id = `child-container-${sec.id}`;

    otherItems.forEach(item => {
      const row = renderSettingRow(item, isMasterEnabled);
      childContainer.appendChild(row);
    });

    if (masterGroup) {
      masterGroup.appendChild(childContainer);
      secCard.appendChild(masterGroup);
    } else {
      secCard.appendChild(childContainer);
    }
    
    container.appendChild(secCard);
  });
}

function renderMasterCard(item, isEnabled) {
  const card = document.createElement('div');
  card.className = 'master-row';
  card.id = `master-row-${item.key}`;

  const left = document.createElement('div');
  left.className = 'master-left';

  const title = document.createElement('span');
  title.className = 'master-title';
  title.textContent = getItemLabel(item);
  left.appendChild(title);

  // Info Button
  if (item.info_uk || item.info_en) {
    const infoBtn = document.createElement('button');
    infoBtn.className = 'info-btn';
    infoBtn.textContent = 'i';
    infoBtn.addEventListener('mouseenter', (e) => showTooltip(e, item));
    infoBtn.addEventListener('mouseleave', hideTooltip);
    left.appendChild(infoBtn);
  }

  card.appendChild(left);

  // Master Switch
  const switchLabel = document.createElement('label');
  switchLabel.className = 'toggle-switch master';

  const input = document.createElement('input');
  input.type = 'checkbox';
  input.checked = isEnabled;
  input.addEventListener('change', () => {
    const newChecked = input.checked;
    recordUndo(item.key, !newChecked, newChecked);
    state.config[item.key] = newChecked;

    // Visual border update
    const mGroup = document.getElementById(`master-group-${item.section}`);
    if (mGroup) {
      mGroup.classList.toggle('disabled', !newChecked);
    }

    // Dependent items update
    const childContainer = document.getElementById(`child-container-${item.section}`);
    if (childContainer) {
      childContainer.classList.toggle('dimmed', !newChecked);
      const inputs = childContainer.querySelectorAll('input, select');
      inputs.forEach(inp => inp.disabled = !newChecked);
    }
  });

  const sliderSpan = document.createElement('span');
  sliderSpan.className = 'toggle-slider';

  switchLabel.appendChild(input);
  switchLabel.appendChild(sliderSpan);
  card.appendChild(switchLabel);

  return card;
}

function renderSettingRow(item, isMasterEnabled) {
  const row = document.createElement('div');
  row.className = 'setting-row' + (item.is_advanced && !state.showAdvanced ? ' hidden-item' : '');
  row.dataset.key = item.key;
  if (item.is_advanced) {
    row.classList.add('advanced-row');
  }

  // Left side: Name + Info
  const left = document.createElement('div');
  left.className = 'setting-left';

  const name = document.createElement('span');
  name.className = 'setting-name';
  name.textContent = getItemLabel(item);
  left.appendChild(name);

  if (item.info_uk || item.info_en) {
    const infoBtn = document.createElement('button');
    infoBtn.className = 'info-btn';
    infoBtn.textContent = 'i';
    infoBtn.addEventListener('mouseenter', (e) => showTooltip(e, item));
    infoBtn.addEventListener('mouseleave', hideTooltip);
    left.appendChild(infoBtn);
  }
  row.appendChild(left);

  // Right side: Control
  const right = document.createElement('div');
  right.className = 'setting-right';

  const currentVal = state.config[item.key];

  if (item.widget === 'slider') {
    const group = document.createElement('div');
    group.className = 'slider-group';

    const valBadge = document.createElement('span');
    valBadge.className = 'slider-val-badge';
    valBadge.textContent = formatSliderValue(item, currentVal);

    const slider = document.createElement('input');
    slider.type = 'range';
    slider.className = 'range-slider';
    slider.min = item.min_val !== undefined ? item.min_val : 0;
    slider.max = item.max_val !== undefined ? item.max_val : 1;
    slider.step = item.step !== undefined ? item.step : 0.05;
    slider.value = currentVal !== undefined ? currentVal : slider.min;
    slider.disabled = !isMasterEnabled;

    slider.addEventListener('input', () => {
      valBadge.textContent = formatSliderValue(item, slider.value);
    });

    slider.addEventListener('mousedown', () => {
      state.sliderStartVals[item.key] = parseSliderValue(item, slider.value);
    });

    slider.addEventListener('change', () => {
      const startVal = state.sliderStartVals[item.key];
      const endVal = parseSliderValue(item, slider.value);
      if (startVal !== undefined && Math.abs(startVal - endVal) > 1e-4) {
        recordUndo(item.key, startVal, endVal);
      }
      state.config[item.key] = endVal;
    });

    group.appendChild(slider);
    group.appendChild(valBadge);
    right.appendChild(group);

  } else if (item.widget === 'switch') {
    const switchLabel = document.createElement('label');
    switchLabel.className = 'toggle-switch';

    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = Boolean(currentVal);
    input.disabled = !isMasterEnabled;

    input.addEventListener('change', () => {
      const newChecked = input.checked;
      recordUndo(item.key, !newChecked, newChecked);
      state.config[item.key] = newChecked;
    });

    const sliderSpan = document.createElement('span');
    sliderSpan.className = 'toggle-slider';

    switchLabel.appendChild(input);
    switchLabel.appendChild(sliderSpan);
    right.appendChild(switchLabel);

  } else if (item.widget === 'select' || item.widget === 'dropdown') {
    const select = document.createElement('select');
    select.className = 'input-select';
    select.disabled = !isMasterEnabled;

    const options = item.options || [];
    options.forEach(opt => {
      const optEl = document.createElement('option');
      const val = typeof opt === 'object' ? opt.value : opt;
      let label = val;
      if (typeof opt === 'object') {
        label = (state.lang === 'uk' ? opt.label_uk : opt.label_en) || opt.label || val;
      }
      optEl.value = val;
      optEl.textContent = label;
      if (String(currentVal).toLowerCase() === String(val).toLowerCase()) {
        optEl.selected = true;
      }
      select.appendChild(optEl);
    });

    select.addEventListener('change', () => {
      const oldVal = state.config[item.key];
      const newVal = select.value;
      if (oldVal !== newVal) {
        recordUndo(item.key, oldVal, newVal);
        state.config[item.key] = newVal;
      }
    });

    right.appendChild(select);

  } else {
    // Text / Number Entry
    const input = document.createElement('input');
    input.type = item.type === 'int' ? 'number' : 'text';
    input.className = 'input-text';
    input.value = currentVal !== undefined ? currentVal : '';
    input.disabled = !isMasterEnabled;

    input.addEventListener('focus', () => {
      state.entryStartVals[item.key] = input.value;
    });

    input.addEventListener('blur', () => {
      const oldVal = state.entryStartVals[item.key];
      const newVal = input.value;
      if (oldVal !== undefined && oldVal !== newVal) {
        const parsedOld = item.type === 'int' ? parseInt(oldVal, 10) : oldVal;
        const parsedNew = item.type === 'int' ? parseInt(newVal, 10) : newVal;
        recordUndo(item.key, parsedOld, parsedNew);
        state.config[item.key] = parsedNew;
      }
    });

    right.appendChild(input);
  }

  row.appendChild(right);
  return row;
}

function formatSliderValue(item, val) {
  const num = parseFloat(val) || 0;
  if (item.format && item.format.includes('°')) {
    return `${Math.round(num)}°`;
  }
  if (item.type === 'int') {
    return `${Math.round(num)}`;
  }
  return num.toFixed(2);
}

function parseSliderValue(item, val) {
  return item.type === 'int' ? parseInt(val, 10) : parseFloat(val);
}

function toggleAdvanced() {
  state.showAdvanced = !state.showAdvanced;
  const btn = document.getElementById('btn-adv-toggle');
  btn.textContent = state.showAdvanced ? t('cfg_btn_adv_hide') : t('cfg_btn_adv_show');

  const advRows = document.querySelectorAll('.advanced-row');
  advRows.forEach(row => {
    row.classList.toggle('hidden-item', !state.showAdvanced);
  });
}

function showTooltip(event, item) {
  const tooltip = document.getElementById('floating-tooltip');
  const titleEl = document.getElementById('tooltip-title');
  const textEl = document.getElementById('tooltip-text');

  titleEl.textContent = getItemLabel(item);
  textEl.textContent = getItemInfo(item);

  // Position relative to target button
  const rect = event.target.getBoundingClientRect();
  const tipWidth = Math.min(320, window.innerWidth - 32);

  tooltip.style.maxWidth = `${tipWidth}px`;
  tooltip.classList.add('visible');

  // Let DOM measure actual rendered dimensions
  const tipRect = tooltip.getBoundingClientRect();
  let x = rect.left - 6;
  let y = rect.bottom + 6;

  // Horizontal boundary protection
  if (x + tipRect.width > window.innerWidth - 12) {
    x = window.innerWidth - tipRect.width - 12;
  }
  if (x < 12) x = 12;

  // Vertical boundary protection (flip above if overflowing window)
  if (y + tipRect.height > window.innerHeight - 12) {
    y = Math.max(10, rect.top - tipRect.height - 6);
  }

  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
}

function hideTooltip() {
  const tooltip = document.getElementById('floating-tooltip');
  tooltip.classList.remove('visible');
}

function recordUndo(key, oldValue, newValue) {
  state.undoStack.push({ key, oldValue, newValue });
  const undoBtn = document.getElementById('btn-undo');
  undoBtn.classList.add('active');
}

function triggerUndo() {
  if (!state.undoStack.length) {
    showToast(t('cfg_undo_empty'), '#a1a1aa');
    return;
  }

  const { key, oldValue } = state.undoStack.pop();
  state.config[key] = oldValue;

  // Re-render row widget in DOM
  const item = state.items.find(it => it.key === key);
  const row = document.querySelector(`.setting-row[data-key="${key}"], .master-row[id="master-row-${key}"]`);

  if (item && row) {
    if (item.widget === 'slider') {
      const slider = row.querySelector('.range-slider');
      const badge = row.querySelector('.slider-val-badge');
      if (slider) slider.value = oldValue;
      if (badge) badge.textContent = formatSliderValue(item, oldValue);
    } else if (item.is_master || item.widget === 'switch') {
      const checkbox = row.querySelector('input[type="checkbox"]');
      if (checkbox) checkbox.checked = Boolean(oldValue);

      if (item.is_master) {
        const mGroup = document.getElementById(`master-group-${item.section}`);
        if (mGroup) mGroup.classList.toggle('disabled', !oldValue);
        const childContainer = document.getElementById(`child-container-${item.section}`);
        if (childContainer) {
          childContainer.classList.toggle('dimmed', !oldValue);
          const inputs = childContainer.querySelectorAll('input, select');
          inputs.forEach(inp => inp.disabled = !oldValue);
        }
      }
    } else if (item.widget === 'select' || item.widget === 'dropdown') {
      const select = row.querySelector('.input-select');
      if (select) select.value = oldValue;
    } else {
      const input = row.querySelector('.input-text');
      if (input) input.value = oldValue;
    }
  }

  // Update button active state
  if (!state.undoStack.length) {
    document.getElementById('btn-undo').classList.remove('active');
  }

  const name = item ? getItemLabel(item) : key;
  showToast(`${t('cfg_undo_done').replace('{name}', name)}`, '#38bdf8');

  // Push updated config to Python
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.save_single_key(key, oldValue);
  }
}

// Global Ctrl+Z Listener
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
    e.preventDefault();
    triggerUndo();
  }
});

async function saveConfig() {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    await window.pywebview.api.save_config(state.config);
    showToast(t('cfg_saved'), '#22c55e');
  } catch (err) {
    console.error('Error saving config:', err);
  }
}

function showToast(msg, color) {
  const toast = document.getElementById('cfg-toast');
  toast.textContent = msg;
  toast.style.color = color || '#22c55e';
  setTimeout(() => {
    toast.textContent = '';
  }, 2400);
}

async function toggleService() {
  if (!window.pywebview || !window.pywebview.api) return;
  try {
    const res = await window.pywebview.api.toggle_service();
    state.isActive = res.is_active;

    const btn = document.getElementById('btn-toggle-service');
    btn.textContent = state.isActive ? t('btn_stop') : t('btn_start');
    btn.className = `btn-action-big ${state.isActive ? 'stop' : 'start'}`;

    const svcBadge = document.getElementById('val-status-svc');
    svcBadge.textContent = state.isActive ? t('service_running') : t('service_stopped');
    svcBadge.className = `status-badge ${state.isActive ? 'green' : 'red'}`;
  } catch (err) {
    console.error('Error toggling service:', err);
  }
}

let _isPolling = false;

async function pollStatus() {
  if (_isPolling) return;
  _isPolling = true;

  try {
    if (window.pywebview && window.pywebview.api) {
      const status = await window.pywebview.api.get_status();

      const ctrlBadge = document.getElementById('val-status-ctrl');
      if (ctrlBadge) {
        if (status.ctrl_conn === 'usb') {
          ctrlBadge.textContent = t('ctrl_usb');
          ctrlBadge.className = 'status-badge green';
        } else if (status.ctrl_conn === 'bt') {
          ctrlBadge.textContent = t('ctrl_bt');
          ctrlBadge.className = 'status-badge blue';
        } else {
          ctrlBadge.textContent = t('ctrl_disconnected');
          ctrlBadge.className = 'status-badge gray';
        }
      }

      const gameBadge = document.getElementById('val-status-game');
      if (gameBadge) {
        if (status.udp_active) {
          gameBadge.textContent = `${t('game_active_udp').replace('{rate}', Math.round(status.packet_rate))}`;
          gameBadge.className = 'status-badge green';
        } else if (status.sm_active) {
          gameBadge.textContent = t('game_active_sm');
          gameBadge.className = 'status-badge green';
        } else {
          gameBadge.textContent = t('game_waiting');
          gameBadge.className = 'status-badge yellow';
        }
      }

      const svcBadge = document.getElementById('val-status-svc');
      if (svcBadge) {
        state.isActive = status.is_active;
        svcBadge.textContent = state.isActive ? t('service_running') : t('service_stopped');
        svcBadge.className = `status-badge ${state.isActive ? 'green' : 'red'}`;
      }

      const btn = document.getElementById('btn-toggle-service');
      if (btn) {
        btn.textContent = state.isActive ? t('btn_stop') : t('btn_start');
        btn.className = `btn-action-big ${state.isActive ? 'stop' : 'start'}`;
      }
    }
  } catch (err) {
    // Ignore background transient errors
  } finally {
    _isPolling = false;
    // Sequential poll: only schedule next request after current one has resolved
    setTimeout(pollStatus, 400);
  }
}

function startStatusPolling() {
  setTimeout(pollStatus, 200);
}
