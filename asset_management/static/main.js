// Equipment Management System - Core JavaScript
// Connected to SQL Server via C# API

class EquipmentManager {
    constructor() {
        this.currentUser = null;
        this.init();
    }

    notifyAuthChanged() {
        window.dispatchEvent(new CustomEvent('asset-auth-changed', {
            detail: { user: this.currentUser || null }
        }));
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
        await this.loadCurrentUser();
        await this.ensureAuthenticated();
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
            this.notifyAuthChanged();
        }
    }

    async ensureAuthenticated() {
        if (this.currentUser) return;
        await this.showLoginModal();
    }

    updateUserInterface() {
        const displayName = this.currentUser?.displayName || this.currentUser?.full_name || 'Not logged in';
        const role = this.currentUser?.role || '';

        const userNameElements = document.querySelectorAll('.user-full-name');
        userNameElements.forEach(el => el.textContent = displayName);

        const userRoleElements = document.querySelectorAll('.user-role');
        userRoleElements.forEach(el => el.textContent = role);

        this.bindLogoutButtons();
        this.ensureAdminNavLink();
    }

    bindLogoutButtons() {
        document.querySelectorAll('button').forEach((button) => {
            const label = (button.textContent || '').trim().toLowerCase();
            if (label !== 'logout') return;
            if (button.dataset.boundLogout === 'true') return;
            button.dataset.boundLogout = 'true';
            button.addEventListener('click', async () => {
                await window.sqlAPI.logout();
                this.currentUser = null;
                this.updateUserInterface();
                this.notifyAuthChanged();
                await this.showLoginModal();
            });
        });
    }

    ensureAdminNavLink() {
        const navGroups = document.querySelectorAll('nav .ml-10.flex.items-baseline.space-x-4');
        if (!navGroups.length) return;
        const shouldShow = this.currentUser?.role === 'Admin';
        navGroups.forEach((group) => {
            let link = group.querySelector('a[data-admin-link="true"]');
            if (!shouldShow) {
                if (link) link.remove();
                return;
            }
            if (link) return;
            link = document.createElement('a');
            link.href = 'admin.html';
            link.dataset.adminLink = 'true';
            link.className = 'nav-link text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm';
            link.textContent = 'Admin';
            group.appendChild(link);
        });
    }

    async showLoginModal() {
        const existing = document.getElementById('global-login-modal');
        if (existing) {
            existing.classList.remove('hidden');
            return;
        }

        const modal = document.createElement('div');
        modal.id = 'global-login-modal';
        modal.style.position = 'fixed';
        modal.style.inset = '0';
        modal.style.background = 'rgba(0, 0, 0, 0.55)';
        modal.style.display = 'flex';
        modal.style.alignItems = 'center';
        modal.style.justifyContent = 'center';
        modal.style.zIndex = '2000';
        modal.innerHTML = `
            <div style="background:#fff;border-radius:12px;padding:20px;width:min(92vw,420px);box-shadow:0 20px 30px rgba(0,0,0,0.18);">
                <h2 style="font-size:1.25rem;font-weight:700;margin:0 0 8px 0;">Sign In</h2>
                <p style="margin:0 0 16px 0;color:#4b5563;font-size:0.9rem;">Find your name and enter your code.</p>
                <div style="display:grid;gap:12px;">
                    <label style="font-size:0.8rem;font-weight:600;color:#374151;">Name</label>
                    <div id="global-login-combobox" style="position:relative;">
                        <input id="global-login-search" type="text" autocomplete="off" style="width:100%;border:1px solid #d1d5db;border-radius:8px;padding:10px 38px 10px 10px;" placeholder="Select or type name">
                        <button id="global-login-toggle" type="button" aria-label="Show names" style="position:absolute;right:6px;top:50%;transform:translateY(-50%);border:0;background:transparent;width:28px;height:28px;border-radius:6px;cursor:pointer;color:#4b5563;font-size:0.9rem;">&#9662;</button>
                        <div id="global-login-dropdown" style="display:none;position:absolute;top:calc(100% + 4px);left:0;right:0;border:1px solid #e5e7eb;border-radius:8px;max-height:190px;overflow-y:auto;background:#fff;box-shadow:0 8px 18px rgba(0,0,0,0.1);z-index:20;"></div>
                    </div>
                    <label style="font-size:0.8rem;font-weight:600;color:#374151;">Code</label>
                    <input id="global-login-code" type="password" style="border:1px solid #d1d5db;border-radius:8px;padding:10px;" placeholder="Enter code">
                    <div id="global-login-error" style="display:none;color:#b91c1c;font-size:0.8rem;"></div>
                    <button id="global-login-submit" style="background:#1f2937;color:#fff;border:0;border-radius:8px;padding:10px;cursor:pointer;">Login</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        const searchInput = document.getElementById('global-login-search');
        const comboboxEl = document.getElementById('global-login-combobox');
        const toggleBtn = document.getElementById('global-login-toggle');
        const dropdownEl = document.getElementById('global-login-dropdown');
        const codeInput = document.getElementById('global-login-code');
        const submitBtn = document.getElementById('global-login-submit');
        const errorEl = document.getElementById('global-login-error');
        const employees = await window.sqlAPI.getEmployees();
        const allUsers = [
            {
                kind: 'admin',
                username: 'admin',
                employeeID: 999999,
                displayName: 'Administrator (Local)',
                searchText: 'administrator admin 999999'
            },
            ...(employees || []).map((employee) => ({
                kind: 'employee',
                employeeID: Number(employee.employeeID),
                displayName: employee.displayName || employee.name || `Employee #${employee.employeeID}`,
                name: employee.name || '',
                employeeNumber: employee.employeeNumber || String(employee.employeeID),
                searchText: `${employee.displayName || ''} ${employee.name || ''} ${employee.employeeNumber || ''} ${employee.employeeID || ''}`.toLowerCase()
            }))
        ];
        let selectedUser = null;
        let filteredUsers = [];
        let isDropdownOpen = false;

        const getUserLabel = (user) => {
            if (!user) return '';
            return user.kind === 'admin'
                ? user.displayName
                : `${user.displayName} (#${user.employeeNumber || user.employeeID})`;
        };

        const hideDropdown = () => {
            dropdownEl.style.display = 'none';
            isDropdownOpen = false;
        };

        const showDropdown = () => {
            dropdownEl.style.display = 'block';
            isDropdownOpen = true;
        };

        const setSelectedUser = (user, { updateInput = true } = {}) => {
            selectedUser = user;
            if (updateInput) {
                searchInput.value = getUserLabel(selectedUser);
            }
        };

        const renderDropdown = (query) => {
            const term = String(query || '').trim().toLowerCase();
            filteredUsers = allUsers
                .filter((user) => !term || user.searchText.includes(term))
                .slice(0, 50);
            dropdownEl.innerHTML = '';
            if (!filteredUsers.length) {
                const empty = document.createElement('div');
                empty.style.padding = '8px';
                empty.style.fontSize = '0.8rem';
                empty.style.color = '#6b7280';
                empty.textContent = 'No matching users';
                dropdownEl.appendChild(empty);
                return;
            }
            filteredUsers.forEach((user) => {
                const row = document.createElement('button');
                row.type = 'button';
                row.style.display = 'block';
                row.style.width = '100%';
                row.style.textAlign = 'left';
                row.style.padding = '8px 10px';
                row.style.fontSize = '0.85rem';
                row.style.border = '0';
                row.style.borderBottom = '1px solid #f3f4f6';
                row.style.background = '#fff';
                row.style.cursor = 'pointer';
                row.textContent = getUserLabel(user);
                row.addEventListener('mousedown', (event) => event.preventDefault());
                row.addEventListener('click', () => {
                    setSelectedUser(user);
                    hideDropdown();
                });
                row.addEventListener('mouseenter', () => { row.style.background = '#f9fafb'; });
                row.addEventListener('mouseleave', () => { row.style.background = '#fff'; });
                dropdownEl.appendChild(row);
            });
        };

        const clearSelectedWhenInputChanges = () => {
            if (!selectedUser) return;
            if (searchInput.value.trim() !== getUserLabel(selectedUser)) {
                setSelectedUser(null, { updateInput: false });
            }
        };

        const tryResolveTypedSelection = () => {
            if (selectedUser) return selectedUser;
            const term = String(searchInput.value || '').trim().toLowerCase();
            if (!term) return null;
            const matches = allUsers.filter((user) => {
                const display = (user.displayName || '').toLowerCase();
                const number = String(user.employeeNumber || user.employeeID || '').toLowerCase();
                return display === term || number === term || getUserLabel(user).toLowerCase() === term;
            });
            if (matches.length === 1) {
                setSelectedUser(matches[0], { updateInput: false });
                return matches[0];
            }
            return null;
        };

        const submit = async () => {
            const pinCode = (codeInput.value || '').trim();
            errorEl.style.display = 'none';
            const resolvedUser = tryResolveTypedSelection();
            if (!resolvedUser || pinCode.length < 4) {
                errorEl.textContent = 'Select your name and enter a valid code.';
                errorEl.style.display = 'block';
                return;
            }
            submitBtn.disabled = true;
            try {
                if (resolvedUser.kind === 'admin') {
                    this.currentUser = await window.sqlAPI.loginAdmin('admin', pinCode);
                } else {
                    this.currentUser = await window.sqlAPI.loginEmployee(resolvedUser.employeeID, pinCode);
                }
                this.updateUserInterface();
                this.notifyAuthChanged();
                modal.remove();
            } catch (error) {
                errorEl.textContent = 'Login failed. Check your code.';
                errorEl.style.display = 'block';
            } finally {
                submitBtn.disabled = false;
            }
        };

        submitBtn.addEventListener('click', submit);
        searchInput.addEventListener('input', () => {
            clearSelectedWhenInputChanges();
            renderDropdown(searchInput.value || '');
            showDropdown();
        });
        searchInput.addEventListener('keydown', (event) => {
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                renderDropdown(searchInput.value || '');
                showDropdown();
                return;
            }
            if (event.key === 'Escape') {
                hideDropdown();
                return;
            }
            if (event.key === 'Enter') submit();
        });
        searchInput.addEventListener('focus', () => {
            errorEl.style.display = 'none';
        });
        toggleBtn.addEventListener('click', () => {
            if (isDropdownOpen) {
                hideDropdown();
                return;
            }
            renderDropdown(searchInput.value || '');
            showDropdown();
            searchInput.focus();
        });
        modal.addEventListener('click', (event) => {
            if (!comboboxEl.contains(event.target)) {
                hideDropdown();
            }
        });
        codeInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') submit();
        });
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
                        whoHasIt: rental.employeeDisplay || `Employee #${rental.employeeID}`,
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
