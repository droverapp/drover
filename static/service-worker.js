self.addEventListener("push", (event) => {
  let payload = {
    title: "New Drover message",
    body: "Open Drover to view the message.",
    url: "/users/dashboard/",
  };

  if (event.data) {
    try {
      payload = { ...payload, ...event.data.json() };
    } catch {
      // Keep the generic user-visible notification for invalid payloads.
    }
  }

  const target = new URL(payload.url || "/users/dashboard/", self.location.origin);
  if (target.origin !== self.location.origin) {
    target.href = "/users/dashboard/";
  }

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: "/static/img/drover_pwa_192.png",
      badge: "/static/img/drover_pwa_192.png",
      data: { url: `${target.pathname}${target.search}${target.hash}` },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(
    event.notification.data?.url || "/users/dashboard/",
    self.location.origin,
  );
  if (target.origin !== self.location.origin) {
    return;
  }

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const window of windows) {
        if (new URL(window.url).origin === self.location.origin && "focus" in window) {
          return window.navigate(target.href).then(() => window.focus());
        }
      }
      return self.clients.openWindow(target.href);
    }),
  );
});
