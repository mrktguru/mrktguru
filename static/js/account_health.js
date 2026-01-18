// Account Health Check Function
function checkAccountHealth(method, accountId) {
    const methodNames = {
        'self_check': 'Self-Check',
        'public_channel': 'Public Channel',
        'get_me': 'Get Me'
    };

    // Show loading state
    const btn = document.querySelector('.btn-outline-success.dropdown-toggle');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Checking...';

    // Make AJAX request
    fetch(`/accounts/${accountId}/verify-safe`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `method=${method}`
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Success - show alert (NO reload, just health check)
                const userDisplay = data.user.username ? '@' + data.user.username : (data.user.first_name || 'ID: ' + data.user.id);
                const alert = document.createElement('div');
                alert.className = 'alert alert-success alert-dismissible fade show mt-3';
                alert.innerHTML = `
                    <strong>✅ Account is Alive!</strong> Check via ${methodNames[method]} successful.
                    <br><small>Duration: ${data.duration || 'N/A'} | User: ${userDisplay}</small>
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                `;
                btn.parentElement.parentElement.appendChild(alert);

                // Auto-dismiss after 10 seconds
                setTimeout(() => alert.remove(), 10000);
            } else {
                // Error - show error message
                const errorType = data.error_type || 'error';
                let alertClass = 'alert-danger';
                let icon = '❌';

                if (errorType === 'cooldown') {
                    alertClass = 'alert-warning';
                    icon = '⏱️';
                } else if (errorType === 'flood_wait') {
                    alertClass = 'alert-warning';
                    icon = '⚠️';
                }

                const alert = document.createElement('div');
                alert.className = `alert ${alertClass} alert-dismissible fade show mt-3`;
                alert.innerHTML = `
                    <strong>${icon} ${errorType === 'cooldown' ? 'Cooldown Active' : 'Error'}</strong> ${data.error}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                `;
                btn.parentElement.parentElement.appendChild(alert);

                // Auto-dismiss after 10 seconds
                setTimeout(() => alert.remove(), 10000);
            }
        })
        .catch(error => {
            // Network error
            const alert = document.createElement('div');
            alert.className = 'alert alert-danger alert-dismissible fade show mt-3';
            alert.innerHTML = `
                <strong>❌ Network Error!</strong> ${error.message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            btn.parentElement.parentElement.appendChild(alert);
            setTimeout(() => alert.remove(), 5000);
        })
        .finally(() => {
            // Re-enable button
            btn.disabled = false;
            btn.innerHTML = originalText;
        });
}
