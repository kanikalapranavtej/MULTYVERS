(function () {
  "use strict";

  function csrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || "";
  }

  async function api(url, method, payload) {
    const response = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken()
      },
      body: payload ? JSON.stringify(payload) : undefined
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || data.message || `Request failed (${response.status})`);
    return data;
  }

  const form = document.getElementById("eventForm");

  if (form) {
    const checkButton = document.getElementById("checkVenueAvailability");
    const availabilityMessage = document.getElementById("venueAvailabilityMessage");
    const venueSelect = document.getElementById("eventVenue");
    const combine = (dateId, timeId) => {
      const date = document.getElementById(dateId)?.value || "";
      const time = document.getElementById(timeId)?.value || "";
      return date && time ? `${date}T${time}:00` : "";
    };
    const updateAvailabilitySummary = () => {
      const selected = venueSelect?.selectedOptions?.[0];
      const venueName = selected?.textContent?.trim() || "Choose a venue above";
      const start = combine("starts_date", "starts_time");
      const end = combine("ends_date", "ends_time");
      document.getElementById("availabilityVenueName").textContent = venueName;
      document.getElementById("availabilityStart").textContent = start.replace("T", " ") || "Select start date and time";
      document.getElementById("availabilityEnd").textContent = end.replace("T", " ") || "Select end date and time";
    };
    ["change", "input"].forEach((eventName) => {
      form.addEventListener(eventName, updateAvailabilitySummary);
    });
    updateAvailabilitySummary();

    checkButton?.addEventListener("click", async () => {
      const venueId = venueSelect?.value;
      const startsAt = combine("starts_date", "starts_time");
      const endsAt = combine("ends_date", "ends_time");
      if (!venueId || !startsAt || !endsAt) {
        availabilityMessage.textContent = "Select a venue and both event start/end dates and times first.";
        availabilityMessage.className = "portal-error";
        return;
      }
      if (new Date(endsAt) <= new Date(startsAt)) {
        availabilityMessage.textContent = "Event end must be later than event start.";
        availabilityMessage.className = "portal-error";
        return;
      }
      const params = new URLSearchParams({venue_id: venueId, starts_at: startsAt, ends_at: endsAt});
      if (form.dataset.eventId) params.set("exclude_event_id", form.dataset.eventId);
      checkButton.disabled = true;
      availabilityMessage.textContent = "Checking venue schedule…";
      availabilityMessage.className = "portal-note";
      try {
        const result = await api(`/api/venues/availability?${params.toString()}`, "GET");
        if (result.available) {
          availabilityMessage.textContent = `${result.venue.venue_name} is available for the selected time.`;
          availabilityMessage.className = "is-available";
        } else {
          const names = (result.conflicts || []).map(item => item.title).join(", ");
          availabilityMessage.textContent = `Venue conflict found${names ? ` with: ${names}` : ""}. Choose another time or venue.`;
          availabilityMessage.className = "is-conflict";
        }
      } catch (error) {
        availabilityMessage.textContent = error.message;
        availabilityMessage.className = "is-error";
      } finally {
        checkButton.disabled = false;
      }
    });
  }

  if (form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = document.getElementById("eventFormMessage");
      const values = new FormData(form);
      const payload = Object.fromEntries(values.entries());
      const combineDateTime = (dateId, timeId) => {
        const date = document.getElementById(dateId)?.value || "";
        const time = document.getElementById(timeId)?.value || "";
        return date && time ? `${date}T${time}:00` : "";
      };
      payload.starts_at = combineDateTime("starts_date", "starts_time");
      payload.ends_at = combineDateTime("ends_date", "ends_time");
      payload.registration_deadline = combineDateTime("deadline_date", "deadline_time");
      ["category_id", "venue_id", "capacity"].forEach((key) => payload[key] = Number(payload[key]));
      if (!payload.starts_at || !payload.ends_at || !payload.registration_deadline) {
        message.textContent = "Choose both a date and a time for start, end and registration deadline.";
        message.className = "portal-error";
        return;
      }
      if (new Date(payload.ends_at) <= new Date(payload.starts_at)) {
        message.textContent = "Event end must be later than event start.";
        message.className = "portal-error";
        return;
      }
      if (new Date(payload.registration_deadline) > new Date(payload.starts_at)) {
        message.textContent = "Registration deadline must be before the event starts.";
        message.className = "portal-error";
        return;
      }
      const venueSelect = document.getElementById("eventVenue");
      const selectedVenue = venueSelect?.selectedOptions?.[0];
      const venueCapacity = Number(selectedVenue?.dataset?.capacity || 0);
      if (venueCapacity && payload.capacity > venueCapacity) {
        message.textContent = `Event capacity cannot exceed the selected venue capacity (${venueCapacity}).`;
        message.className = "portal-error";
        return;
      }
      const eventId = form.dataset.eventId;
      const url = eventId ? `/api/events/${eventId}` : "/api/events/";
      const method = eventId ? "PUT" : "POST";
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      message.textContent = "Submitting…";
      try {
        const result = await api(url, method, payload);
        message.textContent = result.message || "Event saved. Awaiting administrator review.";
        message.className = "portal-success";
        window.setTimeout(() => window.location.assign("/organizer/portal"), 900);
      } catch (error) {
        message.textContent = error.message;
        message.className = "portal-error";
        button.disabled = false;
      }
    });
  }

  document.querySelectorAll("[data-cancel-event]").forEach((button) => {
    button.addEventListener("click", async () => {
      const eventId = button.dataset.cancelEvent;
      if (!window.confirm("Cancel this pending event? This action cannot be undone.")) return;
      button.disabled = true;
      const message = document.getElementById("organizerEventMessage");
      try {
        await api(`/api/events/${eventId}/cancel`, "PATCH");
        message.textContent = "Event cancelled.";
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
