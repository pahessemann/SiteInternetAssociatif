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
      if (logoPreview) {
        const placeholder = document.createElement("div");
        placeholder.className = "logo-placeholder";
        placeholder.textContent = "VT";
        logoPreview.replaceChildren(placeholder);
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

  document.querySelectorAll("[data-article-editor]").forEach(initEditor);
  initHomeImageDefaults();
  initRichTextEditor();
  initAdminHomeTabs();
})();
