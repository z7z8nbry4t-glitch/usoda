// Optional Cloudflare Worker proxy for data.police.uk to add caching and rate-limit protection
// Place as functions/api/[[path]].js for Pages Functions if needed
export async function onRequest(context) {
  const url = new URL(context.request.url);
  const target = 'https://data.police.uk' + url.pathname + url.search;
  const cache = caches.default;
  const cacheKey = new Request(target, context.request);
  let response = await cache.match(cacheKey);
  if (!response) {
    response = await fetch(target, {
      headers: { 'User-Agent': 'USODA-Proxy' }
    });
    response = new Response(response.body, response);
    response.headers.set('Cache-Control', 'public, max-age=3600'); // hourly cache
    response.headers.set('Access-Control-Allow-Origin', '*');
    context.waitUntil(cache.put(cacheKey, response.clone()));
  }
  return response;
}
