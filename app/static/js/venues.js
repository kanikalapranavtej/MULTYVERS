document.addEventListener("DOMContentLoaded", () => {
    const API_URL = "/api/venues/";

    const tableBody = document.getElementById("venueTableBody");
    const searchInput = document.getElementById("venueSearch");
    const dialog = document.getElementById("venueDialog");
    const form = document.getElementById("venueForm");

    const messageBox = document.getElementById("venueMessage");
    const errorBox = document.getElementById("venueFormError");

    const availabilityForm = document.getElementById("availabilityForm");
    const availabilityVenue = document.getElementById("availabilityVenue");
    const availabilityStart = document.getElementById("availabilityStart");
    const availabilityEnd = document.getElementById("availabilityEnd");
    const availabilityResult = document.getElementById("availabilityResult");

    const csrfToken =
        document.querySelector('input[name="csrf_token"]')?.value ||
        document.querySelector('meta[name="csrf-token"]')?.content ||
        "";

    let venues = [];
    let editingVenueId = null;

    // ----------------------------------
    // API REQUEST HANDLER
    // ----------------------------------

    async function apiRequest(url, options = {}) {
        const headers = {
            ...(options.body ? {
                "Content-Type": "application/json"
            } : {}),
            ...(options.headers || {})
        };

        if (options.method && options.method !== "GET") {
            headers["X-CSRFToken"] = csrfToken;
        }

        const response = await fetch(url, {
            ...options,
            headers,
            credentials: "same-origin"
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(
                data.error || `Request failed: ${response.status}`
            );
        }

        return data;
    }

    // ----------------------------------
    // NOTIFICATIONS
    // ----------------------------------

    function showMessage(message, isError = false) {
        messageBox.textContent = message;

        messageBox.className = isError
            ? "venue-message error"
            : "venue-message success";

        messageBox.style.display = "block";

        clearTimeout(showMessage.timer);

        showMessage.timer = setTimeout(() => {
            messageBox.style.display = "none";
        }, 4000);
    }

    // ----------------------------------
    // LOAD VENUES
    // ----------------------------------

    async function loadVenues() {
        tableBody.innerHTML = `
            <tr>
                <td colspan="4">Loading venues...</td>
            </tr>
        `;

        try {
            const data = await apiRequest(API_URL);

            venues = data.venues || [];

            renderVenues();
            populateAvailabilityVenues();

        } catch (error) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="4">Unable to load venues.</td>
                </tr>
            `;

            showMessage(error.message, true);
        }
    }

    // ----------------------------------
    // POPULATE AVAILABILITY VENUE SELECT
    // ----------------------------------

    function populateAvailabilityVenues() {
        availabilityVenue.replaceChildren();

        const defaultOption = document.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = "Choose a venue";

        availabilityVenue.appendChild(defaultOption);

        venues.forEach(venue => {
            const option = document.createElement("option");

            option.value = venue.venue_id;
            option.textContent =
                `${venue.venue_name} (${venue.location})`;

            availabilityVenue.appendChild(option);
        });
    }

    // ----------------------------------
    // RENDER VENUES
    // ----------------------------------

    function renderVenues() {
        const searchTerm = searchInput.value.trim().toLowerCase();

        const filteredVenues = venues.filter(venue => {
            const searchableText =
                `${venue.venue_name} ${venue.location}`.toLowerCase();

            return searchableText.includes(searchTerm);
        });

        document.getElementById("totalVenues").textContent =
            venues.length;

        document.getElementById("totalCapacity").textContent =
            venues.reduce(
                (total, venue) => total + Number(venue.capacity),
                0
            ).toLocaleString();

        document.getElementById("visibleVenues").textContent =
            filteredVenues.length;

        tableBody.replaceChildren();

        if (filteredVenues.length === 0) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");

            cell.colSpan = 4;
            cell.textContent = venues.length
                ? "No matching venues found."
                : "No venues have been added yet.";

            row.appendChild(cell);
            tableBody.appendChild(row);
            return;
        }

        filteredVenues.forEach(venue => {
            const row = document.createElement("tr");

            const nameCell = document.createElement("td");
            const name = document.createElement("strong");

            name.textContent = venue.venue_name;
            nameCell.appendChild(name);

            const locationCell = document.createElement("td");
            locationCell.textContent = venue.location;

            const capacityCell = document.createElement("td");
            capacityCell.textContent =
                Number(venue.capacity).toLocaleString();

            const actionCell = document.createElement("td");

            const editButton = document.createElement("button");
            editButton.textContent = "Edit";
            editButton.className = "action";

            editButton.addEventListener("click", () => {
                openEditDialog(venue);
            });

            const deleteButton = document.createElement("button");
            deleteButton.textContent = "Delete";
            deleteButton.className = "action delete";

            deleteButton.addEventListener("click", () => {
                deleteVenue(venue);
            });

            actionCell.append(editButton, deleteButton);

            row.append(
                nameCell,
                locationCell,
                capacityCell,
                actionCell
            );

            tableBody.appendChild(row);
        });
    }

    // ----------------------------------
    // ADD VENUE
    // ----------------------------------

    function openAddDialog() {
        editingVenueId = null;
        form.reset();
        errorBox.textContent = "";

        document.getElementById("venueDialogTitle").textContent =
            "Add venue";

        dialog.showModal();
    }

    // ----------------------------------
    // EDIT VENUE
    // ----------------------------------

    function openEditDialog(venue) {
        editingVenueId = venue.venue_id;

        form.reset();

        form.elements.venue_name.value = venue.venue_name;
        form.elements.location.value = venue.location;
        form.elements.capacity.value = venue.capacity;

        errorBox.textContent = "";

        document.getElementById("venueDialogTitle").textContent =
            "Edit venue";

        dialog.showModal();
    }

    // ----------------------------------
    // SAVE VENUE
    // ----------------------------------

    form.addEventListener("submit", async event => {
        event.preventDefault();

        errorBox.textContent = "";

        const payload = {
            venue_name: form.elements.venue_name.value.trim(),
            location: form.elements.location.value.trim(),
            capacity: Number(form.elements.capacity.value)
        };

        if (
            !payload.venue_name ||
            !payload.location ||
            !Number.isInteger(payload.capacity) ||
            payload.capacity <= 0
        ) {
            errorBox.textContent =
                "Enter valid venue details and a positive whole-number capacity.";
            return;
        }

        const isEditing = editingVenueId !== null;

        const url = isEditing
            ? `${API_URL}${editingVenueId}`
            : API_URL;

        try {
            await apiRequest(url, {
                method: isEditing ? "PUT" : "POST",
                body: JSON.stringify(payload)
            });

            dialog.close();

            showMessage(
                isEditing
                    ? "Venue updated successfully."
                    : "Venue created successfully."
            );

            await loadVenues();

        } catch (error) {
            errorBox.textContent = error.message;
        }
    });

    // ----------------------------------
    // DELETE VENUE
    // ----------------------------------

    async function deleteVenue(venue) {
        const confirmed = window.confirm(
            `Are you sure you want to delete "${venue.venue_name}"?`
        );

        if (!confirmed) return;

        try {
            await apiRequest(
                `${API_URL}${venue.venue_id}`,
                { method: "DELETE" }
            );

            showMessage("Venue deleted successfully.");
            await loadVenues();

        } catch (error) {
            showMessage(error.message, true);
        }
    }

    // ----------------------------------
    // CHECK VENUE AVAILABILITY
    // ----------------------------------

    availabilityForm.addEventListener("submit", async event => {
        event.preventDefault();

        availabilityResult.textContent = "Checking availability...";

        const venueId = availabilityVenue.value;
        const start = availabilityStart.value;
        const end = availabilityEnd.value;

        if (!venueId || !start || !end) {
            availabilityResult.textContent =
                "Please complete all availability fields.";
            return;
        }

        if (new Date(end) <= new Date(start)) {
            availabilityResult.textContent =
                "End time must be later than start time.";
            return;
        }

        const params = new URLSearchParams({
            venue_id: venueId,
            starts_at: start,
            ends_at: end
        });

        try {
            const data = await apiRequest(
                `${API_URL}availability?${params.toString()}`
            );

            availabilityResult.replaceChildren();

            const heading = document.createElement("h3");

            heading.textContent = data.available
                ? "Venue is available"
                : "Venue is not available";

            heading.className = data.available
                ? "availability-success"
                : "availability-error";

            availabilityResult.appendChild(heading);

            if (data.available) {
                const message = document.createElement("p");
                message.textContent =
                    `${data.venue.venue_name} has no conflicting bookings during this time.`;

                availabilityResult.appendChild(message);
            } else {
                const count = document.createElement("p");
                count.textContent =
                    `${data.conflict_count} conflicting booking(s) found.`;

                availabilityResult.appendChild(count);

                data.conflicts.forEach(conflict => {
                    const item = document.createElement("div");
                    item.className = "conflict-item";

                    const title = document.createElement("strong");
                    title.textContent = conflict.title;

                    const details = document.createElement("p");
                    details.textContent =
                        `${conflict.starts_at} – ${conflict.ends_at} (${conflict.status})`;

                    item.append(title, details);
                    availabilityResult.appendChild(item);
                });
            }

        } catch (error) {
            availabilityResult.textContent = error.message;
        }
    });

    // ----------------------------------
    // EVENT LISTENERS
    // ----------------------------------

    document.getElementById("addVenueBtn")
        .addEventListener("click", openAddDialog);

    document.getElementById("cancelVenue")
        .addEventListener("click", () => dialog.close());

    searchInput.addEventListener("input", renderVenues);

    // ----------------------------------
    // INITIALIZATION
    // ----------------------------------

    loadVenues();
});