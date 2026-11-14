(function () {
  "use strict";
  const token = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const message = document.getElementById("reviewMessage");

  document.querySelectorAll("[data-review]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.review;
      const eventId = button.dataset.eventId;
      const verb = action === "approve" ? "approve" : "reject";
      if (!window.confirm(`Are you sure you want to ${verb} this event?`)) return;
      button.disabled = true;
      try {
        const response = await fetch(`/api/events/${eventId}/${action}`, {
          method: "PATCH",
          credentials: "same-origin",
          headers: { "X-CSRFToken": token }
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || `Unable to ${verb} event.`);
        message.textContent = data.message || `Event ${verb}d.`;
        message.className = "portal-success";
        window.location.reload();
      } catch (error) {
        message.textContent = error.message;
        message.className = "portal-error";
        button.disabled = false;
      }
    });
  });
})();
