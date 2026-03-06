function openApp(port) {
    const host = window.location.hostname;
    window.location.href = `http://${host}:${port}`;
}

document.addEventListener("DOMContentLoaded", function () {
    var hostEl = document.getElementById("hostname");
    if (hostEl && !hostEl.textContent) {
        hostEl.textContent = window.location.hostname;
    }
});
