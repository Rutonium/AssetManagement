// Equipment Management System - Core JavaScript
// Connected to SQL Server via C# API

class EquipmentManager {
    constructor() {
        this.currentUser = null;
        this.init();
    }

    async init() {
        // Wait for the SQL API adapter to be ready
        let attempts = 0;
        while (!window.sqlAPI && attempts < 10) {
            await new Promise(resolve => setTimeout(resolve, 100));
            attempts++;
        }

        if (!window.sqlAPI) {
            console.error("SQL API not found. Make sure api-simulation.js is loaded.");
            return;
        }

        this.setupEventListeners();
        this.loadCurrentUser();
    }

    setupEventListeners() {
        // Global event listeners for the application
        document.addEventListener('DOMContentLoaded', () => {
            this.initializePage();
        });

        // Navigation handling
        document.addEventListener('click', (e) => {
            // Check if the clicked element or its parent has data-page
            const target = e.target.closest('[data-page]');
            if (target) {
                e.preventDefault();
                this.navigateToPage(target.dataset.page);
            }
        });
    }

    async loadCurrentUser() {
        if (window.sqlAPI) {
            this.currentUser = await window.sqlAPI.getCurrentUser();
            this.updateUserInterface();
        }
    }

    updateUserInterface() {
        if (!this.currentUser) return;

        const userNameElements = document.querySelectorAll('.user-full-name');
        userNameElements.forEach(el => el.textContent = this.currentUser.full_name);

        const userRoleElements = document.querySelectorAll('.user-role');
        userRoleElements.forEach(el => el.textContent = this.currentUser.role);
    }

    initializePage() {
        const currentPage = this.getCurrentPage();

        switch (currentPage) {
            case 'index':
                this.initializeDashboard();
                break;
            case 'warehouse':
                // Logic handled by warehouse.html script
                break;
            case 'catalog':
                // Logic handled by catalog.html script
                break;
            case 'rentals':
                // Logic handled by rentals.html script
                break;
        }
    }

    getCurrentPage() {
        const path = window.location.pathname;
        if (path.includes('warehouse')) return 'warehouse';
        if (path.includes('catalog')) return 'catalog';
        if (path.includes('rentals')) return 'rentals';
        return 'index';
    }

    navigateToPage(page) {
        window.location.href = `${page}.html`;
    }

    // --- DASHBOARD FUNCTIONALITY ---
    async initializeDashboard() {
        await this.loadDashboardStats();
        await this.loadRecentActivity();
        this.initializeDashboardCharts();
        await this.loadCalibrationAlerts();
    }

    async loadDashboardStats() {
        try {
            // Fetch real data from SQL
            const equipment = await window.sqlAPI.getEquipment();
            const rentals = await window.sqlAPI.getRentals();

            // Calculate stats
            const totalEquipment = equipment.length;
            const activeRentals = rentals.filter(r => r.status === 'Active').length;

            // Update UI
            this.updateStatCard('total-equipment', totalEquipment);
            this.updateStatCard('active-rentals', activeRentals);

            // Status Breakdown
            const statusMap = {};
            equipment.forEach(item => {
                const status = item.status || 'Unknown';
                statusMap[status] = (statusMap[status] || 0) + 1;
            });
            this.updateStatusBreakdown(statusMap);

        } catch (error) {
            console.error('Error loading dashboard stats:', error);
        }
    }

    updateStatCard(elementId, value) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = value;
            // Simple animation if anime.js is loaded
            if (typeof anime !== 'undefined') {
                anime({
                    targets: element,
                    innerHTML: [0, value],
                    round: 1,
                    easing: 'easeInOutExpo'
                });
            }
        }
    }

    updateStatusBreakdown(statusMap) {
        const container = document.getElementById('status-breakdown');
        if (container) {
            container.innerHTML = '';
            Object.entries(statusMap).forEach(([status, count]) => {
                const statusElement = document.createElement('div');
                statusElement.className = 'flex justify-between items-center text-sm mt-1';
                statusElement.innerHTML = `
                    <span class="text-gray-600">${status}:</span>
                    <span class="font-bold text-gray-800">${count}</span>
                `;
                container.appendChild(statusElement);
            });
        }
    }

    async loadRecentActivity() {
        const container = document.getElementById('recent-activity');
        if (container) {
            container.innerHTML = '<p class="text-sm text-gray-500">No recent activity logged.</p>';
        }
    }

    initializeDashboardCharts() {
        const chartContainer = document.getElementById('equipment-chart');
        if (chartContainer && typeof echarts !== 'undefined') {
            const chart = echarts.init(chartContainer);
            const option = {
                tooltip: { trigger: 'item' },
                series: [{
                    type: 'pie',
                    radius: ['40%', '70%'],
                    data: [
                        { value: 1, name: 'Available', itemStyle: { color: '#38A169' } },
                        { value: 0, name: 'Rented', itemStyle: { color: '#D69E2E' } }
                    ]
                }]
            };
            chart.setOption(option);
        }
    }

    async loadCalibrationAlerts() {
        try {
            const alerts = await window.sqlAPI.getCalibrationAlerts();
            const container = document.getElementById('calibration-alerts');

            if (container) {
                container.innerHTML = '';
                if (!alerts || alerts.length === 0) {
                    container.innerHTML = '<div class="text-sm text-gray-500">No upcoming calibrations.</div>';
                    return;
                }

                alerts.forEach(alert => {
                    const alertElement = document.createElement('div');
                    alertElement.className = `p-3 bg-white border-l-4 border-yellow-500 shadow-sm rounded`;
                    alertElement.innerHTML = `
                        <div class="font-medium text-gray-900">${alert.toolName || 'Equipment'}</div>
                        <div class="text-xs text-gray-500">Due: ${new Date(alert.nextCalibration).toLocaleDateString()}</div>
                    `;
                    container.appendChild(alertElement);
                });
            }
        } catch (error) {
            console.error("Error loading alerts", error);
        }
    }

    showNotification(message, type = 'info') {
        console.log(`[${type.toUpperCase()}] ${message}`);
        // You can add a toast UI implementation here later
    }
}

// Initialize the global instance
window.equipmentManager = new EquipmentManager();
