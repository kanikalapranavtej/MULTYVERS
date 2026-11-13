document.addEventListener("DOMContentLoaded", () => {

    const loadingMessage = document.getElementById("loadingMessage");
    const errorMessage = document.getElementById("errorMessage");

    const refreshButton = document.getElementById("refreshButton");
    const exportButton = document.getElementById("exportButton");

    const eventTableBody = document.getElementById("eventTableBody");

    let charts = {};


    // ==========================================
    // HELPER FUNCTIONS
    // ==========================================

    function setNumber(id, value) {

        document.getElementById(id).textContent =
            Number(value || 0).toLocaleString("en-IN");

    }


    function showError(message) {

        errorMessage.textContent = message;
        errorMessage.classList.remove("hidden");

    }


    function hideError() {

        errorMessage.classList.add("hidden");

    }


    function destroyCharts() {

        Object.values(charts).forEach(chart => {

            if (chart) {
                chart.destroy();
            }

        });

        charts = {};

    }


    function createChart(id, config) {

        const canvas = document.getElementById(id);

        if (!canvas || typeof Chart === "undefined") {
            return;
        }

        charts[id] = new Chart(canvas, config);

    }


    function statusClass(status) {

        const allowed = [
            "approved",
            "pending",
            "rejected",
            "cancelled",
            "draft"
        ];

        return allowed.includes(status)
            ? `status-${status}`
            : "";

    }


    // ==========================================
    // LOAD ANALYTICS
    // ==========================================

    async function loadAnalytics() {

        loadingMessage.classList.remove("hidden");
        loadingMessage.textContent = "Loading analytics...";

        hideError();

        refreshButton.disabled = true;
        exportButton.disabled = true;

        try {

            const response = await fetch("/api/analytics/overview");

            const data = await response.json();

            if (!response.ok) {

                throw new Error(
                    data.error || "Unable to load analytics."
                );

            }

            const stats = data.statistics;

            // KPI CARDS

            setNumber("totalEvents", stats.total_events);
            setNumber("approvedEvents", stats.approved_events);
            setNumber("pendingEvents", stats.pending_events);

            setNumber(
                "totalRegistrations",
                stats.confirmed_registrations
            );

            setNumber(
                "totalAttendance",
                stats.total_attendance
            );

            document.getElementById("attendanceRate").textContent =
                `${Number(stats.attendance_percentage || 0).toFixed(2)}%`;


            // CHARTS

            destroyCharts();

            createStatusChart(stats);

            createCategoryChart(data.category_performance || []);

            createRegistrationChart(data.event_performance || []);

            createAttendanceChart(data.event_performance || []);


            // TABLE

            renderEventTable(data.event_performance || []);

            loadingMessage.classList.add("hidden");

            exportButton.disabled = false;

        } catch (error) {

            loadingMessage.classList.add("hidden");

            showError(error.message);

            eventTableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="empty-state">
                        Unable to load analytics.
                    </td>
                </tr>
            `;

        } finally {

            refreshButton.disabled = false;

        }

    }


    // ==========================================
    // EVENT STATUS CHART
    // ==========================================

    function createStatusChart(stats) {

        createChart("eventStatusChart", {

            type: "doughnut",

            data: {

                labels: [
                    "Approved",
                    "Pending",
                    "Rejected",
                    "Cancelled"
                ],

                datasets: [{

                    data: [
                        stats.approved_events,
                        stats.pending_events,
                        stats.rejected_events,
                        stats.cancelled_events
                    ],

                    backgroundColor: [
                        "#54d6a0",
                        "#f6ad62",
                        "#ff7777",
                        "#7c79a3"
                    ],

                    borderWidth: 0

                }]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                plugins: {

                    legend: {

                        position: "bottom",

                        labels: {
                            color: "#c7c1df",
                            padding: 18
                        }

                    }

                }

            }

        });

    }


    // ==========================================
    // CATEGORY CHART
    // ==========================================

    function createCategoryChart(categories) {

        createChart("categoryChart", {

            type: "bar",

            data: {

                labels: categories.map(
                    item => item.category_name
                ),

                datasets: [{

                    label: "Confirmed Registrations",

                    data: categories.map(
                        item => item.confirmed_registrations
                    ),

                    backgroundColor: "#9b7bff",

                    borderRadius: 6

                }]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                indexAxis: "y",

                plugins: {
                    legend: { display: false }
                },

                scales: {

                    x: {
                        beginAtZero: true,
                        ticks: { color: "#9691b0" },
                        grid: { color: "#2b2843" }
                    },

                    y: {
                        ticks: { color: "#c7c1df" },
                        grid: { display: false }
                    }

                }

            }

        });

    }


    // ==========================================
    // REGISTRATION CHART
    // ==========================================

    function createRegistrationChart(events) {

        const sorted = [...events]
            .sort((a, b) =>
                b.confirmed_registrations -
                a.confirmed_registrations
            )
            .slice(0, 10);

        createChart("registrationChart", {

            type: "bar",

            data: {

                labels: sorted.map(item => item.title),

                datasets: [{

                    label: "Registrations",

                    data: sorted.map(
                        item => item.confirmed_registrations
                    ),

                    backgroundColor: "#55d6e8",

                    borderRadius: 6

                }]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                plugins: {

                    legend: {

                        labels: {
                            color: "#c7c1df"
                        }

                    }

                },

                scales: {

                    x: {
                        ticks: { color: "#9691b0" },
                        grid: { display: false }
                    },

                    y: {
                        beginAtZero: true,
                        ticks: { color: "#9691b0" },
                        grid: { color: "#2b2843" }
                    }

                }

            }

        });

    }


    // ==========================================
    // ATTENDANCE CHART
    // ==========================================

    function createAttendanceChart(events) {

        const sorted = [...events]
            .sort((a, b) =>
                b.attendance_percentage -
                a.attendance_percentage
            )
            .slice(0, 8);

        createChart("attendanceChart", {

            type: "bar",

            data: {

                labels: sorted.map(item => item.title),

                datasets: [{

                    label: "Attendance Percentage",

                    data: sorted.map(
                        item => item.attendance_percentage
                    ),

                    backgroundColor: "#54d6a0",

                    borderRadius: 6

                }]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                plugins: {
                    legend: { display: false }
                },

                scales: {

                    x: {
                        ticks: { color: "#9691b0" },
                        grid: { display: false }
                    },

                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            color: "#9691b0",
                            callback: value => `${value}%`
                        },
                        grid: { color: "#2b2843" }
                    }

                }

            }

        });

    }


    // ==========================================
    // EVENT PERFORMANCE TABLE
    // ==========================================

    function renderEventTable(events) {

        eventTableBody.innerHTML = "";

        document.getElementById("eventCount").textContent =
            `${events.length} events`;

        if (!events.length) {

            eventTableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="empty-state">
                        No event analytics available.
                    </td>
                </tr>
            `;

            return;

        }

        events.forEach(event => {

            const row = document.createElement("tr");

            const values = [
                event.title,
                event.status,
                event.capacity,
                event.confirmed_registrations,
                event.attendance_count,
                `${Number(event.attendance_percentage).toFixed(2)}%`,
                `${Number(event.registration_percentage).toFixed(2)}%`
            ];

            values.forEach((value, index) => {

                const cell = document.createElement("td");

                if (index === 0) {

                    cell.className = "event-title";

                }

                if (index === 1) {

                    const badge = document.createElement("span");

                    badge.className =
                        `status-badge ${statusClass(event.status)}`;

                    badge.textContent = value;

                    cell.appendChild(badge);

                } else {

                    cell.textContent = value;

                }

                if (index === 5) {
                    cell.classList.add("percentage-cell");
                }

                row.appendChild(cell);

            });

            eventTableBody.appendChild(row);

        });

    }


    // ==========================================
    // CSV EXPORT
    // ==========================================

    exportButton.addEventListener("click", () => {

        window.location.href = "/api/analytics/export";

    });


    // ==========================================
    // REFRESH
    // ==========================================

    refreshButton.addEventListener("click", loadAnalytics);


    // INITIAL LOAD

    loadAnalytics();

});