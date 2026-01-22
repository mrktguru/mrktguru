// Device Profile Selector - Auto-save on change
document.addEventListener('DOMContentLoaded', function () {
    const deviceSelect = document.getElementById('deviceProfileSelect');
    if (!deviceSelect) return;

    // Get accountId from data attribute
    const accountId = deviceSelect.dataset.accountId;
    if (!accountId) {
        console.error('Account ID not found in device selector');
        return;
    }

    // Device presets data
    const devicePresets = {
        original: null, // Will delete device_profile to use TData original
        json: 'use_json', // Special flag to use JSON parameters
        iphone15_ios18: {
            device_model: 'iPhone 15 Pro',
            system_version: 'iOS 18.2',
            app_version: '10.5.1',
            lang_code: 'en',
            system_lang_code: 'en-US',
            client_type: 'ios'
        },
        iphone14_ios17: {
            device_model: 'iPhone 14 Pro',
            system_version: 'iOS 17.6',
            app_version: '10.5.1',
            lang_code: 'en',
            system_lang_code: 'en-US',
            client_type: 'ios'
        },
        iphone13_ios17: {
            device_model: 'iPhone 13',
            system_version: 'iOS 17.4',
            app_version: '10.5.1',
            lang_code: 'en',
            system_lang_code: 'en-US',
            client_type: 'ios'
        },
        iphone12_ios16: {
            device_model: 'iPhone 12',
            system_version: 'iOS 16.7',
            app_version: '10.5.1',
            lang_code: 'en',
            system_lang_code: 'en-US',
            client_type: 'ios'
        },
        iphone11_ios16: {
            device_model: 'iPhone 11',
            system_version: 'iOS 16.5',
            app_version: '10.5.1',
            lang_code: 'en',
            system_lang_code: 'en-US',
            client_type: 'ios'
        },
        samsung_s24_android14: {
            device_model: 'Samsung Galaxy S24 Ultra',
            system_version: 'Android 14',
            app_version: '10.5.0',
            lang_code: 'en',
            system_lang_code: 'en-US',
            client_type: 'android'
        },
        samsung_s21_android13: {
            device_model: 'Samsung Galaxy S21 Ultra',
            system_version: 'Android 13',
            app_version: '10.5.0',
            lang_code: 'en',
            system_lang_code: 'en-US',
            client_type: 'android'
        },
        pixel8_android14: {
            device_model: 'Google Pixel 8 Pro',
            system_version: 'Android 14',
            app_version: '10.5.0',
            lang_code: 'en',
            system_lang_code: 'en-US',
            client_type: 'android'
        },
        xiaomi14_android14: {
            device_model: 'Xiaomi 14 Pro',
            system_version: 'Android 14',
            app_version: '10.5.0',
            lang_code: 'en',
            system_lang_code: 'en-US',
            client_type: 'android'
        },
        windows11_desktop: {
            device_model: 'Desktop',
            system_version: 'Windows 11',
            app_version: '4.16.8 x64',
            lang_code: 'en',
            system_lang_code: 'en-US',
            client_type: 'desktop'
        },
        windows10_desktop: {
            device_model: 'Desktop',
            system_version: 'Windows 10',
            app_version: '4.16.8 x64',
            lang_code: 'en',
            system_lang_code: 'en-US',
            client_type: 'desktop'
        },
        macos_sonoma: {
            device_model: 'Desktop',
            system_version: 'macOS Sonoma',
            app_version: '10.5.1 arm64',
            lang_code: 'en',
            system_lang_code: 'en-US',
            client_type: 'desktop'
        }
    };

    deviceSelect.addEventListener('change', async function (e) {
        const presetKey = e.target.value;
        const preset = devicePresets[presetKey];

        // Show loading indicator
        deviceSelect.disabled = true;

        try {
            const formData = new FormData();

            if (preset === null) {
                // User selected "Use Original" - we'll send a flag to delete device_profile
                formData.append('use_original', 'true');
            } else if (preset === 'use_json') {
                // User selected JSON parameters
                formData.append('use_json', 'true');
            } else {
                // User selected a preset
                for (const [key, value] of Object.entries(preset)) {
                    formData.append(key, value);
                }
            }

            const response = await fetch(`/accounts/${accountId}/update_device`, {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                // Update the Selected Profile display
                if (preset === null) {
                    document.getElementById('profile-device').textContent = 'Original';
                    document.getElementById('profile-system').textContent = 'Original';
                    document.getElementById('profile-app').textContent = 'Original';
                    document.getElementById('profile-language').textContent = 'en / en-US';
                } else if (preset === 'use_json') {
                    // Get JSON params from data attribute
                    const jsonParamsElem = document.getElementById('json-device-params');
                    if (jsonParamsElem) {
                        try {
                            const jsonParams = JSON.parse(jsonParamsElem.textContent);
                            document.getElementById('profile-device').textContent = jsonParams.device_model || 'N/A';
                            document.getElementById('profile-system').textContent = jsonParams.system_version || 'N/A';
                            document.getElementById('profile-app').textContent = jsonParams.app_version || 'N/A';
                            document.getElementById('profile-language').textContent =
                                `${jsonParams.lang_code || 'en'} / ${jsonParams.system_lang_code || 'en-US'}`;
                        } catch (e) {
                            console.error('Failed to parse JSON params:', e);
                        }
                    }
                } else {
                    document.getElementById('profile-device').textContent = preset.device_model;
                    document.getElementById('profile-system').textContent = preset.system_version;
                    document.getElementById('profile-app').textContent = preset.app_version;
                    document.getElementById('profile-language').textContent = `${preset.lang_code} / ${preset.system_lang_code}`;
                }

                // Show success feedback
                showToast('Device profile updated successfully', 'success');
            } else {
                throw new Error('Failed to update device profile');
            }
        } catch (error) {
            console.error('Error updating device profile:', error);
            showToast('Error updating device profile', 'danger');
            // Reload page to restore correct state
            setTimeout(() => location.reload(), 1500);
        } finally {
            deviceSelect.disabled = false;
        }
    });

    // Simple toast notification
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} position-fixed top-0 start-50 translate-middle-x mt-3`;
        toast.style.zIndex = '9999';
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
});
