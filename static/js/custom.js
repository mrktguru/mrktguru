// Custom JavaScript for Telegram System

$(document).ready(function() {
    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        $('.alert').fadeOut('slow');
    }, 5000);

    // Confirm delete actions
    $('form[data-confirm]').on('submit', function(e) {
        if (!confirm($(this).data('confirm'))) {
            e.preventDefault();
            return false;
        }
    });

    // AJAX proxy test
    $('.test-proxy-btn').on('click', function() {
        var proxyId = $(this).data('proxy-id');
        var btn = $(this);
        
        btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Testing...');
        
        $.ajax({
            url: '/proxies/' + proxyId + '/test',
            type: 'POST',
            success: function(response) {
                alert('Proxy test successful! IP: ' + response.ip);
                location.reload();
            },
            error: function(xhr) {
                var error = xhr.responseJSON ? xhr.responseJSON.error : 'Unknown error';
                alert('Proxy test failed: ' + error);
                btn.prop('disabled', false).html('Test');
            }
        });
    });
});
