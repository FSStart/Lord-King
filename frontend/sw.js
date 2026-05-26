// Lord King PWA Service Worker
// 提供基础缓存和推送通知支持

const CACHE_NAME = 'lordking-v1';
const STATIC_FILES = [
  '/',
  '/index.html',
  '/manifest.json'
];

// 安装
self.addEventListener('install', (event) => {
  console.log('[SW] 安装');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_FILES).catch((err) => {
        console.warn('[SW] 缓存失败,继续:', err);
      });
    })
  );
  self.skipWaiting();
});

// 激活 - 清理旧缓存
self.addEventListener('activate', (event) => {
  console.log('[SW] 激活');
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// 拦截请求 - 网络优先策略(适合动态内容)
self.addEventListener('fetch', (event) => {
  // 只缓存 GET 请求
  if (event.request.method !== 'GET') return;

  // API 请求和 WebSocket 不缓存
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/ws') ||
      url.pathname.startsWith('/auth') ||
      url.pathname.startsWith('/chat') ||
      url.pathname.startsWith('/tts') ||
      url.pathname.startsWith('/relationship') ||
      url.pathname.startsWith('/reminder')) {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // 成功就更新缓存
        if (response && response.status === 200) {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }
        return response;
      })
      .catch(() => {
        // 网络失败,从缓存读取
        return caches.match(event.request);
      })
  );
});

// 通知点击 - 打开应用
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then((clientList) => {
      // 如果已有窗口,聚焦
      for (const client of clientList) {
        if (client.url && 'focus' in client) {
          return client.focus();
        }
      }
      // 否则打开新窗口
      if (clients.openWindow) {
        return clients.openWindow('/');
      }
    })
  );
});
