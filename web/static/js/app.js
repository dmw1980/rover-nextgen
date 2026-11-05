/*
 * XMW Rover NextGen web control client.
 *
 * Sends tank-drive commands over Socket.IO. The server validates every command,
 * applies the selected speed limit, and enforces the watchdog and emergency
 * stop; this client only mirrors that state and never persists commands.
 */
(function () {
  'use strict';

  var SEND_INTERVAL_MS = 50; // maximum drive command rate: 20 Hz
  var LATENCY_INTERVAL_MS = 2000;
  var FULL_SCALE = 100;

  function clamp(value, low, high) {
    return Math.min(high, Math.max(low, value));
  }

  /*
   * Joystick mixing (screen coordinates: x right is positive, y down is positive).
   *   throttle = -y        (pushing the stick up drives forward)
   *   steering = x         (pushing the stick right turns right)
   *   left     = throttle + steering
   *   right    = throttle - steering
   * If either magnitude exceeds 1.0 both are divided by the larger one, which
   * keeps the left/right ratio (and therefore the turn radius) intact.
   * Results are percentages from -100 to 100. Non-finite inputs mix to zero.
   */
  function mixJoystick(x, y) {
    var nx = Number.isFinite(x) ? clamp(x, -1, 1) : 0;
    var ny = Number.isFinite(y) ? clamp(y, -1, 1) : 0;
    var throttle = -ny;
    var steering = nx;
    var left = throttle + steering;
    var right = throttle - steering;
    var largest = Math.max(Math.abs(left), Math.abs(right));
    if (largest > 1) {
      left /= largest;
      right /= largest;
    }
    return { left: left * FULL_SCALE, right: right * FULL_SCALE };
  }

  /*
   * Scale a full-range command into the selected speed mode so joystick travel
   * stays proportional. The server still clamps independently.
   */
  function scaleToLimit(command, limitPercent) {
    var factor = clamp(limitPercent, 0, FULL_SCALE) / FULL_SCALE;
    return { left: command.left * factor, right: command.right * factor };
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { mixJoystick: mixJoystick, scaleToLimit: scaleToLimit };
  }
  if (typeof document === 'undefined') {
    return;
  }

  var DIRECTIONS = {
    forward: { left: 1, right: 1 },
    reverse: { left: -1, right: -1 },
    left: { left: -1, right: 1 },
    right: { left: 1, right: -1 }
  };

  var $ = function (id) { return document.getElementById(id); };
  var els = {
    indicator: $('connection-indicator'),
    connectionText: $('connection-text'),
    headerSpeed: $('header-speed-mode'),
    estopButton: $('estop-button'),
    estopText: $('estop-status-text'),
    estopConfirm: $('estop-confirm'),
    estopClear: $('estop-clear-button'),
    stopButton: $('stop-button'),
    joystick: $('joystick'),
    knob: $('joystick-knob'),
    joyX: $('joy-x'),
    joyY: $('joy-y'),
    cameraGrid: $('camera-grid'),
    latency: $('t-latency')
  };
  var directionButtons = Array.prototype.slice.call(document.querySelectorAll('[data-direction]'));
  var speedButtons = Array.prototype.slice.call(document.querySelectorAll('[data-speed-mode]'));
  var cameraButtons = Array.prototype.slice.call(document.querySelectorAll('[data-camera-view]'));
  var lightingItems = Array.prototype.slice.call(document.querySelectorAll('[data-lighting]'));

  var session = {
    connected: false,
    everConnected: false,
    estop: false,
    limit: 40,
    lastState: null
  };
  var active = null; // current hold-to-drive source, if any
  var joy = { x: 0, y: 0 };
  var lastSentAt = 0;

  var socket = io({ reconnectionDelay: 500, reconnectionDelayMax: 2000 });

  function canDrive() {
    return session.connected && !session.estop;
  }

  function sendDrive() {
    if (!active || !canDrive()) {
      return;
    }
    var now = performance.now();
    if (now - lastSentAt < SEND_INTERVAL_MS * 0.9) {
      return;
    }
    lastSentAt = now;
    var target = active.target();
    socket.volatile.emit('drive', { left: target.left, right: target.right });
  }

  function sendStop() {
    if (socket.connected) {
      socket.emit('stop');
    }
  }

  function resetJoystick() {
    joy.x = 0;
    joy.y = 0;
    els.knob.style.transform = 'translate(0px, 0px)';
    els.joyX.textContent = '0.00';
    els.joyY.textContent = '0.00';
    els.joystick.classList.remove('is-active');
  }

  function releaseActive(notifyServer) {
    if (active) {
      active.release();
      active = null;
    }
    resetJoystick();
    if (notifyServer) {
      sendStop();
    }
  }

  function startActive(source) {
    if (!canDrive()) {
      return false;
    }
    if (active) {
      active.release();
    }
    active = source;
    lastSentAt = 0;
    sendDrive();
    return true;
  }

  /* Direction buttons: hold to drive */
  function directionTarget(name) {
    var direction = DIRECTIONS[name];
    return scaleToLimit(
      { left: direction.left * FULL_SCALE, right: direction.right * FULL_SCALE },
      session.limit
    );
  }

  function beginButton(button, pointerId) {
    var name = button.getAttribute('data-direction');
    var started = startActive({
      pointerId: pointerId,
      element: button,
      target: function () { return directionTarget(name); },
      release: function () { button.classList.remove('is-active'); }
    });
    if (started) {
      button.classList.add('is-active');
    }
  }

  directionButtons.forEach(function (button) {
    button.addEventListener('pointerdown', function (event) {
      if (event.pointerType === 'mouse' && event.button !== 0) {
        return;
      }
      event.preventDefault();
      // Touch pointers are captured implicitly; release so pointerleave can stop us.
      if (button.hasPointerCapture && button.hasPointerCapture(event.pointerId)) {
        button.releasePointerCapture(event.pointerId);
      }
      beginButton(button, event.pointerId);
    });
    button.addEventListener('pointerleave', function (event) {
      if (active && active.element === button && active.pointerId === event.pointerId) {
        releaseActive(true);
      }
    });
    button.addEventListener('keydown', function (event) {
      if ((event.key === ' ' || event.key === 'Enter') && !event.repeat) {
        event.preventDefault();
        beginButton(button, 'keyboard');
      }
    });
    button.addEventListener('keyup', function (event) {
      if ((event.key === ' ' || event.key === 'Enter') && active && active.element === button) {
        event.preventDefault();
        releaseActive(true);
      }
    });
    button.addEventListener('blur', function () {
      if (active && active.element === button) {
        releaseActive(true);
      }
    });
    button.addEventListener('contextmenu', function (event) { event.preventDefault(); });
  });

  els.stopButton.addEventListener('click', function () {
    releaseActive(true);
  });

  /* Virtual joystick */
  function moveJoystick(event) {
    var rect = els.joystick.getBoundingClientRect();
    var travel = (rect.width - els.knob.offsetWidth) / 2;
    if (travel <= 0) {
      return;
    }
    var dx = (event.clientX - (rect.left + rect.width / 2)) / travel;
    var dy = (event.clientY - (rect.top + rect.height / 2)) / travel;
    var length = Math.hypot(dx, dy);
    if (length > 1) {
      dx /= length;
      dy /= length;
    }
    joy.x = dx;
    joy.y = dy;
    els.knob.style.transform = 'translate(' + dx * travel + 'px, ' + dy * travel + 'px)';
    els.joyX.textContent = dx.toFixed(2);
    els.joyY.textContent = dy.toFixed(2);
  }

  els.joystick.addEventListener('pointerdown', function (event) {
    if (active || (event.pointerType === 'mouse' && event.button !== 0)) {
      return;
    }
    event.preventDefault();
    var started = startActive({
      pointerId: event.pointerId,
      element: els.joystick,
      target: function () { return scaleToLimit(mixJoystick(joy.x, joy.y), session.limit); },
      release: function () { els.joystick.classList.remove('is-active'); }
    });
    if (started) {
      els.joystick.setPointerCapture(event.pointerId);
      els.joystick.classList.add('is-active');
      moveJoystick(event);
    }
  });
  els.joystick.addEventListener('pointermove', function (event) {
    if (active && active.element === els.joystick && active.pointerId === event.pointerId) {
      moveJoystick(event);
    }
  });
  els.joystick.addEventListener('lostpointercapture', function (event) {
    if (active && active.element === els.joystick && active.pointerId === event.pointerId) {
      releaseActive(true);
    }
  });
  els.joystick.addEventListener('contextmenu', function (event) { event.preventDefault(); });

  function onGlobalPointerEnd(event) {
    if (active && active.pointerId === event.pointerId) {
      releaseActive(true);
    }
  }
  window.addEventListener('pointerup', onGlobalPointerEnd);
  window.addEventListener('pointercancel', onGlobalPointerEnd);

  /* Lost focus or hidden page: always stop */
  function stopEverything() {
    releaseActive(true);
  }
  window.addEventListener('blur', stopEverything);
  window.addEventListener('pagehide', stopEverything);
  window.addEventListener('beforeunload', stopEverything);
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      stopEverything();
    }
  });

  /* Emergency stop */
  function triggerEmergencyStop() {
    releaseActive(false);
    if (socket.connected) {
      socket.emit('emergency_stop');
    }
  }
  els.estopButton.addEventListener('click', triggerEmergencyStop);
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && !event.repeat) {
      triggerEmergencyStop();
    }
  });
  els.estopConfirm.addEventListener('change', function () {
    els.estopClear.disabled = !(session.estop && els.estopConfirm.checked);
  });
  els.estopClear.addEventListener('click', function () {
    if (!session.estop || !els.estopConfirm.checked) {
      return;
    }
    els.estopConfirm.checked = false;
    els.estopClear.disabled = true;
    socket.emit('clear_emergency_stop', null, reportFailure);
  });

  /* Speed mode and camera layout */
  speedButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      releaseActive(false);
      socket.emit('set_speed_mode', { mode: button.getAttribute('data-speed-mode') }, reportFailure);
    });
  });
  cameraButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      els.cameraGrid.setAttribute('data-view', button.getAttribute('data-camera-view'));
      cameraButtons.forEach(function (other) {
        other.setAttribute('aria-pressed', String(other === button));
      });
    });
  });

  function reportFailure(response) {
    if (response && response.ok === false) {
      console.warn('Command rejected:', response.error);
    }
  }

  /* Rendering */
  function percent(value) {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      return '-';
    }
    var rounded = Math.round(value);
    return (rounded > 0 ? '+' : '') + rounded + '%';
  }

  function words(text) {
    return String(text).replace(/_/g, ' ');
  }

  function setText(id, text, tone) {
    var element = $(id);
    element.textContent = text;
    element.classList.toggle('is-bad', tone === 'bad');
    element.classList.toggle('is-good', tone === 'good');
    element.classList.toggle('is-warn', tone === 'warn');
  }

  function deviceTone(status) {
    if (status === 'ready') { return 'good'; }
    if (status === 'fault' || status === 'disconnected') { return 'bad'; }
    if (status === 'degraded') { return 'warn'; }
    return null;
  }

  function currentLighting() {
    if (!session.everConnected) {
      return null;
    }
    if (session.lastState && session.lastState.emergency_stop) {
      return 'Emergency Stop';
    }
    if (!session.connected) {
      return 'WiFi Lost';
    }
    return session.lastState && session.lastState.rover_mode === 'manual' ? 'Manual' : 'Ready';
  }

  function renderControls() {
    var enabled = canDrive();
    directionButtons.forEach(function (button) { button.disabled = !enabled; });
    els.joystick.classList.toggle('is-disabled', !enabled);
    els.estopConfirm.disabled = !session.estop;
    els.estopClear.disabled = !(session.estop && els.estopConfirm.checked);
    document.body.classList.toggle('is-estop', session.estop);
    els.estopText.textContent = session.estop
      ? 'EMERGENCY STOP ACTIVE: driving is disabled.'
      : 'Emergency stop is not active.';
    var lighting = currentLighting();
    lightingItems.forEach(function (item) {
      var isCurrent = item.getAttribute('data-lighting') === lighting;
      item.classList.toggle('is-current', isCurrent);
      if (isCurrent) {
        item.setAttribute('aria-current', 'true');
      } else {
        item.removeAttribute('aria-current');
      }
    });
  }

  function renderConnection() {
    els.indicator.className = 'indicator ' + (session.connected ? 'indicator--online' : 'indicator--offline');
    els.connectionText.textContent = session.connected ? 'Connected' : 'Disconnected';
    if (!session.connected) {
      setText('t-latency', '-');
    }
  }

  function renderState(state) {
    session.lastState = state;
    session.estop = Boolean(state.emergency_stop);
    session.limit = state.speed_limit_percent;

    els.headerSpeed.textContent = state.speed_mode;
    speedButtons.forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.getAttribute('data-speed-mode') === state.speed_mode));
    });

    setText('t-mode', words(state.rover_mode), state.rover_mode === 'emergency_stop' ? 'bad' : null);
    setText('t-left', percent(state.command.left));
    setText('t-right', percent(state.command.right));
    setText('t-fl', percent(state.wheels.FL));
    setText('t-fr', percent(state.wheels.FR));
    setText('t-rl', percent(state.wheels.RL));
    setText('t-rr', percent(state.wheels.RR));
    setText('t-estop', state.emergency_stop ? 'ACTIVE' : 'Clear', state.emergency_stop ? 'bad' : 'good');
    setText(
      't-watchdog',
      words(state.watchdog.status) + ' (' + state.watchdog.timeout_ms + ' ms)',
      state.watchdog.status === 'timed_out' ? 'bad' : (state.watchdog.status === 'armed' ? 'good' : null)
    );
    setText('t-battery', words(state.battery.status), deviceTone(state.battery.status));
    setText('t-imu', words(state.imu.status), deviceTone(state.imu.status));
    setText('t-lidar', words(state.lidar.status), deviceTone(state.lidar.status));
    var front = state.cameras.front_camera;
    var rear = state.cameras.rear_camera;
    setText('t-front-camera', words(front.status) + ' (stream not connected)', deviceTone(front.status));
    setText('t-rear-camera', words(rear.status) + ' (stream not connected)', deviceTone(rear.status));

    renderControls();
  }

  /* Socket events */
  socket.on('connect', function () {
    session.connected = true;
    session.everConnected = true;
    renderConnection();
    renderControls();
    socket.emit('request_state');
  });
  socket.on('disconnect', function () {
    session.connected = false;
    releaseActive(false);
    renderConnection();
    renderControls();
  });
  socket.on('state', renderState);

  window.setInterval(sendDrive, SEND_INTERVAL_MS);
  window.setInterval(function () {
    if (!socket.connected) {
      return;
    }
    var started = performance.now();
    socket.timeout(1500).emit('request_state', null, function (error) {
      setText('t-latency', error ? 'timeout' : Math.round(performance.now() - started) + ' ms');
    });
  }, LATENCY_INTERVAL_MS);

  renderConnection();
  renderControls();
}());
