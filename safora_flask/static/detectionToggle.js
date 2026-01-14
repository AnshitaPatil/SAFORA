// static/js/detectionToggle.js

class DetectionToggle {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.isEnabled = false;
        this.initialize();
    }

    async initialize() {
        this.render();
        await this.checkDetectionStatus();
        setInterval(() => this.checkDetectionStatus(), 2000); // Check every 2 seconds
    }

    async checkDetectionStatus() {
        try {
            const response = await fetch('/detection_status');
            const data = await response.json();
            this.isEnabled = data.enabled;
            this.updateUI();
        } catch (error) {
            console.error('Error checking detection status:', error);
        }
    }

    async toggleDetection() {
        try {
            const response = await fetch('/toggle_detection', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ enabled: !this.isEnabled }),
            });
            
            const data = await response.json();
            if (data.success) {
                this.isEnabled = data.enabled;
                this.updateUI();
                
                // Show notification
                this.showNotification(
                    data.enabled 
                        ? 'AI Detection activated. Monitoring started.' 
                        : 'AI Detection deactivated. Monitoring stopped.',
                    data.enabled ? 'success' : 'info'
                );
            } else {
                console.error('Error toggling detection:', data.error);
                this.showNotification('Failed to toggle detection', 'error');
            }
        } catch (error) {
            console.error('Error toggling detection:', error);
            this.showNotification('Error connecting to server', 'error');
        }
    }

    showNotification(message, type = 'info') {
        // Create or update notification element
        let notification = document.getElementById('detection-notification');
        if (!notification) {
            notification = document.createElement('div');
            notification.id = 'detection-notification';
            notification.style.cssText = `
                position: fixed;
                top: 80px;
                right: 20px;
                padding: 12px 20px;
                border-radius: 8px;
                color: white;
                font-weight: 500;
                z-index: 10000;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                transition: all 0.3s ease;
            `;
            document.body.appendChild(notification);
        }

        // Set color based on type
        const colors = {
            success: '#4CAF50',
            info: '#2196F3',
            error: '#f44336'
        };
        notification.style.backgroundColor = colors[type] || colors.info;
        notification.textContent = message;
        notification.style.opacity = '1';
        notification.style.transform = 'translateX(0)';

        // Hide after 3 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(100%)';
        }, 3000);
    }

    render() {
        this.container.innerHTML = `
            <div class="relative">
                <button id="detectionToggleBtn" class="flex items-center gap-2 px-4 py-2 rounded-full transition-all duration-300 border-2" style="font-weight: 600;">
                    <span class="icon"></span>
                    <span class="text">Detection OFF</span>
                </button>
            </div>
        `;

        this.toggleBtn = document.getElementById('detectionToggleBtn');
        this.toggleBtn.addEventListener('click', () => this.toggleDetection());
    }

    updateUI() {
        // Update button appearance
        const baseClass = 'flex items-center gap-2 px-4 py-2 rounded-full transition-all duration-300 border-2';
        this.toggleBtn.className = baseClass + ` ${
            this.isEnabled
                ? 'bg-green-600 text-white border-green-700 hover:bg-green-700 shadow-lg' 
                : 'bg-gray-100 text-gray-700 border-gray-300 hover:bg-gray-200'
        }`;
        this.toggleBtn.style.fontWeight = '600';

        // Update icon and text
        const iconSpan = this.toggleBtn.querySelector('.icon');
        const textSpan = this.toggleBtn.querySelector('.text');
        
        if (this.isEnabled) {
            iconSpan.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`;
            textSpan.textContent = 'Detection ON';
        } else {
            iconSpan.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
            textSpan.textContent = 'Detection OFF';
        }
    }
}

