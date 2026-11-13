document.addEventListener("DOMContentLoaded", () => {

    const csrfToken = document.querySelector(
        'meta[name="csrf-token"]'
    )?.content;


    // ==========================================
    // ORGANIZER ATTENDANCE
    // ==========================================

    const eventSelect = document.getElementById(
        "attendanceEventSelect"
    );

    if (eventSelect) {

        const generateButton = document.getElementById(
            "generateQrBtn"
        );

        const qrImage = document.getElementById(
            "attendanceQrImage"
        );

        const qrSection = document.getElementById(
            "qrSection"
        );

        const qrMessage = document.getElementById(
            "qrMessage"
        );

        const reportBody = document.getElementById(
            "attendanceTableBody"
        );

        const reportMessage = document.getElementById(
            "reportMessage"
        );

        const exportButton = document.getElementById(
            "exportAttendanceBtn"
        );

        let currentQrUrl = null;


        eventSelect.addEventListener("change", async () => {

            qrSection.classList.add("hidden");

            exportButton.classList.add("disabled");
            exportButton.removeAttribute("href");

            const eventId = eventSelect.value;

            if (!eventId) {
                reportBody.innerHTML = `
                    <tr>
                        <td colspan="4" class="empty-state">
                            Select an event to view attendance.
                        </td>
                    </tr>
                `;
                return;
            }

            await loadAttendance(eventId);
        });


        generateButton.addEventListener("click", async () => {

            const eventId = eventSelect.value;

            if (!eventId) {
                qrMessage.textContent = "Please select an event.";
                return;
            }

            generateButton.disabled = true;
            generateButton.textContent = "Generating...";

            try {

                const response = await fetch(
                    `/api/events/${eventId}/attendance/qr`
                );

                if (!response.ok) {
                    throw new Error(
                        "Unable to generate QR code."
                    );
                }

                const blob = await response.blob();

                if (currentQrUrl) {
                    URL.revokeObjectURL(currentQrUrl);
                }

                currentQrUrl = URL.createObjectURL(blob);

                qrImage.src = currentQrUrl;

                document.getElementById(
                    "downloadQr"
                ).href = currentQrUrl;

                qrSection.classList.remove("hidden");

                qrMessage.textContent =
                    "QR code generated successfully.";

            } catch (error) {

                qrMessage.textContent = error.message;

            } finally {

                generateButton.disabled = false;
                generateButton.textContent = "Generate QR Code";

            }

        });


        async function loadAttendance(eventId) {

            reportMessage.textContent = "Loading attendance...";

            try {

                const response = await fetch(
                    `/api/events/${eventId}/attendance`
                );

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(
                        result.error || "Unable to load attendance."
                    );
                }

                const records = result.attendance || [];

                reportBody.innerHTML = "";

                if (records.length === 0) {

                    reportBody.innerHTML = `
                        <tr>
                            <td colspan="4" class="empty-state">
                                No attendance has been marked yet.
                            </td>
                        </tr>
                    `;

                } else {

                    records.forEach(record => {

                        const row = document.createElement("tr");

                        const name = document.createElement("td");
                        name.textContent = record.name;

                        const email = document.createElement("td");
                        email.textContent = record.email;

                        const markedAt = document.createElement("td");
                        markedAt.textContent = record.marked_at;

                        const method = document.createElement("td");
                        method.textContent = record.method;

                        row.append(name, email, markedAt, method);

                        reportBody.appendChild(row);

                    });

                }

                exportButton.href =
                    `/api/events/${eventId}/attendance/export`;

                exportButton.classList.remove("disabled");

                reportMessage.textContent =
                    `${records.length} attendance record(s) found.`;

            } catch (error) {

                reportMessage.textContent = error.message;

            }

        }

    }


    // ==========================================
    // STUDENT QR SCANNER
    // ==========================================

    const readerElement = document.getElementById("qr-reader");

    if (readerElement) {

        const startButton = document.getElementById(
            "startScannerBtn"
        );

        const stopButton = document.getElementById(
            "stopScannerBtn"
        );

        const scannerMessage = document.getElementById(
            "scannerMessage"
        );

        let scanner = null;
        let processing = false;


        async function stopScanner() {

            if (scanner && scanner.isScanning) {

                await scanner.stop();

            }

            startButton.disabled = false;
            stopButton.disabled = true;

        }


        async function markAttendance(token) {

            if (processing) return;

            processing = true;

            scannerMessage.textContent =
                "Verifying QR code and marking attendance...";

            await stopScanner();

            try {

                const response = await fetch(
                    "/api/attendance/mark",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": csrfToken
                        },

                        body: JSON.stringify({
                            token: token
                        })
                    }
                );

                const result = await response.json();

                if (!response.ok) {

                    throw new Error(
                        result.error || "Attendance could not be marked."
                    );

                }

                scannerMessage.textContent =
                    result.message || "Attendance marked successfully!";

                scannerMessage.classList.add("success-message");

            } catch (error) {

                scannerMessage.textContent = error.message;

                scannerMessage.classList.remove("success-message");

            } finally {

                processing = false;

            }

        }


        startButton.addEventListener("click", async () => {

            if (typeof Html5Qrcode === "undefined") {

                scannerMessage.textContent =
                    "QR scanner library could not be loaded.";

                return;

            }

            try {

                scanner = new Html5Qrcode("qr-reader");

                await scanner.start(
                    { facingMode: "environment" },

                    {
                        fps: 10,

                        qrbox: {
                            width: 250,
                            height: 250
                        }
                    },

                    decodedText => {
                        markAttendance(decodedText);
                    },

                    () => {}
                );

                startButton.disabled = true;
                stopButton.disabled = false;

                scannerMessage.textContent =
                    "Scanner running. Point your camera at the QR code.";

            } catch (error) {

                scannerMessage.textContent =
                    "Camera access failed. Check browser permissions.";

            }

        });


        stopButton.addEventListener("click", async () => {

            try {

                await stopScanner();

                scannerMessage.textContent = "Scanner stopped.";

            } catch (error) {

                scannerMessage.textContent =
                    "Unable to stop the scanner.";

            }

        });

    }

});