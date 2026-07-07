(() => {
  const id = document.querySelector('meta[name="google-ads-id"]')?.content?.trim();
  if (!id) return;

  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function gtag() {
    window.dataLayer.push(arguments);
  };

  window.gtag("js", new Date());
  window.gtag("config", id);

  const shouldTrack = document.querySelector('meta[name="google-ads-conversion"]');
  const label = document.querySelector('meta[name="google-ads-conversion-label"]')?.content?.trim();
  if (shouldTrack && label) {
    window.gtag("event", "conversion", {
      send_to: `${id}/${label}`,
    });
  }
})();
