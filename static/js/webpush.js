(() => {
  const button = document.getElementById("web-push-toggle");
  const status = document.getElementById("web-push-status");
  if (!button || !status) return;

  const setStatus = (message) => {
    status.textContent = message;
  };
  const isIOS =
    /iPhone|iPad|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const isStandalone =
    window.navigator.standalone === true ||
    window.matchMedia("(display-mode: standalone)").matches;

  if (isIOS && !isStandalone) {
    setStatus("On iOS/iPadOS 16.4 or later, add Drover to your Home Screen first.");
    return;
  }

  if (
    !("serviceWorker" in navigator) ||
    !("PushManager" in window) ||
    !("Notification" in window)
  ) {
    setStatus("This browser does not support Web Push notifications.");
    return;
  }

  const configured = button.dataset.enabled === "true";
  const permissionDenied = Notification.permission === "denied";

  function csrfToken() {
    const prefix = "csrftoken=";
    const cookie = document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(prefix));
    return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : "";
  }

  async function postJson(url, data) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error("The notification setting could not be saved.");
  }

  function base64UrlToUint8Array(value) {
    const padding = "=".repeat((4 - (value.length % 4)) % 4);
    const base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = window.atob(base64);
    return Uint8Array.from(raw, (character) => character.charCodeAt(0));
  }

  let registration;
  let currentSubscription = null;

  async function initialize() {
    await navigator.serviceWorker.register(button.dataset.workerUrl, { scope: "/" });
    registration = await navigator.serviceWorker.ready;
    currentSubscription = await registration.pushManager.getSubscription();
    if (currentSubscription) {
      button.dataset.subscribed = "true";
      button.textContent = "Turn off on this device";
      if (configured) {
        try {
          await postJson(button.dataset.registerUrl, currentSubscription.toJSON());
          setStatus("Notifications are on for this device.");
        } catch {
          setStatus(
            "This device has a browser subscription, but Drover could not sync it. Turn it off and enable it again.",
          );
        }
      } else {
        setStatus("Web Push is unavailable here; you can still turn off this device.");
      }
      button.disabled = false;
      return;
    }

    button.dataset.subscribed = "false";
    button.textContent = "Enable notifications";
    if (permissionDenied) {
      setStatus("Notifications are blocked in this browser's site settings.");
      button.disabled = true;
      return;
    }
    if (!configured) {
      setStatus("Browser notifications aren't configured for this Drover installation.");
      button.disabled = true;
      return;
    }
    setStatus("Message notifications are optional and can be turned off on this device.");
    button.disabled = false;
  }

  button.addEventListener("click", async () => {
    button.disabled = true;
    if (button.dataset.subscribed === "true") {
      try {
        let serverRevoked = false;
        const hadSubscription = Boolean(currentSubscription);
        if (currentSubscription) {
          try {
            await postJson(button.dataset.revokeUrl, {
              endpoint: currentSubscription.endpoint,
            });
            serverRevoked = true;
          } catch {
            // The browser-side unsubscribe still disables this device locally.
          }
          await currentSubscription.unsubscribe();
          currentSubscription = null;
        }
        button.dataset.subscribed = "false";
        button.textContent = "Enable notifications";
        setStatus(
          serverRevoked || !hadSubscription
            ? "Notifications are off on this device."
            : "Notifications are off locally; Drover will remove this device after it expires.",
        );
      } catch {
        setStatus("Drover could not turn off notifications on this device. Try again.");
      } finally {
        button.disabled = false;
      }
      return;
    }

    if (!configured) {
      setStatus("Web Push is not configured for this Drover installation.");
      button.disabled = true;
      return;
    }

    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setStatus(
          permission === "denied"
            ? "Notifications are blocked in this browser's site settings."
            : "Notifications remain off until you allow them.",
        );
        button.disabled = permission === "denied";
        return;
      }

      const newSubscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: base64UrlToUint8Array(button.dataset.publicKey),
      });
      try {
        await postJson(button.dataset.registerUrl, newSubscription.toJSON());
      } catch (error) {
        await newSubscription.unsubscribe();
        throw error;
      }

      currentSubscription = newSubscription;
      button.dataset.subscribed = "true";
      button.textContent = "Turn off on this device";
      setStatus("Notifications are on for this device.");
    } catch {
      setStatus("Drover could not update this device's notification setting. Try again.");
    } finally {
      if (Notification.permission !== "denied" && configured) {
        button.disabled = false;
      }
    }
  });

  initialize().catch(() => {
    setStatus("Web Push could not start in this browser.");
    button.disabled = true;
  });
})();
