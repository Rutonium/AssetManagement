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
            case 'operations':
                // Logic handled by operations.html script
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
        if (path.includes('operations')) return 'operations';
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
        this.setupLocateEquipment();
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

    async setupLocateEquipment() {
        this.locateData = [];
        const openBtn = document.getElementById('open-locate-modal');
        const modal = document.getElementById('locate-modal');
        const closeBtn = document.getElementById('close-locate-modal');
        const input = document.getElementById('locate-search-input');
        const results = document.getElementById('locate-results');
        if (!openBtn || !modal || !closeBtn || !input || !results) return;

        openBtn.addEventListener('click', async () => {
            modal.classList.add('active');
            input.value = '';
            results.innerHTML = 'Loading...';
            await this.loadLocateData();
            this.renderLocateResults('');
            input.focus();
        });

        closeBtn.addEventListener('click', () => modal.classList.remove('active'));
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.classList.remove('active');
        });
        input.addEventListener('input', () => this.renderLocateResults(input.value));
    }

    async loadLocateData() {
        const [equipment, rentals] = await Promise.all([
            window.sqlAPI.getEquipment(),
            window.sqlAPI.getRentals()
        ]);

        const holderByTool = new Map();
        (rentals || []).forEach((rental) => {
            const status = String(rental.status || '');
            if (!['Active', 'Overdue', 'Reserved'].includes(status)) return;
            (rental.rentalItems || []).forEach((item) => {
                const lifecycleState = item?.lifecycle?.state || '';
                const isPickedOrReserved = ['Picked Up', 'Reserved'].includes(lifecycleState) || !!item.toolInstanceID;
                if (!isPickedOrReserved) return;
                const key = `${item.toolID}:${item.toolInstanceID || 0}`;
                if (!holderByTool.has(key)) {
                    holderByTool.set(key, {
                        whoHasIt: `Employee #${rental.employeeID}`,
                        project: rental.projectCode || '-',
                        rentalNumber: rental.rentalNumber || '-'
                    });
                }
            });
        });

        this.locateData = (equipment || []).map((tool) => {
            const holder = holderByTool.get(`${tool.id}:0`) || null;
            return {
                id: tool.id,
                name: tool.name || '',
                model: tool.model_number || '',
                manufacturer: tool.manufacturer || '',
                serial: tool.serial_number || '',
                description: tool.description || '',
                category: `Category ${tool.category_id || '-'}`,
                where: holder ? 'Checked out / reserved' : (tool.location_code || 'Warehouse / Unassigned'),
                whoHasIt: holder ? holder.whoHasIt : 'In stock',
                project: holder ? holder.project : '-',
                rentalNumber: holder ? holder.rentalNumber : '-'
            };
        });
    }

    renderLocateResults(rawTerm) {
        const results = document.getElementById('locate-results');
        if (!results) return;
        const term = String(rawTerm || '').trim().toLowerCase();
        let rows = this.locateData || [];
        if (term) {
            rows = rows.filter((item) => {
                const searchable = [
                    item.name,
                    item.model,
                    item.manufacturer,
                    item.serial,
                    item.description,
                    item.category,
                    item.where,
                    item.whoHasIt,
                    item.project,
                    item.rentalNumber
                ].join(' ').toLowerCase();
                return searchable.includes(term);
            });
        }

        if (!rows.length) {
            results.innerHTML = '<div class="text-sm text-gray-500">No matching equipment found.</div>';
            return;
        }

        results.innerHTML = rows.map((item) => `
            <div class="border rounded p-3 bg-white">
                <div class="font-semibold text-gray-900">${item.name} <span class="text-xs text-gray-500">(${item.serial || 'No serial'})</span></div>
                <div class="text-xs text-gray-600 mt-1">${item.manufacturer} ${item.model ? `• ${item.model}` : ''} • ${item.category}</div>
                <div class="grid grid-cols-1 md:grid-cols-4 gap-2 mt-2 text-xs">
                    <div><strong>Who has it:</strong> ${item.whoHasIt}</div>
                    <div><strong>Where is it:</strong> ${item.where}</div>
                    <div><strong>Project:</strong> ${item.project}</div>
                    <div><strong>Rental no:</strong> ${item.rentalNumber}</div>
                </div>
            </div>
        `).join('');
    }
}

// Initialize the global instance
window.equipmentManager = new EquipmentManager();
