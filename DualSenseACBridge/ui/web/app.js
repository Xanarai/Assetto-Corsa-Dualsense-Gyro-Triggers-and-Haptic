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
  isActive: true,
  hapticStatus: null,
  lastCtrlConn: null,
  vigemOk: true,
  ds4Running: false
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
    state.hapticStatus = data.haptic_status || null;

    // Apply language
    updateLanguageUI(state.lang);

    // Apply ViGEmBus and DS4 conflicts
    state.vigemOk = data.vigem_ok !== undefined ? data.vigem_ok : true;
    state.ds4Running = Boolean(data.ds4_running);
    updateVigembusUI();
    updateConflictUI();

    // Render settings
    renderSettings();

    // Update haptic status UI (banner + settings badge)
    updateHapticUI();

    // If device is disabled and controller is connected via USB, show alert modal once on startup
    if (state.hapticStatus && state.hapticStatus.device_disabled && state.hapticStatus.ctrl_connected && state.lastCtrlConn === 'usb' && !state.hasShownInitialAudioAlert) {
      state.hasShownInitialAudioAlert = true;
      setTimeout(() => {
        openHapticAlert();
      }, 600);
    }

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

  const btnTest = document.getElementById('btn-test-haptics');
  if (btnTest) btnTest.textContent = t('btn_test');

  const btnSave = document.getElementById('btn-save-cfg');
  if (btnSave) btnSave.textContent = t('cfg_btn_save');
  const btnUndo = document.getElementById('btn-undo');
  if (btnUndo) btnUndo.textContent = t('cfg_btn_undo');
  const btnAdv = document.getElementById('btn-adv-toggle');
  if (btnAdv) btnAdv.textContent = state.showAdvanced ? t('cfg_btn_adv_hide') : t('cfg_btn_adv_show');

  // ViGEmBus Driver banner texts
  const vigemTitle = document.getElementById('vigembus-warning-title');
  const vigemDesc = document.getElementById('vigembus-warning-desc');
  const vigemBtn = document.getElementById('vigembus-warning-btn');
  if (vigemTitle) vigemTitle.textContent = t('vigem_warn_title');
  if (vigemDesc) vigemDesc.textContent = t('vigem_warn_desc');
  if (vigemBtn) vigemBtn.textContent = t('vigem_warn_btn');

  // DS4Windows warning texts
  const ds4Title = document.getElementById('ds4-warning-title');
  const ds4Desc = document.getElementById('ds4-warning-desc');
  if (ds4Title) ds4Title.textContent = t('conflict_ds4_title');
  if (ds4Desc) ds4Desc.textContent = t('conflict_ds4_desc');

  // BT Haptic Notice banner texts
  const btTitle = document.getElementById('bt-haptic-title');
  const btDesc = document.getElementById('bt-haptic-desc');
  if (btTitle) btTitle.textContent = t('bt_haptic_notice_title');
  if (btDesc) btDesc.textContent = t('bt_haptic_notice_desc');

  // Conflict tip card texts
  const conflictTitle = document.getElementById('lbl-conflict-tip-title');
  const conflictDesc = document.getElementById('lbl-conflict-tip-desc');
  if (conflictTitle) conflictTitle.textContent = t('conflict_tip_title');
  if (conflictDesc) conflictDesc.textContent = t('conflict_tip_desc');

  localizeDiagnosticsModal();
}

function updateVigembusUI() {
  const banner = document.getElementById('vigembus-warning-banner');
  if (!banner) return;
  if (!state.vigemOk) {
    banner.classList.remove('hidden');
  } else {
    banner.classList.add('hidden');
  }
}

function updateConflictUI() {
  const banner = document.getElementById('ds4-warning-banner');
  if (!banner) return;
  if (state.ds4Running) {
    banner.classList.remove('hidden');
  } else {
    banner.classList.add('hidden');
  }
}

async function openViGEmBusDownload() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.open_vigembus_download) {
    try {
      await window.pywebview.api.open_vigembus_download();
    } catch (e) {
      console.error('Failed to open ViGEmBus download link:', e);
    }
  }
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

  // Info Button (before title)
  if (item.info_uk || item.info_en) {
    const infoBtn = document.createElement('button');
    infoBtn.className = 'info-btn';
    infoBtn.textContent = 'i';
    infoBtn.setAttribute('type', 'button');
    infoBtn.setAttribute('aria-label', 'Info');
    infoBtn.addEventListener('mouseenter', (e) => showTooltip(e, item));
    infoBtn.addEventListener('mouseleave', hideTooltip);
    left.appendChild(infoBtn);
  }

  const title = document.createElement('span');
  title.className = 'master-title';
  title.textContent = getItemLabel(item);
  left.appendChild(title);

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

  // Left side: Info + Name
  const left = document.createElement('div');
  left.className = 'setting-left';

  if (item.info_uk || item.info_en) {
    const infoBtn = document.createElement('button');
    infoBtn.className = 'info-btn';
    infoBtn.textContent = 'i';
    infoBtn.setAttribute('type', 'button');
    infoBtn.setAttribute('aria-label', 'Info');
    infoBtn.addEventListener('mouseenter', (e) => showTooltip(e, item));
    infoBtn.addEventListener('mouseleave', hideTooltip);
    left.appendChild(infoBtn);
  }

  const name = document.createElement('span');
  name.className = 'setting-name';
  name.textContent = getItemLabel(item);
  left.appendChild(name);

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

let _diagAnimationFrame = null;
let _diagTimeout = null;
let _isDiagPolling = false;
let _activeTest = null;

function openDiagnostics() {
  console.log("openDiagnostics called");
  if (window.pywebview && window.pywebview.api && window.pywebview.api.log_info) {
    try {
      window.pywebview.api.log_info("Diagnostics button pressed -> opening modal");
    } catch(e) {}
  }
  const overlay = document.getElementById('diagnostics-modal-overlay');
  if (!overlay) {
    console.error("diagnostics-modal-overlay not found in DOM!");
    return;
  }
  overlay.classList.remove('hidden');
  overlay.style.display = 'flex';
  overlay.style.opacity = '1';

  localizeDiagnosticsModal();
  backToDiagMenu();
  refreshHapticStatus();
}

function onDiagOverlayClick(e) {
  if (e.target && e.target.id === 'diagnostics-modal-overlay') {
    closeDiagnostics();
  }
}

async function closeDiagnostics() {
  console.log("closeDiagnostics called");
  if (window.pywebview && window.pywebview.api && window.pywebview.api.log_info) {
    try {
      window.pywebview.api.log_info("Diagnostics modal closed");
    } catch(e) {}
  }
  await backToDiagMenu();
  const overlay = document.getElementById('diagnostics-modal-overlay');
  if (overlay) {
    overlay.classList.add('hidden');
    overlay.style.display = 'none';
  }
}

async function backToDiagMenu() {
  if (_diagTimeout) {
    clearTimeout(_diagTimeout);
    _diagTimeout = null;
  }
  if (_diagAnimationFrame) {
    cancelAnimationFrame(_diagAnimationFrame);
    _diagAnimationFrame = null;
  }
  _isDiagPolling = false;
  if (_activeTest) {
    _activeTest = null;
    if (window.pywebview && window.pywebview.api) {
      try {
        await window.pywebview.api.stop_diagnostics();
      } catch (e) {
        console.error("stop_diagnostics error:", e);
      }
    }
  }

  // Reset trigger visual states
  const barL2 = document.getElementById('bar-l2');
  const barR2 = document.getElementById('bar-r2');
  const valL2 = document.getElementById('val-l2');
  const valR2 = document.getElementById('val-r2');
  if (barL2) { barL2.style.height = '0%'; barL2.style.background = ''; barL2.style.boxShadow = ''; }
  if (barR2) { barR2.style.height = '0%'; barR2.style.background = ''; barR2.style.boxShadow = ''; }
  if (valL2) valL2.textContent = '0%';
  if (valR2) valR2.textContent = '0%';

  // Reset gyro visual state
  const gyroModel = document.getElementById('gyro-model');
  if (gyroModel) gyroModel.style.transform = 'rotate(0deg)';
  const angleEl = document.getElementById('gyro-val-angle');
  const outputEl = document.getElementById('gyro-val-output');
  if (angleEl) angleEl.textContent = '0.0°';
  if (outputEl) outputEl.textContent = '0.0%';

  // Switch subviews
  const menu = document.getElementById('diag-menu');
  const viewTriggers = document.getElementById('diag-view-triggers');
  const viewGyro = document.getElementById('diag-view-gyro');
  if (menu) menu.classList.remove('hidden');
  if (viewTriggers) viewTriggers.classList.add('hidden');
  if (viewGyro) viewGyro.classList.add('hidden');
}

async function openTest(mode) {
  console.log("openTest called with mode:", mode);
  if (mode === 'triggers') {
    // Only check audio status and block if connected via USB!
    if (state.lastCtrlConn === 'usb') {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.check_haptic_status) {
        try {
          const hs = await window.pywebview.api.check_haptic_status();
          state.hapticStatus = hs;
          updateHapticUI();
        } catch (e) {
          console.error("check_haptic_status in openTest:", e);
        }
      }
      if (state.hapticStatus && state.hapticStatus.needs_setup) {
        openHapticAlert();
        return;
      }
    }
  }
  await _reallyStartTest(mode);
}

async function _reallyStartTest(mode) {
  const menu = document.getElementById('diag-menu');
  const viewTriggers = document.getElementById('diag-view-triggers');
  const viewGyro = document.getElementById('diag-view-gyro');
  
  if (menu) menu.classList.add('hidden');
  if (viewTriggers) viewTriggers.classList.add('hidden');
  if (viewGyro) viewGyro.classList.add('hidden');

  if (mode === 'triggers' && viewTriggers) {
    viewTriggers.classList.remove('hidden');
    const triggerStatusBadge = document.getElementById('diag-status-triggers-badge');
    if (triggerStatusBadge) {
      if (state.lastCtrlConn === 'bt') {
        triggerStatusBadge.textContent = t('diag_status_bt');
        triggerStatusBadge.className = 'status-badge yellow';
      } else {
        triggerStatusBadge.textContent = t('diag_status_active');
        triggerStatusBadge.className = 'status-badge green';
      }
    }
  } else if (mode === 'gyro' && viewGyro) {
    viewGyro.classList.remove('hidden');
  }

  _activeTest = mode;
  _isDiagPolling = false;

  if (window.pywebview && window.pywebview.api) {
    try {
      const res = await window.pywebview.api.start_diagnostics(mode);
      if (res && res.haptic_status) {
        state.hapticStatus = res.haptic_status;
        updateHapticUI();
      }
    } catch (e) {
      console.error("start_diagnostics error:", e);
    }
  }

  pollDiagnostics();
}

function getTriggerGradient(pct) {
  if (pct < 35) {
    return 'linear-gradient(180deg, #38bdf8 0%, #2563eb 100%)';
  } else if (pct < 70) {
    return 'linear-gradient(180deg, #a855f7 0%, #6366f1 100%)';
  } else {
    return 'linear-gradient(180deg, #ef4444 0%, #ea580c 100%)';
  }
}

function getTriggerGlow(pct) {
  if (pct < 35) {
    return '0 0 14px rgba(56, 189, 248, 0.4)';
  } else if (pct < 70) {
    return '0 0 18px rgba(168, 85, 247, 0.5)';
  } else {
    return '0 0 22px rgba(239, 68, 68, 0.65)';
  }
}

async function pollDiagnostics() {
  if (!_activeTest || _isDiagPolling) return;
  _isDiagPolling = true;

  if (window.pywebview && window.pywebview.api) {
    try {
      const data = await window.pywebview.api.get_diagnostics_data();
      if (_activeTest === 'triggers') {
        const l2 = Math.min(100, Math.max(0, (data.l2 || 0) * 100));
        const r2 = Math.min(100, Math.max(0, (data.r2 || 0) * 100));
        
        const barL2 = document.getElementById('bar-l2');
        const barR2 = document.getElementById('bar-r2');
        const valL2 = document.getElementById('val-l2');
        const valR2 = document.getElementById('val-r2');

        if (barL2) {
          barL2.style.height = `${l2}%`;
          barL2.style.background = getTriggerGradient(l2);
          barL2.style.boxShadow = getTriggerGlow(l2);
        }
        if (barR2) {
          barR2.style.height = `${r2}%`;
          barR2.style.background = getTriggerGradient(r2);
          barR2.style.boxShadow = getTriggerGlow(r2);
        }
        if (valL2) valL2.textContent = `${Math.round(l2)}%`;
        if (valR2) valR2.textContent = `${Math.round(r2)}%`;

      } else if (_activeTest === 'gyro') {
        const steerAngle = Number(data.steer_angle) || 0;
        const steerOutput = Number(data.steer_output) || 0;
        const maxAngle = Number(data.max_angle) || 65.0;

        const model = document.getElementById('gyro-model');
        if (model) {
          model.style.transform = `rotate(${steerAngle.toFixed(1)}deg)`;
        }

        const angleEl = document.getElementById('gyro-val-angle');
        const outputEl = document.getElementById('gyro-val-output');
        const maxEl = document.getElementById('gyro-val-max');

        if (angleEl) {
          const sign = steerAngle > 0 ? '+' : '';
          angleEl.textContent = `${sign}${steerAngle.toFixed(1)}°`;
        }
        if (outputEl) {
          const sign = steerOutput > 0 ? '+' : '';
          outputEl.textContent = `${sign}${steerOutput.toFixed(1)}%`;
        }
        if (maxEl) {
          maxEl.textContent = `${maxAngle.toFixed(1)}°`;
        }
      }
    } catch (e) {
      // Ignore transient frame errors
    }
  }

  _isDiagPolling = false;
  if (_activeTest) {
    _diagTimeout = setTimeout(pollDiagnostics, 25);
  }
}

function localizeDiagnosticsModal() {
  const setTxt = (id, key) => {
    const el = document.getElementById(id);
    if (el) el.textContent = t(key);
  };

  setTxt('diag-modal-title', 'diag_modal_title');
  setTxt('diag-menu-triggers-title', 'diag_menu_triggers_title');
  setTxt('diag-menu-triggers-desc', 'diag_menu_triggers_desc');
  setTxt('diag-menu-gyro-title', 'diag_menu_gyro_title');
  setTxt('diag-menu-gyro-desc', 'diag_menu_gyro_desc');

  setTxt('diag-btn-back-triggers', 'diag_btn_back');
  setTxt('diag-sub-triggers-title', 'diag_sub_triggers_title');
  setTxt('diag-sub-triggers-hint', 'diag_sub_triggers_hint');
  setTxt('diag-lbl-l2', 'diag_lbl_l2');
  setTxt('diag-lbl-r2', 'diag_lbl_r2');
  setTxt('diag-lbl-status-triggers', 'diag_lbl_status');
  const triggerStatusBadge = document.getElementById('diag-status-triggers-badge');
  if (triggerStatusBadge) {
    if (state.lastCtrlConn === 'bt') {
      triggerStatusBadge.textContent = t('diag_status_bt');
      triggerStatusBadge.className = 'status-badge yellow';
    } else {
      triggerStatusBadge.textContent = t('diag_status_active');
      triggerStatusBadge.className = 'status-badge green';
    }
  }
  setTxt('diag-btn-stop-triggers', 'diag_btn_stop');

  setTxt('diag-btn-back-gyro', 'diag_btn_back');
  setTxt('diag-sub-gyro-title', 'diag_sub_gyro_title');
  setTxt('diag-sub-gyro-hint', 'diag_sub_gyro_hint');
  setTxt('diag-lbl-steer-angle', 'diag_lbl_steer_angle');
  setTxt('diag-lbl-steer-output', 'diag_lbl_steer_output');
  setTxt('diag-lbl-max-angle', 'diag_lbl_max_angle');
  setTxt('diag-btn-stop-gyro', 'diag_btn_stop');
}

// Global window exports for seamless event handler binding & backward compatibility
window.openDiagnostics = openDiagnostics;
window.closeDiagnostics = closeDiagnostics;
window.onDiagOverlayClick = onDiagOverlayClick;
window.backToDiagMenu = backToDiagMenu;
window.openTest = openTest;
window.testHaptics = openDiagnostics;
window.openHapticAlert = openHapticAlert;
window.closeHapticAlert = closeHapticAlert;
window.hapticAlertOpenWizard = hapticAlertOpenWizard;
window.hapticAlertOpenSettings = hapticAlertOpenSettings;
window.wizardOpenSoundSettings = wizardOpenSoundSettings;
window.wizardOpenMmsys = wizardOpenMmsys;
window.wizardRefreshStatus = wizardRefreshStatus;
window.openHapticWizard = openHapticWizard;
window.closeHapticWizard = closeHapticWizard;
window.openViGEmBusDownload = openViGEmBusDownload;

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

        // Trigger haptic status refresh if connection or audio engine status changed
        if (state.lastCtrlConn !== status.ctrl_conn || state.lastAudioActive !== status.audio_active) {
          state.lastCtrlConn = status.ctrl_conn;
          state.lastAudioActive = status.audio_active;
          refreshHapticStatus();
          updateHapticUI();
        }

        // Bluetooth haptic notice banner on Dashboard
        const btBanner = document.getElementById('bt-haptic-banner');
        if (btBanner) {
          if (status.ctrl_conn === 'bt') {
            btBanner.classList.remove('hidden');
          } else {
            btBanner.classList.add('hidden');
          }
        }

        // Periodic background refresh if controller connected via USB and setup is needed
        if (!state._pollCounter) state._pollCounter = 0;
        state._pollCounter++;
        if (state._pollCounter >= 10 && status.ctrl_conn === 'usb') {
          state._pollCounter = 0;
          if (!state.hapticStatus || state.hapticStatus.needs_setup) {
            refreshHapticStatus();
          }
        }
      }

      // ViGEmBus status update
      if (status.vigem_ok !== undefined && status.vigem_ok !== state.vigemOk) {
        state.vigemOk = status.vigem_ok;
        updateVigembusUI();
      }

      // DS4Windows running conflict update
      if (status.ds4_running !== undefined && status.ds4_running !== state.ds4Running) {
        state.ds4Running = status.ds4_running;
        updateConflictUI();
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

// ─────────────────────────────────────────────────────────────────────────
// HAPTIC STATUS + WIZARD
// ─────────────────────────────────────────────────────────────────────────

function updateHapticUI() {
  const hs = state.hapticStatus;
  const banner = document.getElementById('haptic-warning-banner');
  const statusCard = document.getElementById('haptic-settings-status');
  const statusIcon = document.getElementById('haptic-status-icon');
  const statusText = document.getElementById('haptic-status-text');

  // No status data or controller not connected → hide everything
  if (!hs || !hs.ctrl_connected) {
    if (banner) banner.classList.add('hidden');
    if (statusCard) statusCard.classList.add('hidden');
    return;
  }

  // Bluetooth connected: HD audio haptics not supported over standard Windows BT
  if (state.lastCtrlConn === 'bt') {
    if (banner) banner.classList.add('hidden');

    if (statusCard) {
      statusCard.classList.remove('hidden');
      statusCard.style.borderColor = 'rgba(234, 179, 8, 0.3)';
      statusCard.style.background = 'rgba(234, 179, 8, 0.06)';
      statusCard.style.cursor = 'default';
      statusCard.onclick = null;
    }
    if (statusIcon) {
      statusIcon.textContent = 'ℹ';
      statusIcon.className = 'haptic-status-icon warn';
    }
    if (statusText) {
      statusText.textContent = t('haptic_status_bt');
      statusText.className = 'haptic-status-text warn';
    }
    return;
  }

  if (hs.needs_setup) {
    // Show warning banner on dashboard
    if (banner) {
      banner.classList.remove('hidden');
      const titleEl = document.getElementById('haptic-warning-title');
      const descEl = document.getElementById('haptic-warning-desc');
      const btnEl = document.getElementById('haptic-warning-btn');
      if (hs.device_disabled) {
        if (titleEl) titleEl.textContent = t('haptic_disabled_title');
        if (descEl) descEl.textContent = t('haptic_disabled_desc');
      } else {
        if (titleEl) titleEl.textContent = t('haptic_warn_title');
        if (descEl) descEl.textContent = t('haptic_warn_desc');
      }
      if (btnEl) btnEl.textContent = t('haptic_warn_btn');
    }

    // Show warning in settings
    if (statusCard) {
      statusCard.classList.remove('hidden');
      statusCard.style.borderColor = 'rgba(234, 179, 8, 0.3)';
      statusCard.style.background = 'rgba(234, 179, 8, 0.06)';
      statusCard.style.cursor = 'pointer';
      statusCard.onclick = openHapticWizard;
    }
    if (statusIcon) {
      statusIcon.textContent = '⚠';
      statusIcon.className = 'haptic-status-icon warn';
    }
    if (statusText) {
      statusText.textContent = hs.device_disabled ? t('haptic_disabled_title') : t('haptic_status_warn');
      statusText.className = 'haptic-status-text warn';
    }
  } else if (state.lastCtrlConn === 'bt') {
    // Bluetooth connected: HD audio haptics not supported over standard Windows BT
    if (banner) banner.classList.add('hidden');

    if (statusCard) {
      statusCard.classList.remove('hidden');
      statusCard.style.borderColor = 'rgba(234, 179, 8, 0.3)';
      statusCard.style.background = 'rgba(234, 179, 8, 0.06)';
      statusCard.style.cursor = 'default';
      statusCard.onclick = null;
    }
    if (statusIcon) {
      statusIcon.textContent = 'ℹ';
      statusIcon.className = 'haptic-status-icon warn';
    }
    if (statusText) {
      statusText.textContent = t('haptic_status_bt');
      statusText.className = 'haptic-status-text warn';
    }
  } else {
    // All OK (USB) — hide warning banner
    if (banner) banner.classList.add('hidden');

    // Show green status in settings
    if (statusCard) {
      statusCard.classList.remove('hidden');
      statusCard.style.borderColor = 'rgba(34, 197, 94, 0.25)';
      statusCard.style.background = 'rgba(34, 197, 94, 0.06)';
      statusCard.style.cursor = 'default';
      statusCard.onclick = null;
    }
    if (statusIcon) {
      statusIcon.textContent = '✓';
      statusIcon.className = 'haptic-status-icon ok';
    }
    if (statusText) {
      statusText.textContent = t('haptic_status_ok');
      statusText.className = 'haptic-status-text ok';
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────
// HAPTIC ALERT MODAL
// ─────────────────────────────────────────────────────────────────────────

function openHapticAlert() {
  if (state.lastCtrlConn === 'bt') return; // NEVER show audio alert modal when on Bluetooth!
  const overlay = document.getElementById('haptic-alert-overlay');
  if (!overlay) return;

  const hs = state.hapticStatus;
  const isDevDisabled = hs && hs.device_disabled;

  const titleEl = document.getElementById('haptic-alert-title');
  const descEl = document.getElementById('haptic-alert-desc');
  const btnWiz = document.getElementById('haptic-alert-btn-wizard');
  const btnSet = document.getElementById('haptic-alert-btn-settings');
  const btnCont = document.getElementById('haptic-alert-btn-continue');

  if (titleEl) titleEl.textContent = '⚠️ ' + t('haptic_alert_title');
  if (descEl) {
    descEl.textContent = isDevDisabled ? t('haptic_alert_disabled_desc') : t('haptic_alert_2ch_desc');
  }
  if (btnWiz) btnWiz.textContent = t('haptic_alert_btn_wizard');
  if (btnSet) btnSet.textContent = t('haptic_alert_btn_settings');
  if (btnCont) btnCont.textContent = t('haptic_alert_btn_continue');

  overlay.classList.remove('hidden');
  overlay.style.display = 'flex';
  overlay.style.opacity = '1';
}

function closeHapticAlert(proceed = false) {
  const overlay = document.getElementById('haptic-alert-overlay');
  if (overlay) {
    overlay.classList.add('hidden');
    overlay.style.display = 'none';
  }
  if (proceed && typeof _reallyStartTest === 'function') {
    _reallyStartTest('triggers');
  }
}

function hapticAlertOpenWizard() {
  closeHapticAlert(false);
  openHapticWizard();
}

async function hapticAlertOpenSettings() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.open_sound_settings) {
    try {
      await window.pywebview.api.open_sound_settings();
    } catch (e) {
      console.error("open_sound_settings error:", e);
    }
  }
}

async function wizardOpenSoundSettings() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.open_sound_settings) {
    try {
      await window.pywebview.api.open_sound_settings();
    } catch (e) {
      console.error("open_sound_settings error:", e);
    }
  }
}

async function wizardOpenMmsys() {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.open_mmsys_cpl) {
    try {
      await window.pywebview.api.open_mmsys_cpl();
    } catch (e) {
      console.error("open_mmsys_cpl error:", e);
    }
  }
}

async function wizardRefreshStatus() {
  const btn1 = document.getElementById('wizard-btn-refresh-status');
  const btn3 = document.getElementById('wizard-btn-verify-refresh');
  const status1 = document.getElementById('wizard-step1-status');
  if (btn1) btn1.disabled = true;
  if (btn3) btn3.disabled = true;
  if (status1) {
    status1.textContent = t('wizard_refreshing');
    status1.style.color = '#38bdf8';
  }

  try {
    const hs = await window.pywebview.api.check_haptic_status();
    state.hapticStatus = hs;
    updateHapticUI();

    if (hs && !hs.needs_setup) {
      if (status1) {
        status1.textContent = t('wizard_refresh_success');
        status1.style.color = '#4ade80';
      }
      setTimeout(() => {
        wizardGoToStep(3);
        wizardVerify();
      }, 500);
    } else if (hs && hs.device_found && !hs.device_disabled) {
      if (status1) {
        status1.textContent = `${t('wizard_step1_ok')} (${hs.device_name})`;
        status1.style.color = '#4ade80';
      }
      setTimeout(() => {
        if (hs.is_4ch && !hs.volume_ok) {
          wizardGoToStep(2);
        } else {
          wizardGoToStep(3);
          wizardVerify();
        }
      }, 700);
    } else {
      if (status1) {
        const errMsg = (hs && hs.device_disabled)
          ? t('wizard_verify_disabled')
          : t('wizard_step1_fail');
        status1.textContent = errMsg;
        status1.style.color = '#f87171';
      }
    }
  } catch (err) {
    if (status1) {
      status1.textContent = String(err);
      status1.style.color = '#f87171';
    }
  } finally {
    if (btn1) btn1.disabled = false;
    if (btn3) btn3.disabled = false;
  }
}

function openHapticWizard() {
  if (state.lastCtrlConn === 'bt') return; // Cannot setup USB audio over Bluetooth
  const overlay = document.getElementById('haptic-wizard-overlay');
  if (!overlay) return;
  overlay.classList.remove('hidden');

  const hs = state.hapticStatus;
  const isDevDisabled = hs && hs.device_disabled;

  // Localize wizard text (no wrench emoji)
  const wTitle = document.getElementById('wizard-title');
  if (wTitle) wTitle.textContent = t('wizard_title');

  const step1Title = document.getElementById('wizard-step1-title');
  const step1Desc = document.getElementById('wizard-step1-desc');
  const step1Note = document.getElementById('wizard-step1-note');
  const btn4chText = document.getElementById('wizard-btn-4ch-text');
  const btnOpenSetText = document.getElementById('wizard-btn-open-settings-text');
  const btnRefreshText = document.getElementById('wizard-btn-refresh-text');
  const btnMmsysText = document.getElementById('wizard-btn-open-mmsys-text');

  if (step1Title) step1Title.textContent = isDevDisabled ? t('wizard_step1_disabled_title') : t('wizard_step1_title');
  if (step1Desc) step1Desc.textContent = isDevDisabled ? t('wizard_step1_disabled_desc') : t('wizard_step1_desc');
  if (step1Note) step1Note.textContent = t('wizard_step1_note');
  if (btn4chText) btn4chText.textContent = t('wizard_btn_4ch');
  if (btnOpenSetText) btnOpenSetText.textContent = t('wizard_btn_open_sound');
  if (btnRefreshText) btnRefreshText.textContent = t('wizard_btn_refresh');
  if (btnMmsysText) btnMmsysText.textContent = t('wizard_btn_open_mmsys');

  document.getElementById('wizard-step2-title').textContent = t('wizard_step2_title');
  document.getElementById('wizard-step2-desc').textContent = t('wizard_step2_desc');
  document.getElementById('wizard-btn-vol-text').textContent = t('wizard_btn_vol');

  document.getElementById('wizard-step3-title').textContent = t('wizard_step3_title');
  document.getElementById('wizard-step3-desc').textContent = t('wizard_step3_checking');
  const btnVerifyOpenSet = document.getElementById('wizard-btn-verify-open-settings-text');
  if (btnVerifyOpenSet) btnVerifyOpenSet.textContent = t('wizard_btn_open_sound');
  const btnVerifyRefreshText = document.getElementById('wizard-btn-verify-refresh-text');
  if (btnVerifyRefreshText) btnVerifyRefreshText.textContent = t('wizard_btn_refresh');
  const btnVerifyMmsysText = document.getElementById('wizard-btn-verify-open-mmsys-text');
  if (btnVerifyMmsysText) btnVerifyMmsysText.textContent = t('wizard_btn_open_mmsys');

  // Reset to step 1
  wizardGoToStep(1);
}

function closeHapticWizard() {
  const overlay = document.getElementById('haptic-wizard-overlay');
  if (overlay) overlay.classList.add('hidden');

  // Refresh haptic status
  refreshHapticStatus();
}

function wizardGoToStep(step) {
  for (let i = 1; i <= 3; i++) {
    const view = document.getElementById(`wizard-view-${i}`);
    const dot = document.getElementById(`wizard-step-${i}`);
    if (view) view.classList.toggle('hidden', i !== step);
    if (dot) {
      dot.classList.remove('active', 'done');
      if (i < step) dot.classList.add('done');
      else if (i === step) dot.classList.add('active');
    }
  }
  // Clear status messages
  for (let i = 1; i <= 2; i++) {
    const status = document.getElementById(`wizard-step${i}-status`);
    if (status) status.textContent = '';
  }
}

async function wizardApply4Channel() {
  const btn = document.getElementById('wizard-btn-4ch');
  const status = document.getElementById('wizard-step1-status');
  if (btn) btn.disabled = true;
  if (status) {
    status.textContent = t('wizard_applying');
    status.style.color = '#38bdf8';
  }

  try {
    const res = await window.pywebview.api.run_haptic_wizard();
    if (res.format_ok || res.device_enabled) {
      if (status) {
        status.textContent = t('wizard_step1_ok');
        status.style.color = '#4ade80';
      }
      // Auto-advance to step 2 or 3 after short delay
      setTimeout(() => {
        if (res.volume_ok && res.format_ok) {
          wizardGoToStep(3);
          wizardVerify();
        } else if (res.format_ok && !res.volume_ok) {
          wizardGoToStep(2);
        } else {
          // Device enabled, check full status
          wizardGoToStep(3);
          wizardVerify();
        }
      }, 800);
    } else {
      if (status) {
        const errMsg = res.error ? `${t('wizard_step1_fail')} (${res.error})` : t('wizard_step1_fail');
        status.textContent = errMsg;
        status.style.color = '#f87171';
      }
      if (btn) btn.disabled = false;
    }
  } catch (err) {
    if (status) {
      status.textContent = String(err);
      status.style.color = '#f87171';
    }
    if (btn) btn.disabled = false;
  }
}

async function wizardApplyVolume() {
  const btn = document.getElementById('wizard-btn-vol');
  const status = document.getElementById('wizard-step2-status');
  if (btn) btn.disabled = true;
  if (status) {
    status.textContent = t('wizard_applying');
    status.style.color = '#38bdf8';
  }

  try {
    const res = await window.pywebview.api.set_haptic_volume();
    if (res.volume_ok) {
      if (status) {
        status.textContent = t('wizard_step2_ok');
        status.style.color = '#4ade80';
      }
      setTimeout(() => {
        wizardGoToStep(3);
        wizardVerify();
      }, 800);
    } else {
      if (status) {
        status.textContent = res.error || t('wizard_step2_fail');
        status.style.color = '#f87171';
      }
      if (btn) btn.disabled = false;
    }
  } catch (err) {
    if (status) {
      status.textContent = String(err);
      status.style.color = '#f87171';
    }
    if (btn) btn.disabled = false;
  }
}

async function wizardVerify() {
  const spinner = document.getElementById('wizard-verify-spinner');
  const resultDiv = document.getElementById('wizard-verify-result');
  const icon = document.getElementById('wizard-verify-icon');
  const text = document.getElementById('wizard-verify-text');
  const btnDone = document.getElementById('wizard-btn-done');
  const btnRetry = document.getElementById('wizard-btn-retry');
  const btnSettings = document.getElementById('wizard-btn-verify-open-settings');
  const btnRefresh = document.getElementById('wizard-btn-verify-refresh');
  const btnMmsys = document.getElementById('wizard-btn-verify-open-mmsys');
  const desc = document.getElementById('wizard-step3-desc');

  if (spinner) spinner.classList.remove('hidden');
  if (resultDiv) resultDiv.classList.add('hidden');
  if (btnDone) btnDone.classList.add('hidden');
  if (btnRetry) btnRetry.classList.add('hidden');
  if (btnSettings) btnSettings.classList.add('hidden');
  if (btnRefresh) btnRefresh.classList.add('hidden');
  if (btnMmsys) btnMmsys.classList.add('hidden');
  if (desc) desc.textContent = t('wizard_step3_checking');

  try {
    // Wait a moment for Windows audio subsystem to refresh
    await new Promise(r => setTimeout(r, 1500));

    const hs = await window.pywebview.api.check_haptic_status();
    state.hapticStatus = hs;

    if (spinner) spinner.classList.add('hidden');
    if (resultDiv) resultDiv.classList.remove('hidden');
    if (desc) desc.textContent = '';

    if (hs && !hs.needs_setup) {
      // Success
      if (icon) { icon.textContent = '✓'; icon.className = 'wizard-verify-icon ok'; }
      if (text) {
        text.textContent = t('wizard_verify_ok');
        text.className = 'wizard-verify-text ok';
      }
      if (btnDone) {
        btnDone.classList.remove('hidden');
        btnDone.textContent = t('wizard_btn_done');
      }
    } else {
      // Something still wrong
      let detail = [];
      if (hs && hs.device_disabled) detail.push(t('wizard_verify_disabled'));
      else if (hs && !hs.is_4ch) detail.push(t('wizard_verify_no_4ch'));
      if (hs && !hs.volume_ok) detail.push(t('wizard_verify_no_vol'));
      if (icon) { icon.textContent = '✕'; icon.className = 'wizard-verify-icon fail'; }
      if (text) {
        text.textContent = detail.join('. ') || t('wizard_verify_fail');
        text.className = 'wizard-verify-text fail';
      }
      if (btnRetry) {
        btnRetry.classList.remove('hidden');
        btnRetry.textContent = t('wizard_btn_retry');
      }
      if (btnRefresh) {
        btnRefresh.classList.remove('hidden');
        const txt = document.getElementById('wizard-btn-verify-refresh-text');
        if (txt) txt.textContent = t('wizard_btn_refresh');
      }
      if (btnMmsys) {
        btnMmsys.classList.remove('hidden');
        const txt = document.getElementById('wizard-btn-verify-open-mmsys-text');
        if (txt) txt.textContent = t('wizard_btn_open_mmsys');
      }
      if (btnSettings) {
        btnSettings.classList.remove('hidden');
        const spanTxt = document.getElementById('wizard-btn-verify-open-settings-text');
        if (spanTxt) spanTxt.textContent = t('wizard_btn_open_sound');
      }
    }

    updateHapticUI();
  } catch (err) {
    if (spinner) spinner.classList.add('hidden');
    if (resultDiv) resultDiv.classList.remove('hidden');
    if (icon) { icon.textContent = '✕'; icon.className = 'wizard-verify-icon fail'; }
    if (text) {
      text.textContent = String(err);
      text.className = 'wizard-verify-text fail';
    }
    if (btnRetry) btnRetry.classList.remove('hidden');
  }
}

function wizardRetry() {
  wizardGoToStep(1);
}

async function refreshHapticStatus() {
  try {
    if (window.pywebview && window.pywebview.api) {
      const hs = await window.pywebview.api.check_haptic_status();
      state.hapticStatus = hs;
      updateHapticUI();
    }
  } catch (e) {
    // Silent
  }
}
