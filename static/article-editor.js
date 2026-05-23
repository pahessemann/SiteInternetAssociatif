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

  document.querySelectorAll("[data-article-editor]").forEach(initEditor);
})();
