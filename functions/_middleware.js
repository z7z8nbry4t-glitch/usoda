// Cloudflare Pages Function: send the old address to the main address.
// Only the exact production host redirects. Preview deployments
// (<id>.usoda.pages.dev) and the custom domain are served as normal.
const OLD_HOST = 'usoda.pages.dev';
const MAIN_HOST = 'usoda.alphatedigital.co.uk';

export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (url.hostname === OLD_HOST) {
    url.protocol = 'https:';
    url.hostname = MAIN_HOST;
    url.port = '';
    return Response.redirect(url.toString(), 301);
  }
  return context.next();
}
