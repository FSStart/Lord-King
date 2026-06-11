// Hiyori 桌面悬浮宠物 —— Electron 主进程
// 思路: 不重写任何业务逻辑, 直接用透明/无边框/置顶的小窗加载现有网页前端的
// "宠物模式"(?pet=1). 网页里的 Live2D、语音、好感度、画像等全部原样复用.
const { app, BrowserWindow, Tray, Menu, ipcMain, screen, shell, session } = require('electron');
const path = require('path');
const fs = require('fs');

const userDataDir = app.getPath('userData');
const configPath = path.join(userDataDir, 'config.json');

let win = null;
let tray = null;
let cfg = null;
let dragTimer = null;
let dragOff = null;
let clickThrough = false;

// ---------- 配置(服务器地址 + 窗口位置) ----------
function loadConfig() {
  const def = {
    url: 'http://110.42.217.122',   // Lord King 服务器(nginx, 80 端口); 可被 config.json / LORDKING_URL 覆盖
    x: null, y: null,
    w: 320, h: 440,
    alwaysOnTop: true,
  };
  let c = { ...def };
  try { Object.assign(c, JSON.parse(fs.readFileSync(configPath, 'utf-8'))); } catch (e) {}
  // 环境变量优先, 方便指向远程服务器: set LORDKING_URL=http://1.2.3.4
  if (process.env.LORDKING_URL) c.url = process.env.LORDKING_URL;
  return c;
}
function saveConfig() {
  try { fs.writeFileSync(configPath, JSON.stringify(cfg, null, 2)); } catch (e) {}
}
function petUrl() {
  const u = String(cfg.url || 'http://localhost').replace(/\/+$/, '');
  return u + '/?pet=1';
}

// ---------- 主窗口 ----------
function createWindow() {
  const { workArea } = screen.getPrimaryDisplay();
  const w = cfg.w, h = cfg.h;
  const x = (cfg.x != null) ? cfg.x : workArea.x + workArea.width - w - 24;
  const y = (cfg.y != null) ? cfg.y : workArea.y + workArea.height - h - 24;

  win = new BrowserWindow({
    width: w, height: h, x, y,
    frame: false,
    transparent: true,
    resizable: false,
    hasShadow: false,
    skipTaskbar: true,
    alwaysOnTop: cfg.alwaysOnTop,
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });

  win.setAlwaysOnTop(cfg.alwaysOnTop, 'screen-saver');
  win.loadURL(petUrl());

  // 麦克风等权限放行(本地受信任应用)
  session.defaultSession.setPermissionRequestHandler((wc, perm, cb) => cb(true));

  // 关闭按钮(若网页触发)只隐藏, 真正退出走托盘
  win.on('close', (e) => {
    if (!app.isQuitting) { e.preventDefault(); win.hide(); }
  });
  win.on('moved', () => {
    const [px, py] = win.getPosition();
    cfg.x = px; cfg.y = py; saveConfig();
  });
}

// ---------- 托盘 ----------
function buildTray() {
  tray = new Tray(path.join(__dirname, 'icon.png'));
  rebuildTrayMenu();
  tray.setToolTip('Hiyori 桌面宠物');
  tray.on('click', () => { if (win.isVisible()) win.focus(); else win.show(); });
}
function rebuildTrayMenu() {
  const menu = Menu.buildFromTemplate([
    { label: '显示 / 隐藏', click: () => (win.isVisible() ? win.hide() : win.show()) },
    {
      label: '始终置顶', type: 'checkbox', checked: cfg.alwaysOnTop,
      click: (mi) => { cfg.alwaysOnTop = mi.checked; win.setAlwaysOnTop(mi.checked, 'screen-saver'); saveConfig(); },
    },
    {
      label: '鼠标穿透(锁定不挡操作)', type: 'checkbox', checked: clickThrough,
      click: (mi) => { clickThrough = mi.checked; win.setIgnoreMouseEvents(mi.checked, { forward: true }); },
    },
    { type: 'separator' },
    { label: '打开完整界面…', click: () => shell.openExternal(cfg.url) },
    { label: '重新加载', click: () => win.reload() },
    { type: 'separator' },
    { label: '退出', click: () => { app.isQuitting = true; app.quit(); } },
  ]);
  tray.setContextMenu(menu);
}

// ---------- IPC: 拖拽 / 隐藏 / 退出 ----------
ipcMain.on('pet:drag-start', () => {
  if (!win) return;
  const c = screen.getCursorScreenPoint();
  const [wx, wy] = win.getPosition();
  dragOff = { dx: c.x - wx, dy: c.y - wy };
  if (dragTimer) clearInterval(dragTimer);
  dragTimer = setInterval(() => {
    const p = screen.getCursorScreenPoint();
    win.setPosition(p.x - dragOff.dx, p.y - dragOff.dy);
  }, 16);
});
ipcMain.on('pet:drag-end', () => {
  if (dragTimer) { clearInterval(dragTimer); dragTimer = null; }
  if (win) { const [px, py] = win.getPosition(); cfg.x = px; cfg.y = py; saveConfig(); }
});
ipcMain.on('pet:hide', () => { if (win) win.hide(); });
ipcMain.on('pet:quit', () => { app.isQuitting = true; app.quit(); });

// ---------- 生命周期(单实例 + 常驻托盘) ----------
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => { if (win) { win.show(); win.focus(); } });
  app.whenReady().then(() => {
    cfg = loadConfig();
    createWindow();
    buildTray();
  });
  // 关掉窗口不退出, 留在托盘
  app.on('window-all-closed', (e) => { /* keep alive in tray */ });
  app.on('activate', () => { if (win) win.show(); });
}
