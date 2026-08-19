const CACHE_NAME="diario-autista-v20-scelta-esportazione";
const LOCAL_FILES=["./manifest.json","./icon-192.png","./icon-512.png"];
const JSZIP_URL="https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js";

self.addEventListener("install",e=>{
  e.waitUntil(caches.open(CACHE_NAME).then(c=>c.addAll(LOCAL_FILES)));
  self.skipWaiting();
});

self.addEventListener("activate",e=>{
  e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE_NAME).map(k=>caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener("fetch",e=>{
  if(e.request.method!=="GET") return;
  const u=new URL(e.request.url);

  if(e.request.url===JSZIP_URL){
    e.respondWith(
      caches.match(e.request).then(cached=>{
        if(cached) return cached;
        return fetch(e.request).then(r=>{
          const copy=r.clone();
          caches.open(CACHE_NAME).then(c=>c.put(e.request,copy));
          return r;
        });
      })
    );
    return;
  }

  if(u.origin!==self.location.origin) return;

  if(e.request.mode==="navigate"||u.pathname.endsWith("/index.html")){
    e.respondWith(
      fetch(e.request).then(r=>{
        const copy=r.clone();
        caches.open(CACHE_NAME).then(c=>c.put("./index.html",copy));
        return r;
      }).catch(()=>caches.match("./index.html"))
    );
    return;
  }

  e.respondWith(caches.match(e.request).then(c=>c||fetch(e.request)));
});
