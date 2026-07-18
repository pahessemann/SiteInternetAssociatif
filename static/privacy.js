(() => {
  const STORAGE_KEY = "vertTigeConsent";

  const readConsent = () => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    } catch (_error) {
      return null;
    }
  };

  const writeConsent = (accepted) => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        accepted: Boolean(accepted),
        savedAt: new Date().toISOString(),
      }),
    );
  };

  const loadScript = (src, attributes = {}) => {
    if (!src || document.querySelector(`script[src="${src}"]`)) return;
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    Object.entries(attributes).forEach(([key, value]) => {
      if (value) script.setAttribute(key, value);
    });
    document.head.appendChild(script);
  };

  const loadGoogleAds = () => {
    const id = document.querySelector('meta[name="google-ads-id"]')?.content?.trim();
    if (!id || window.__vertTigeGoogleAdsLoaded) return;
    window.__vertTigeGoogleAdsLoaded = true;

    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function gtag() {
      window.dataLayer.push(arguments);
    };

    loadScript(`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`);
    window.gtag("js", new Date());
    window.gtag("config", id, { anonymize_ip: true });

    const shouldTrack = document.querySelector('meta[name="google-ads-conversion"]');
    const label = document.querySelector('meta[name="google-ads-conversion-label"]')?.content?.trim();
    if (shouldTrack && label) {
      window.gtag("event", "conversion", {
        send_to: `${id}/${label}`,
      });
    }
  };

  const loadAnalytics = () => {
    const provider = document.querySelector('meta[name="analytics-provider"]')?.content?.trim();
    const siteId = document.querySelector('meta[name="analytics-site-id"]')?.content?.trim();
    if (!provider || !siteId || window.__vertTigeAnalyticsLoaded) return;
    window.__vertTigeAnalyticsLoaded = true;

    if (provider === "plausible") {
      loadScript("https://plausible.io/js/script.js", {
        defer: "defer",
        "data-domain": siteId,
      });
    }
    if (provider === "fathom") {
      loadScript("https://cdn.usefathom.com/script.js", {
        defer: "defer",
        "data-site": siteId,
      });
    }
  };

  const applyExternalContent = (accepted) => {
    document.querySelectorAll("[data-consent-src]").forEach((frame) => {
      const placeholder = frame.closest("[data-external-content]")?.querySelector("[data-external-placeholder]");
      if (accepted) {
        frame.src = frame.dataset.consentSrc || "";
        frame.hidden = false;
        if (placeholder) placeholder.hidden = true;
      } else {
        frame.removeAttribute("src");
        frame.hidden = true;
        if (placeholder) placeholder.hidden = false;
      }
    });
  };

  const applyConsent = () => {
    const consent = readConsent();
    const accepted = consent?.accepted === true;
    applyExternalContent(accepted);
    if (accepted) {
      loadGoogleAds();
      loadAnalytics();
    }
  };

  const banner = document.querySelector("[data-cookie-banner]");
  const showBanner = () => {
    if (banner) banner.hidden = false;
  };
  const hideBanner = () => {
    if (banner) banner.hidden = true;
  };
  const saveAndApply = (accepted) => {
    writeConsent(accepted);
    hideBanner();
    applyConsent();
  };

  document.querySelectorAll("[data-cookie-accept]").forEach((button) => {
    button.addEventListener("click", () => saveAndApply(true));
  });
  document.querySelectorAll("[data-external-accept]").forEach((button) => {
    button.addEventListener("click", showBanner);
  });
  document.querySelectorAll("[data-cookie-refuse]").forEach((button) => {
    button.addEventListener("click", () => saveAndApply(false));
  });
  document.querySelectorAll("[data-cookie-open]").forEach((button) => {
    button.addEventListener("click", showBanner);
  });

  if (!readConsent() && banner) {
    showBanner();
  }
  applyConsent();
})();
