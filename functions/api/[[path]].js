// Cloudflare Pages Function: caching, allow-listed proxy for data.police.uk.
// Purpose: let the atlas poll the monthly-availability endpoint (and let
// visitors' browsers avoid upstream rate limits) with a 1-hour edge cache.
// It is NOT an open proxy: GET only, three fixed endpoints.
const ALLOWED = [
  /^\/api\/crimes-street-dates$/,
  /^\/api\/crime-categories$/,
  /^\/api\/crimes-street\/violent-crime$/,
];

export async function onRequest(context) {
  const { request } = context;
  if (request.method !== 'GET') {
    return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET' } });
  }
  const url = new URL(request.url);
  if (!ALLOWED.some((re) => re.test(url.pathname))) {
    return new Response('Not found', { status: 404 });
  }
  const target = 'https://data.police.uk' + url.pathname + url.search;
  const cache = caches.default;
  const cacheKey = new Request(target, { method: 'GET' });

  let response = await cache.match(cacheKey);
  if (response) return response;

  let upstream;
  try {
    upstream = await fetch(target, { headers: { 'User-Agent': 'USODA-Proxy (open-source; github.com/z7z8nbry4t-glitch/usoda)' } });
  } catch (e) {
    return new Response('Upstream unreachable', { status: 502 });
  }
  response = new Response(upstream.body, upstream);
  response.headers.set('Access-Control-Allow-Origin', '*');
  if (upstream.ok) {
    response.headers.set('Cache-Control', 'public, max-age=3600'); // client-facing 1 h cache
    context.waitUntil(cache.put(cacheKey, response.clone()));
  } else {
    response.headers.set('Cache-Control', 'no-store');
  }
  return response;
}
