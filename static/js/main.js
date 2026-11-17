/**
 * TEAMFINDER - MAIN CLIENT JAVASCRIPT
 * Handles AJAX requests, dynamic UI rendering, modals, and toasts.
 */

// Toast notification helper
function showToast(message, type = 'info') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        document.body.appendChild(container);
    }

    const toastId = 'toast_' + Date.now();
    const bgClass = type === 'success' ? 'bg-success text-white' :
                    type === 'danger' || type === 'error' ? 'bg-danger text-white' :
                    type === 'warning' ? 'bg-warning text-dark' : 'bg-primary text-white';

    const icon = type === 'success' ? 'bi-check-circle-fill' :
                 type === 'danger' || type === 'error' ? 'bi-exclamation-triangle-fill' :
                 type === 'warning' ? 'bi-exclamation-circle-fill' : 'bi-info-circle-fill';

    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center ${bgClass} border-0 shadow-lg" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body d-flex align-items-center gap-2">
                    <i class="bi ${icon} fs-5"></i>
                    <div>${message}</div>
                </div>
                <button type="button" class="btn-close ${type !== 'warning' ? 'btn-close-white' : ''} me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', toastHtml);
    const toastEl = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
    toast.show();

    toastEl.addEventListener('hidden.bs.toast', () => {
        toastEl.remove();
    });
}

// Global helper for fetch requests with standard error handling
async function apiRequest(url, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    };
    if (data && (method === 'POST' || method === 'PUT')) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(url, options);
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || `Request failed with status ${response.status}`);
        }
        return result;
    } catch (err) {
        console.error('API Error:', err);
        throw err;
    }
}

// Initialize tooltips and active navigation states
document.addEventListener('DOMContentLoaded', () => {
    // Bootstrap tooltip initialization
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(el => new bootstrap.Tooltip(el));

    // Handle logout link
    const logoutLinks = document.querySelectorAll('.action-logout');
    logoutLinks.forEach(link => {
        link.addEventListener('click', async (e) => {
            e.preventDefault();
            try {
                await apiRequest('/api/auth/logout', 'POST');
                window.location.href = '/login';
            } catch (err) {
                window.location.href = '/login';
            }
        });
    });
});
