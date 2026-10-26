(() => {
  const parseAspect = (value, image) => {
    if (value === "original" && image?.naturalWidth && image?.naturalHeight) {
      return image.naturalWidth / image.naturalHeight;
    }
    const [w, h] = String(value || "16:9").split(":").map(Number);
    return w && h ? w / h : 16 / 9;
  };

  const initEditor = (form) => {
    const fileInput = form.querySelector("[data-crop-file]");
    const librarySelect = form.querySelector("[data-crop-library]");
    const currentButton = form.querySelector("[data-crop-current]");
    const tool = form.querySelector("[data-crop-tool]");
    const canvas = form.querySelector("[data-crop-canvas]");
    const output = form.querySelector("[data-crop-output]");
    const aspect = form.querySelector("[data-crop-aspect]");
    const zoom = form.querySelector("[data-crop-zoom]");
    const posX = form.querySelector("[data-crop-x]");
    const posY = form.querySelector("[data-crop-y]");

    if (!tool || !canvas || !output || !aspect) return;

    const context = canvas.getContext("2d");
    let image = null;
    let cropIsActive = false;

    const resetControls = () => {
      zoom.value = "1";
      posX.value = "50";
      posY.value = "50";
    };

    const render = () => {
      if (!image) return;
      const ratio = parseAspect(aspect.value, image);
      let width = 1200;
      let height = Math.round(width / ratio);
      if (height > 1200) {
        height = 1200;
        width = Math.round(height * ratio);
      }

      canvas.width = width;
      canvas.height = height;
      context.clearRect(0, 0, width, height);
      context.fillStyle = "#f8faf6";
      context.fillRect(0, 0, width, height);

      const baseScale = Math.max(width / image.naturalWidth, height / image.naturalHeight);
      const scale = baseScale * Number(zoom.value || 1);
      const drawWidth = image.naturalWidth * scale;
      const drawHeight = image.naturalHeight * scale;
      const overflowX = Math.max(0, drawWidth - width);
      const overflowY = Math.max(0, drawHeight - height);
      const x = -overflowX * (Number(posX.value || 50) / 100);
      const y = -overflowY * (Number(posY.value || 50) / 100);

      context.drawImage(image, x, y, drawWidth, drawHeight);
    };

    const loadSource = (src) => {
      if (!src) {
        cropIsActive = false;
        output.value = "";
        tool.hidden = true;
        return;
      }

      const nextImage = new Image();
      nextImage.onload = () => {
        image = nextImage;
        cropIsActive = true;
        output.value = "";
        tool.hidden = false;
        resetControls();
        render();
      };
      nextImage.src = src;
    };

    fileInput?.addEventListener("change", () => {
      const file = fileInput.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        loadSource(String(reader.result || ""));
        fileInput.value = "";
      };
      reader.readAsDataURL(file);
    });

    librarySelect?.addEventListener("change", () => {
      loadSource(librarySelect.value);
    });

    currentButton?.addEventListener("click", () => {
      loadSource(currentButton.dataset.currentImage || "");
    });

    [aspect, zoom, posX, posY].forEach((input) => {
      input?.addEventListener("input", render);
      input?.addEventListener("change", render);
    });

    form.addEventListener("submit", () => {
      if (cropIsActive && image) {
        render();
        output.value = canvas.toDataURL("image/jpeg", 0.9);
      }
    });
  };

  const previewFile = (input, callback) => {
    const file = input?.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => callback(String(reader.result || ""));
    reader.readAsDataURL(file);
  };

  const initRichTextEditor = () => {
    const panel = document.querySelector("[data-rich-editor-panel]");
    const editor = panel?.querySelector("[data-rich-editor]");
    const input = panel?.querySelector("[data-rich-input]");
    const toolbar = panel?.querySelector("[data-rich-toolbar]");
    const sizeSelect = panel?.querySelector("[data-rich-size]");
    const form = panel?.closest("form");

    if (!panel || !editor || !input) return;

    let savedRange = null;

    const sync = () => {
      input.value = editor.innerHTML;
    };

    const selectionIsInEditor = () => {
      const selection = window.getSelection();
      if (!selection || selection.rangeCount === 0) return false;
      const range = selection.getRangeAt(0);
      return editor.contains(range.commonAncestorContainer);
    };

    const saveSelection = () => {
      const selection = window.getSelection();
      if (!selection || selection.rangeCount === 0 || !selectionIsInEditor()) return;
      savedRange = selection.getRangeAt(0).cloneRange();
    };

    const restoreFocus = () => {
      editor.focus();
      if (savedRange) {
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(savedRange);
      }
      return selectionIsInEditor();
    };

    const applyInlineSize = (size) => {
      if (!size || !restoreFocus()) return;
      const selection = window.getSelection();
      if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return;

      const range = selection.getRangeAt(0);
      const wrapper = document.createElement("span");
      wrapper.className = `text-size-${size}`;

      try {
        range.surroundContents(wrapper);
      } catch (_error) {
        const fragment = range.extractContents();
        wrapper.appendChild(fragment);
        range.insertNode(wrapper);
      }

      selection.removeAllRanges();
      const nextRange = document.createRange();
      nextRange.selectNodeContents(wrapper);
      selection.addRange(nextRange);
      sync();
    };

    toolbar?.addEventListener("mousedown", (event) => {
      saveSelection();
      if (event.target.closest("[data-rich-command]")) {
        event.preventDefault();
      }
    });

    toolbar?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-rich-command]");
      if (!button || !restoreFocus()) return;
      document.execCommand(button.dataset.richCommand, false, null);
      sync();
    });

    sizeSelect?.addEventListener("mousedown", saveSelection);
    sizeSelect?.addEventListener("change", () => {
      applyInlineSize(sizeSelect.value);
      sizeSelect.value = "";
    });

    editor.addEventListener("keyup", saveSelection);
    editor.addEventListener("mouseup", saveSelection);
    editor.addEventListener("input", () => {
      saveSelection();
      sync();
    });
    editor.addEventListener("paste", (event) => {
      event.preventDefault();
      const text = event.clipboardData?.getData("text/plain") || "";
      document.execCommand("insertText", false, text);
      sync();
    });
    form?.addEventListener("submit", sync);
    sync();
  };

  const initHomeImageDefaults = () => {
    const logoResetField = document.querySelector("[data-logo-reset-field]");
    const logoButton = document.querySelector("[data-reset-logo]");
    const logoFile = document.querySelector("[data-logo-file]");
    const logoPreview = document.querySelector("[data-logo-preview]");
    const homeResetField = document.querySelector("[data-home-image-reset-field]");
    const homeButton = document.querySelector("[data-reset-home-image]");
    const homeFile = document.querySelector("[data-home-image-file]");
    const homeChoice = document.querySelector("[data-home-image-choice]");
    const homePreview = document.querySelector("[data-home-image-preview]");
    const instagramBannerResetField = document.querySelector("[data-instagram-banner-reset-field]");
    const instagramBannerButton = document.querySelector("[data-reset-instagram-banner]");
    const instagramBannerFile = document.querySelector("[data-instagram-banner-file]");
    const instagramBannerChoice = document.querySelector("[data-instagram-banner-choice]");
    const instagramBannerPreview = document.querySelector("[data-instagram-banner-preview]");

    logoButton?.addEventListener("click", () => {
      if (logoResetField) logoResetField.value = "1";
      if (logoFile) logoFile.value = "";
      if (logoPreview && logoButton.dataset.defaultSrc) {
        const image = document.createElement("img");
        image.className = "logo-preview";
        image.src = logoButton.dataset.defaultSrc;
        image.alt = "Logo par défaut";
        logoPreview.replaceChildren(image);
      }
    });

    logoFile?.addEventListener("change", () => {
      if (logoResetField) logoResetField.value = "";
      previewFile(logoFile, (src) => {
        if (!logoPreview) return;
        const image = document.createElement("img");
        image.className = "logo-preview";
        image.src = src;
        image.alt = "Nouveau logo";
        logoPreview.replaceChildren(image);
      });
    });

    homeButton?.addEventListener("click", () => {
      if (homeResetField) homeResetField.value = "1";
      if (homeFile) homeFile.value = "";
      if (homeChoice) homeChoice.value = "";
      if (homePreview && homeButton.dataset.defaultSrc) {
        homePreview.src = homeButton.dataset.defaultSrc;
      }
    });

    homeFile?.addEventListener("change", () => {
      if (homeResetField) homeResetField.value = "";
      if (homeChoice) homeChoice.value = "";
      previewFile(homeFile, (src) => {
        if (homePreview) homePreview.src = src;
      });
    });

    homeChoice?.addEventListener("change", () => {
      if (homeResetField) homeResetField.value = "";
      if (homeFile) homeFile.value = "";
      if (homeChoice.value && homePreview) {
        homePreview.src = homeChoice.value;
      }
    });

    instagramBannerButton?.addEventListener("click", () => {
      if (instagramBannerResetField) instagramBannerResetField.value = "1";
      if (instagramBannerFile) instagramBannerFile.value = "";
      if (instagramBannerChoice) instagramBannerChoice.value = "";
      if (instagramBannerPreview && instagramBannerButton.dataset.defaultSrc) {
        instagramBannerPreview.src = instagramBannerButton.dataset.defaultSrc;
      }
    });

    instagramBannerFile?.addEventListener("change", () => {
      if (instagramBannerResetField) instagramBannerResetField.value = "";
      if (instagramBannerChoice) instagramBannerChoice.value = "";
      previewFile(instagramBannerFile, (src) => {
        if (instagramBannerPreview) instagramBannerPreview.src = src;
      });
    });

    instagramBannerChoice?.addEventListener("change", () => {
      if (instagramBannerResetField) instagramBannerResetField.value = "";
      if (instagramBannerFile) instagramBannerFile.value = "";
      if (instagramBannerChoice.value && instagramBannerPreview) {
        instagramBannerPreview.src = instagramBannerChoice.value;
      }
    });
  };

  const initChristmasCutTemplate = () => {
    const template = document.querySelector("[data-christmas-cut-template]");
    if (!template) return;

    const image = template.querySelector("[data-christmas-cut-image]");
    const grid = template.querySelector("[data-christmas-cut-grid]");
    const layoutSelect = document.querySelector("[data-christmas-layout-select]");
    const imageChoice = template.querySelector("[data-christmas-image-choice]");
    const imageFile = template.querySelector("[data-christmas-image-file]");
    const toggle = template.querySelector("[data-christmas-cut-toggle]");
    const download = template.querySelector("[data-christmas-cut-download]");
    const cells = Array.from(template.querySelectorAll("[data-cut-position]"));
    const verticalPath = template.querySelector("[data-puzzle-vertical]");
    const horizontalPath = template.querySelector("[data-puzzle-horizontal]");
    const year = Number.parseInt(template.dataset.christmasYear || "0", 10);
    let layouts = {};

    try {
      layouts = JSON.parse(template.dataset.cutLayouts || "{}");
    } catch (_error) {
      layouts = {};
    }

    const puzzlePathData = (variant) => {
      const seed = year + variant * 17;
      const vertical = [];
      const horizontal = [];
      for (let column = 1; column <= 5; column += 1) {
        const x = column * 100;
        for (let row = 1; row <= 4; row += 1) {
          const y = (row - 1) * 100;
          const direction = (seed + row + column) % 2 === 0 ? 1 : -1;
          const bulge = direction * 28;
          vertical.push(`M${x} ${y}V${y + 34}C${x + bulge} ${y + 34} ${x + bulge} ${y + 66} ${x} ${y + 66}V${y + 100}`);
        }
      }
      for (let row = 1; row <= 3; row += 1) {
        const y = row * 100;
        for (let column = 1; column <= 6; column += 1) {
          const x = (column - 1) * 100;
          const direction = (seed + row + column) % 2 === 0 ? 1 : -1;
          const bulge = direction * 28;
          horizontal.push(`M${x} ${y}H${x + 34}C${x + 34} ${y + bulge} ${x + 66} ${y + bulge} ${x + 66} ${y}H${x + 100}`);
        }
      }
      return { vertical: vertical.join(""), horizontal: horizontal.join("") };
    };

    const renderLayout = () => {
      const variant = Number.parseInt(layoutSelect?.value || "1", 10);
      const positions = layouts[String(variant)] || [];
      const dayByPosition = new Map(
        positions.map((position, index) => [Number(position), index + 1])
      );
      cells.forEach((cell) => {
        const position = Number.parseInt(cell.dataset.cutPosition || "0", 10);
        const number = cell.querySelector("[data-cut-number]");
        if (number) number.textContent = String(dayByPosition.get(position) || position);
      });
      const paths = puzzlePathData(variant);
      verticalPath?.setAttribute("d", paths.vertical);
      horizontalPath?.setAttribute("d", paths.horizontal);
    };

    const updateImage = (src) => {
      if (image && src) image.src = src;
    };

    layoutSelect?.addEventListener("change", renderLayout);
    imageChoice?.addEventListener("change", () => {
      if (imageFile) imageFile.value = "";
      if (imageChoice.value === "__none__") {
        updateImage(template.dataset.defaultImage || "");
      } else {
        updateImage(imageChoice.value || template.dataset.currentImage || "");
      }
    });
    imageFile?.addEventListener("change", () => {
      if (imageChoice) imageChoice.value = "";
      previewFile(imageFile, updateImage);
    });
    toggle?.addEventListener("click", () => {
      const guidesAreHidden = template.classList.toggle("is-cut-hidden");
      toggle.textContent = guidesAreHidden ? "Afficher les repères" : "Masquer les repères";
      toggle.setAttribute("aria-pressed", String(guidesAreHidden));
    });
    download?.addEventListener("click", () => {
      if (!image?.complete || !image.naturalWidth || !image.naturalHeight) return;
      const width = 1500;
      const height = 1000;
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      if (!context) return;

      const scale = Math.max(width / image.naturalWidth, height / image.naturalHeight);
      const drawWidth = image.naturalWidth * scale;
      const drawHeight = image.naturalHeight * scale;
      context.drawImage(image, (width - drawWidth) / 2, (height - drawHeight) / 2, drawWidth, drawHeight);
      context.strokeStyle = "rgba(255, 255, 255, 0.96)";
      context.lineWidth = 4;
      context.shadowColor = "rgba(0, 0, 0, 0.75)";
      context.shadowBlur = 5;
      context.strokeRect(2, 2, width - 4, height - 4);
      const variant = Number.parseInt(layoutSelect?.value || "1", 10);
      const seed = year + variant * 17;
      const scaleX = width / 600;
      const scaleY = height / 400;
      for (let column = 1; column <= 5; column += 1) {
        const x = column * 100 * scaleX;
        for (let row = 1; row <= 4; row += 1) {
          const y = (row - 1) * 100 * scaleY;
          const direction = (seed + row + column) % 2 === 0 ? 1 : -1;
          const bulge = direction * 28 * scaleX;
          context.beginPath();
          context.moveTo(x, y);
          context.lineTo(x, y + 34 * scaleY);
          context.bezierCurveTo(x + bulge, y + 34 * scaleY, x + bulge, y + 66 * scaleY, x, y + 66 * scaleY);
          context.lineTo(x, y + 100 * scaleY);
          context.stroke();
        }
      }
      for (let row = 1; row <= 3; row += 1) {
        const y = row * 100 * scaleY;
        for (let column = 1; column <= 6; column += 1) {
          const x = (column - 1) * 100 * scaleX;
          const direction = (seed + row + column) % 2 === 0 ? 1 : -1;
          const bulge = direction * 28 * scaleY;
          context.beginPath();
          context.moveTo(x, y);
          context.lineTo(x + 34 * scaleX, y);
          context.bezierCurveTo(x + 34 * scaleX, y + bulge, x + 66 * scaleX, y + bulge, x + 66 * scaleX, y);
          context.lineTo(x + 100 * scaleX, y);
          context.stroke();
        }
      }
      context.shadowBlur = 0;
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.font = "700 40px Arial, sans-serif";
      cells.forEach((cell, index) => {
        const column = index % 6;
        const row = Math.floor(index / 6);
        const x = (column + 0.5) * (width / 6);
        const y = (row + 0.5) * (height / 4);
        context.fillStyle = "rgba(7, 29, 25, 0.82)";
        context.beginPath();
        context.arc(x, y, 35, 0, Math.PI * 2);
        context.fill();
        context.fillStyle = "#ffffff";
        context.fillText(cell.querySelector("[data-cut-number]")?.textContent || "", x, y + 1);
      });
      canvas.toBlob((blob) => {
        if (!blob) return;
        const link = document.createElement("a");
        const url = URL.createObjectURL(blob);
        link.href = url;
        link.download = `gabarit-calendrier-noel-${year || "edition"}.png`;
        link.click();
        URL.revokeObjectURL(url);
      }, "image/png");
    });

    renderLayout();
  };

  const initAdminHomeTabs = () => {
    const tabs = Array.from(document.querySelectorAll("[data-admin-home-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-admin-home-panel]"));
    if (!tabs.length || !panels.length) return;

    const activate = (key) => {
      tabs.forEach((tab) => {
        const isActive = tab.dataset.adminHomeTab === key;
        tab.classList.toggle("is-active", isActive);
        tab.setAttribute("aria-selected", String(isActive));
      });
      panels.forEach((panel) => {
        panel.classList.toggle("is-active", panel.dataset.adminHomePanel === key);
      });
    };

    tabs.forEach((tab) => {
      tab.setAttribute("role", "tab");
      tab.addEventListener("click", () => activate(tab.dataset.adminHomeTab));
    });
    panels.forEach((panel) => panel.setAttribute("role", "tabpanel"));
    activate(tabs.find((tab) => tab.classList.contains("is-active"))?.dataset.adminHomeTab || tabs[0].dataset.adminHomeTab);
  };

  const initMobileMenu = () => {
    const button = document.querySelector("[data-mobile-menu-toggle]");
    const nav = document.querySelector("[data-main-nav]");
    if (!button || !nav) return;

    const close = () => {
      button.classList.remove("is-open");
      button.setAttribute("aria-expanded", "false");
      nav.classList.remove("is-open");
    };

    button.addEventListener("click", () => {
      const isOpen = !button.classList.contains("is-open");
      button.classList.toggle("is-open", isOpen);
      button.setAttribute("aria-expanded", String(isOpen));
      nav.classList.toggle("is-open", isOpen);
    });

    nav.querySelectorAll("a").forEach((link) => link.addEventListener("click", close));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    });
  };

  const initEventModals = () => {
    const triggers = Array.from(document.querySelectorAll("[data-event-modal-open]"));
    const modals = new Map(Array.from(document.querySelectorAll("[data-event-modal]")).map((modal) => [modal.id, modal]));
    if (!triggers.length || !modals.size) return;

    let activeModal = null;
    let previousFocus = null;

    const focusableSelector = [
      "button:not([disabled])",
      "a[href]",
      "input:not([disabled])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "[tabindex]:not([tabindex='-1'])",
    ].join(",");

    const openModal = (modal, trigger) => {
      if (!modal) return;
      previousFocus = trigger || document.activeElement;
      activeModal = modal;
      modal.hidden = false;
      document.body.classList.add("modal-open");
      requestAnimationFrame(() => {
        modal.classList.add("is-open");
        modal.querySelector(".event-modal-panel")?.focus();
      });
    };

    const closeModal = () => {
      if (!activeModal) return;
      const modal = activeModal;
      activeModal = null;
      modal.classList.remove("is-open");
      document.body.classList.remove("modal-open");
      window.setTimeout(() => {
        if (!modal.classList.contains("is-open")) {
          modal.hidden = true;
        }
      }, 160);
      previousFocus?.focus?.();
      previousFocus = null;
    };

    triggers.forEach((trigger) => {
      const modal = modals.get(trigger.dataset.eventModalOpen || "");
      if (!modal) return;
      trigger.addEventListener("click", () => openModal(modal, trigger));
      trigger.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        openModal(modal, trigger);
      });
    });

    modals.forEach((modal) => {
      modal.querySelectorAll("[data-event-modal-close]").forEach((button) => {
        button.addEventListener("click", closeModal);
      });
    });

    document.addEventListener("keydown", (event) => {
      if (!activeModal) return;
      if (event.key === "Escape") {
        closeModal();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(activeModal.querySelectorAll(focusableSelector)).filter((element) => element.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
  };

  const initChristmasModals = () => {
    const triggers = Array.from(document.querySelectorAll("[data-christmas-day-open]"));
    const modals = new Map(
      Array.from(document.querySelectorAll("[data-christmas-day-modal]")).map((modal) => [modal.id, modal])
    );
    if (!triggers.length || !modals.size) return;

    const calendar = document.querySelector("[data-christmas-calendar]");
    const calendarYear = calendar?.dataset.christmasYear || "";
    const isPreview = calendar?.dataset.christmasPreview === "1";
    const consentStorageKey = "vertTigeConsent";
    const progressCookieName = "vert_tige_noel_progress";
    const progressStatus = document.querySelector("[data-christmas-progress-status]");
    const progressCount = document.querySelector("[data-christmas-discovered-count]");
    const completionModal = document.querySelector("[data-christmas-completion-modal]");
    const completionButton = document.querySelector("[data-christmas-completion-open]");
    const completionEligible = calendar?.dataset.christmasCompletionEligible === "1";
    const completionRequired = Number.parseInt(calendar?.dataset.christmasCompletionRequired || "24", 10);
    let pendingDiscovery = null;
    let pendingCompletion = false;
    let activeModal = null;
    let previousFocus = null;
    const focusableSelector = [
      "button:not([disabled])",
      "a[href]",
      "input:not([disabled])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "[tabindex]:not([tabindex='-1'])",
    ].join(",");

    const readConsent = () => {
      try {
        const consent = JSON.parse(localStorage.getItem(consentStorageKey) || "null");
        if (consent?.version !== 2) return null;
        if (consent?.accepted === true) return true;
        if (consent?.accepted === false) return false;
      } catch (_error) {
        return null;
      }
      return null;
    };

    const readProgress = () => {
      const prefix = `${progressCookieName}=`;
      const raw = document.cookie
        .split(";")
        .map((part) => part.trim())
        .find((part) => part.startsWith(prefix));
      if (!raw) return {};
      try {
        const value = JSON.parse(decodeURIComponent(raw.slice(prefix.length)));
        return value && typeof value === "object" ? value : {};
      } catch (_error) {
        return {};
      }
    };

    const writeProgress = (progress) => {
      let cookie = `${progressCookieName}=${encodeURIComponent(JSON.stringify(progress))}; Max-Age=157680000; Path=/; SameSite=Lax`;
      if (window.location.protocol === "https:") cookie += "; Secure";
      document.cookie = cookie;
    };

    const clearProgress = () => {
      document.cookie = `${progressCookieName}=; Max-Age=0; Path=/; SameSite=Lax`;
    };

    const updateProgressStatus = (consent = readConsent()) => {
      if (!progressStatus || isPreview) return;
      if (consent === true) {
        progressStatus.textContent = "Sauvegarde activée sur cet appareil.";
      } else if (consent === false) {
        progressStatus.textContent = "Sauvegarde refusée : les cases restent consultables, mais l’avancement n’est pas mémorisé.";
      } else {
        progressStatus.textContent = "Autorisation à choisir dans la gestion des cookies.";
      }
    };

    const updateProgressCount = () => {
      if (!progressCount) return;
      progressCount.textContent = String(
        triggers.filter((trigger) => trigger.classList.contains("is-discovered")).length
      );
    };

    const completionIsReached = () =>
      completionEligible &&
      Boolean(completionModal) &&
      triggers.filter((trigger) => trigger.classList.contains("is-discovered")).length >= completionRequired;

    const refreshCompletionButton = () => {
      if (completionButton) completionButton.hidden = !completionIsReached();
    };

    const markDiscovered = (trigger) => {
      if (!trigger) return;
      trigger.disabled = false;
      trigger.classList.remove("is-covered", "is-locked", "is-past");
      trigger.classList.add("is-open", "is-discovered");
      if (trigger.dataset.christmasOpenLabel) {
        trigger.setAttribute("aria-label", trigger.dataset.christmasOpenLabel);
      }
      const label = trigger.querySelector("[data-christmas-day-label]");
      if (label) label.textContent = "Revoir";
      updateProgressCount();
      refreshCompletionButton();
    };

    const saveDiscoveredDay = (trigger) => {
      if (isPreview || readConsent() !== true || !calendarYear) return;
      const dayNumber = Number.parseInt(trigger?.dataset.christmasDay || "", 10);
      if (!Number.isInteger(dayNumber)) return;
      const progress = readProgress();
      const days = new Set(Array.isArray(progress[calendarYear]) ? progress[calendarYear] : []);
      days.add(dayNumber);
      progress[calendarYear] = Array.from(days).sort((left, right) => left - right);
      writeProgress(progress);
    };

    const closeModal = () => {
      if (!activeModal) return;
      const modal = activeModal;
      const returnFocus = previousFocus;
      const shouldOpenCompletion = pendingCompletion && completionModal && modal !== completionModal;
      activeModal = null;
      modal.classList.remove("is-open");
      document.body.classList.remove("modal-open");
      window.setTimeout(() => {
        if (!modal.classList.contains("is-open")) modal.hidden = true;
        if (shouldOpenCompletion) {
          pendingCompletion = false;
          openModal(completionModal, returnFocus);
        }
      }, 180);
      if (!shouldOpenCompletion) returnFocus?.focus?.();
      previousFocus = null;
    };

    const openModal = (modal, trigger) => {
      if (!modal) return;
      previousFocus = trigger || document.activeElement;
      activeModal = modal;
      modal.hidden = false;
      document.body.classList.add("modal-open");
      requestAnimationFrame(() => {
        modal.classList.add("is-open");
        modal.querySelector(".christmas-day-panel")?.focus();
      });
    };

    const discoverAndOpen = (trigger, modal, persist) => {
      markDiscovered(trigger);
      if (persist) saveDiscoveredDay(trigger);
      pendingCompletion = completionIsReached();
      openModal(modal, trigger);
    };

    if (!isPreview && readConsent() === true && calendarYear) {
      const savedDays = new Set(readProgress()[calendarYear] || []);
      triggers.forEach((trigger) => {
        if (savedDays.has(Number.parseInt(trigger.dataset.christmasDay || "", 10))) {
          markDiscovered(trigger);
        }
      });
    }
    updateProgressStatus();
    updateProgressCount();
    refreshCompletionButton();

    triggers.forEach((trigger) => {
      const modal = modals.get(trigger.dataset.christmasDayOpen || "");
      if (!modal) return;
      trigger.addEventListener("click", () => {
        if (isPreview) {
          discoverAndOpen(trigger, modal, false);
          return;
        }
        const consent = readConsent();
        if (consent === null) {
          pendingDiscovery = { trigger, modal };
          const banner = document.querySelector("[data-cookie-banner]");
          if (banner) banner.hidden = false;
          banner?.querySelector("[data-cookie-accept]")?.focus();
          return;
        }
        discoverAndOpen(trigger, modal, consent === true);
      });
    });

    document.addEventListener("vertTigeConsentChanged", (event) => {
      const accepted = event.detail?.accepted === true;
      if (!accepted) clearProgress();
      updateProgressStatus(accepted);
      if (pendingDiscovery) {
        const { trigger, modal } = pendingDiscovery;
        pendingDiscovery = null;
        discoverAndOpen(trigger, modal, accepted);
      }
    });

    modals.forEach((modal) => {
      modal.querySelectorAll("[data-christmas-day-close]").forEach((button) => {
        button.addEventListener("click", closeModal);
      });
    });
    completionButton?.addEventListener("click", () => openModal(completionModal, completionButton));
    completionModal?.querySelectorAll("[data-christmas-completion-close]").forEach((button) => {
      button.addEventListener("click", closeModal);
    });
    document.addEventListener("keydown", (event) => {
      if (!activeModal) return;
      if (event.key === "Escape") {
        closeModal();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(activeModal.querySelectorAll(focusableSelector)).filter(
        (element) => element.offsetParent !== null
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
  };

  const initFooterReveal = () => {
    const footer = document.querySelector(".footer-reveal");
    if (!footer) return;
    const startsVisible = footer.getBoundingClientRect().top < window.innerHeight;
    if (startsVisible) {
      footer.classList.add("is-visible");
      return;
    }
    document.body.classList.add("footer-reveal-watch");
    if (!("IntersectionObserver" in window)) {
      footer.classList.add("is-visible");
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          footer.classList.toggle("is-visible", entry.isIntersecting);
        });
      },
      { threshold: 0.18 }
    );
    observer.observe(footer);
  };

  document.querySelectorAll("[data-article-editor]").forEach(initEditor);
  initHomeImageDefaults();
  initChristmasCutTemplate();
  initRichTextEditor();
  initAdminHomeTabs();
  initMobileMenu();
  initEventModals();
  initChristmasModals();
  initFooterReveal();
})();
