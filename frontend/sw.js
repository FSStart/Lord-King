// Lord King SW - 惰性占位版本
// 调试期间 index.html 不再注册 SW,所以这个文件只是为了让
// 历史上注册过 SW 的浏览器拿到一个"啥也不干"的 SW,然后由
// index.html 里的 unregister 逻辑统一清理
// 调试 OK 后再启用真正的缓存策略

self.addEventListener('install', (event) => {
  // 立即激活,但什么也不做
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // 清掉所有旧缓存,但不主动 navigate 客户端(由 index.html 控制)
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
  })());
});

// fetch 完全不拦截,浏览器走默认网络
self.addEventListener('fetch', () => {});
