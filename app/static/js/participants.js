
document.addEventListener("DOMContentLoaded", () => {

    const eventSelect = document.getElementById("eventSelect");
    const statusFilter = document.getElementById("statusFilter");
    const searchInput = document.getElementById("participantSearch");

    const tableBody = document.getElementById("participantTableBody");
    const messageBox = document.getElementById("participantMessage");

    const exportButton = document.getElementById("exportParticipants");
    const previousButton = document.getElementById("previousPage");
    const nextButton = document.getElementById("nextPage");

    const totalParticipants = document.getElementById("totalParticipants");
    const presentParticipants = document.getElementById("presentParticipants");
    const absentParticipants = document.getElementById("absentParticipants");
    const currentPage = document.getElementById("currentPage");

    const participantHeading = document.getElementById("participantHeading");
    const participantCount = document.getElementById("participantCount");
    const paginationInfo = document.getElementById("paginationInfo");

    const csrfToken =
        document.querySelector('input[name="csrf_token"]')?.value || "";

    let selectedEventId = null;
    let page = 1;
    const perPage = 20;
    let totalPages = 0;
    let searchTimer = null;

    function showMessage(message, type = "") {
        messageBox.textContent = message;
        messageBox.className = `participant-message ${type}`;
    }

    function setLoading() {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5">Loading participants...</td>
            </tr>
        `;
    }

    function formatDate(value) {
        if (!value) return "—";

        const date = new Date(
            value.includes("T") ? value : value.replace(" ", "T")
        );

        if (Number.isNaN(date.getTime())) return value;

        return date.toLocaleString();
    }

    function createCell(value, className = "") {
        const cell = document.createElement("td");
        cell.textContent = value ?? "—";

        if (className) {
            cell.className = className;
        }

        return cell;
    }

    function createStatus(status) {
        const badge = document.createElement("span");

        badge.className = `participant-status ${status}`;
        badge.textContent = status;

        return badge;
    }

    function renderParticipants(participants) {
        tableBody.replaceChildren();

        if (!participants.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");

            cell.colSpan = 5;
            cell.textContent = "No participants found.";

            row.appendChild(cell);
            tableBody.appendChild(row);
            return;
        }

        let present = 0;
        let absent = 0;

        participants.forEach(participant => {
            const row = document.createElement("tr");

            const name = createCell(participant.name, "participant-name");
            const email = createCell(participant.email, "participant-email");

            const registrationCell = document.createElement("td");
            registrationCell.appendChild(
                createStatus(participant.registration_status)
            );

            const attendanceCell = document.createElement("td");
            attendanceCell.appendChild(
                createStatus(participant.attendance_status)
            );

            if (participant.attendance_status === "present") {
                present++;
            } else {
                absent++;
            }

            const registered = createCell(
                formatDate(participant.registered_at)
            );

            row.append(
                name,
                email,
                registrationCell,
                attendanceCell,
                registered
            );

            tableBody.appendChild(row);
        });

        presentParticipants.textContent = present;
        absentParticipants.textContent = absent;
    }

    function updatePagination(pagination) {
        page = pagination.page;
        totalPages = pagination.total_pages;

        totalParticipants.textContent =
            pagination.total.toLocaleString();

        currentPage.textContent =
            `${page} / ${totalPages}`;

        paginationInfo.textContent =
            `Page ${page} of ${totalPages}`;

        participantCount.textContent =
            `${pagination.total} registration(s)`;

        previousButton.disabled = page <= 1;
        nextButton.disabled =
            totalPages === 0 || page >= totalPages;
    }

    async function loadParticipants() {
        if (!selectedEventId) return;

        setLoading();
        showMessage("Loading participant records...");

        const params = new URLSearchParams({
            page: String(page),
            per_page: String(perPage),
            status: statusFilter.value,
            search: searchInput.value.trim()
        });

        try {
            const response = await fetch(
                `/api/events/${selectedEventId}/participants?${params}`,
                {
                    credentials: "same-origin"
                }
            );

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error || "Unable to load participants."
                );
            }

            participantHeading.textContent =
                data.event_title;

            renderParticipants(data.participants);
            updatePagination(data.pagination);

            showMessage("");

        } catch (error) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5">Unable to load participants.</td>
                </tr>
            `;

            showMessage(error.message, "error");
        }
    }

    eventSelect.addEventListener("change", () => {
        selectedEventId = eventSelect.value || null;

        page = 1;

        searchInput.value = "";
        searchInput.disabled = !selectedEventId;
        statusFilter.disabled = !selectedEventId;
        exportButton.disabled = !selectedEventId;

        if (!selectedEventId) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5">No event selected.</td>
                </tr>
            `;

            totalParticipants.textContent = "0";
            presentParticipants.textContent = "0";
            absentParticipants.textContent = "0";
            currentPage.textContent = "0 / 0";

            participantCount.textContent = "Select an event";
            paginationInfo.textContent = "Page 0 of 0";

            showMessage("Select an event to load its participants.");
            previousButton.disabled = true;
            nextButton.disabled = true;

            return;
        }

        loadParticipants();
    });

    statusFilter.addEventListener("change", () => {
        page = 1;
        loadParticipants();
    });

    searchInput.addEventListener("input", () => {
        clearTimeout(searchTimer);

        searchTimer = setTimeout(() => {
            page = 1;
            loadParticipants();
        }, 300);
    });

    previousButton.addEventListener("click", () => {
        if (page > 1) {
            page--;
            loadParticipants();
        }
    });

    nextButton.addEventListener("click", () => {
        if (page < totalPages) {
            page++;
            loadParticipants();
        }
    });

    exportButton.addEventListener("click", async () => {
        if (!selectedEventId) return;

        const params = new URLSearchParams({
            status: statusFilter.value
        });

        try {
            exportButton.disabled = true;

            const response = await fetch(
                `/api/events/${selectedEventId}/participants/export?${params}`,
                {
                    credentials: "same-origin"
                }
            );

            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(
                    data.error || "CSV export failed."
                );
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);

            const link = document.createElement("a");

            link.href = url;
            link.download = `event_${selectedEventId}_participants.csv`;

            document.body.appendChild(link);
            link.click();
            link.remove();

            URL.revokeObjectURL(url);

            showMessage("CSV exported successfully.", "success");

        } catch (error) {
            showMessage(error.message, "error");

        } finally {
            exportButton.disabled = false;
        }
    });

    statusFilter.disabled = true;
    searchInput.disabled = true;
    exportButton.disabled = true;

});
