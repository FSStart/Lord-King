// 预加载脚本: 给网页注入一个最小、安全的桥, 让宠物模式知道自己跑在 Electron 里,
// 并提供托盘/窗口控制. contextIsolation 开启, 网页拿不到 node 能力.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('petAPI', {
  isElectron: true,
  // 拖拽: 网页在角色上按下时调用, 主进程让窗口跟随光标
  dragStart: () => ipcRenderer.send('pet:drag-start'),
  dragEnd: () => ipcRenderer.send('pet:drag-end'),
  // 隐藏到托盘
  hide: () => ipcRenderer.send('pet:hide'),
  // 退出
  quit: () => ipcRenderer.send('pet:quit'),
});
