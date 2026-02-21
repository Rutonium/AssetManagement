// SQL Server API Adapter
class SQLServerAPI {
    constructor() {
        const configuredBase = window.ASSET_MANAGEMENT_BASE_PATH;
        if (configuredBase) {
            this.baseUrl = `${configuredBase.replace(/\/$/, '')}/api`;
        } else {
            this.baseUrl = window.location.pathname.startsWith('/asset_management/')
                ? '/asset_management/api'
                : '/api';
        }
        this.currentUser = null;
        this.sessionTokenKey = 'asset_management_session_token';
    }

    getSessionToken() {
        try {
            return window.localStorage.getItem(this.sessionTokenKey) || '';
        } catch (_) {
            return '';
        }
    }

    setSessionToken(token) {
        try {
            if (token) {
                window.localStorage.setItem(this.sessionTokenKey, String(token));
            } else {
                window.localStorage.removeItem(this.sessionTokenKey);
            }
        } catch (_) {
            // ignore localStorage issues
        }
    }

    _withAuth(init) {
        const source = init || {};
        const headers = { ...(source.headers || {}) };
        const token = this.getSessionToken();
        if (token) {
            headers['X-Session-Token'] = token;
        }
        return { ...source, headers };
    }

    async _fetch(url, init) {
        return fetch(url, this._withAuth(init));
    }

    async _getJson(url, init) {
        const response = await this._fetch(url, init);
        if (!response.ok) {
            if (response.status === 401) {
                this.currentUser = null;
                this.setSessionToken('');
            }
            const message = await response.text().catch(() => '');
            throw new Error(`${response.status} ${response.statusText}${message ? ` - ${message}` : ''}`);
        }
        return response.json();
    }

    _currentEmployeeId() {
        const raw = this.currentUser?.employeeID || this.currentUser?.id;
        const parsed = parseInt(raw || '0', 10);
        return parsed > 0 ? parsed : null;
    }

    async loginEmployee(employeeID, pinCode) {
        const payload = {
            employeeID: parseInt(employeeID || '0', 10),
            pinCode: String(pinCode || '')
        };
        const result = await this._getJson(`${this.baseUrl}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        this.setSessionToken(result?.sessionToken || '');
        this.currentUser = result?.user || null;
        return this.currentUser;
    }

    async loginAdmin(username, password) {
        const payload = {
            username: String(username || ''),
            password: String(password || '')
        };
        const result = await this._getJson(`${this.baseUrl}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        this.setSessionToken(result?.sessionToken || '');
        this.currentUser = result?.user || null;
        return this.currentUser;
    }

    async login(employeeID, pinCode) {
        return this.loginEmployee(employeeID, pinCode);
    }

    async logout() {
        try {
            await this._getJson(`${this.baseUrl}/auth/logout`, { method: 'POST' });
        } catch (_) {
            // ignore and clear local session anyway
        }
        this.currentUser = null;
        this.setSessionToken('');
    }

    async getCurrentUser(forceRefresh = false) {
        if (!forceRefresh && this.currentUser) {
            return this.currentUser;
        }
        const token = this.getSessionToken();
        if (!token) {
            this.currentUser = null;
            return null;
        }
        try {
            const payload = await this._getJson(`${this.baseUrl}/auth/me`);
            this.currentUser = payload?.user || null;
            return this.currentUser;
        } catch (_) {
            this.currentUser = null;
            this.setSessionToken('');
            return null;
        }
    }

    async getAdminUsers(forceRefresh = false) {
        const qs = forceRefresh ? '?forceRefresh=true' : '';
        return this._getJson(`${this.baseUrl}/admin/users${qs}`);
    }

    async createAdminUser(payload) {
        return this._getJson(`${this.baseUrl}/admin/users`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload || {})
        });
    }

    async updateAdminUser(employeeID, payload) {
        return this._getJson(`${this.baseUrl}/admin/users/${employeeID}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload || {})
        });
    }

    async deleteAdminUser(employeeID) {
        return this._getJson(`${this.baseUrl}/admin/users/${employeeID}`, {
            method: 'DELETE'
        });
    }

    async searchProjects(query, limit = 20) {
        const params = new URLSearchParams({
            q: String(query || ''),
            limit: String(limit || 20)
        });
        return this._getJson(`${this.baseUrl}/projects/search?${params.toString()}`);
    }

    async getEmployees(forceRefresh = false, throwOnError = false) {
        try {
            const qs = forceRefresh ? '?forceRefresh=true' : '';
            return await this._getJson(`${this.baseUrl}/employees${qs}`);
        } catch (error) {
            console.error('Error fetching employees:', error);
            if (throwOnError) {
                throw error;
            }
            return [];
        }
    }

    // --- RENTALS ---
    async getRentals() {
        try {
            return await this._getJson(`${this.baseUrl}/rentals`);
        } catch (error) {
            console.error('Error fetching rentals:', error);
            return [];
        }
    }

    async getRental(id) {
        try {
            return await this._getJson(`${this.baseUrl}/rentals/${id}`);
        } catch (error) {
            console.error('Error fetching rental:', error);
            return null;
        }
    }

    async getRentalAvailability(toolID, startDate, endDate, quantity) {
        try {
            const params = new URLSearchParams({
                toolID: String(toolID),
                startDate: String(startDate),
                endDate: String(endDate),
                quantity: String(quantity || 1)
            });
            return await this._getJson(`${this.baseUrl}/rentals/availability/by-tool?${params.toString()}`);
        } catch (error) {
            console.error('Error checking rental availability:', error);
            return null;
        }
    }

    async createRental(rentalData) {
        try {
            const response = await this._fetch(`${this.baseUrl}/rentals`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(rentalData)
            });
            return response.ok;
        } catch (error) {
            console.error('Error creating rental:', error);
            return false;
        }
    }

    async createRentalDetailed(rentalData) {
        try {
            return await this._getJson(`${this.baseUrl}/rentals`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(rentalData)
            });
        } catch (error) {
            console.error('Error creating rental (detailed):', error);
            return null;
        }
    }

    async getOfferByNumber(offerNumber) {
        try {
            return await this._getJson(`${this.baseUrl}/offers/${encodeURIComponent(offerNumber)}`);
        } catch (error) {
            console.error('Error fetching offer:', error);
            return null;
        }
    }

    async checkoutOffer(offerNumber, checkoutData) {
        try {
            return await this._getJson(`${this.baseUrl}/offers/${encodeURIComponent(offerNumber)}/checkout`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(checkoutData)
            });
        } catch (error) {
            console.error('Error checking out offer:', error);
            return null;
        }
    }

    async kioskLend(payload) {
        try {
            return await this._getJson(`${this.baseUrl}/kiosk/lend`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } catch (error) {
            console.error('Error creating kiosk lend:', error);
            return null;
        }
    }

    async updateRentalStatus(id, action) {
        try {
            let response;
            const actorUserID = this._currentEmployeeId();
            if (action === 'approve') {
                response = await this._fetch(`${this.baseUrl}/rentals/${id}/decide`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ decision: 'approve', operatorUserID: actorUserID })
                });
            } else if (action === 'cancel') {
                response = await this._fetch(`${this.baseUrl}/rentals/${id}/decide`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ decision: 'reject', reason: 'Rejected by warehouse', operatorUserID: actorUserID })
                });
            } else {
                response = await this._fetch(`${this.baseUrl}/rentals/${id}/${action}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
            }
            if (!response.ok) {
                const detail = await response.text().catch(() => '');
                console.error(`Action ${action} failed:`, response.status, detail);
            }
            return response.ok;
        } catch (error) {
            console.error(`Error performing ${action}:`, error);
            return false;
        }
    }

    async decideReservation(id, payload) {
        try {
            const body = { ...(payload || {}) };
            if (!body.operatorUserID) {
                body.operatorUserID = this._currentEmployeeId();
            }
            return await this._getJson(`${this.baseUrl}/rentals/${id}/decide`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
        } catch (error) {
            console.error('Error deciding reservation:', error);
            return null;
        }
    }

    async markItemsForRental(id, payload) {
        try {
            const body = { ...(payload || {}) };
            if (!body.operatorUserID) {
                body.operatorUserID = this._currentEmployeeId();
            }
            return await this._getJson(`${this.baseUrl}/rentals/${id}/mark-items-for-rental`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
        } catch (error) {
            console.error('Error marking items for rental:', error);
            return null;
        }
    }

    async receiveMarkedItems(id, payload) {
        try {
            const body = { ...(payload || {}) };
            if (!body.operatorUserID) {
                body.operatorUserID = this._currentEmployeeId();
            }
            return await this._getJson(`${this.baseUrl}/rentals/${id}/receive-marked-items`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
        } catch (error) {
            console.error('Error receiving marked items:', error);
            return null;
        }
    }

    async returnRental(id, condition, notes) {
        try {
            const payload = { condition: condition, notes: notes };
            const response = await this._fetch(`${this.baseUrl}/rentals/${id}/return`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            return response.ok;
        } catch (error) {
            console.error('Error returning rental:', error);
            return false;
        }
    }

    async extendRental(id, newDate) {
        try {
            const payload = { newEndDate: newDate };
            const response = await this._fetch(`${this.baseUrl}/rentals/${id}/extend`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            return response.ok;
        } catch (error) {
            console.error('Error extending rental:', error);
            return false;
        }
    }

    async forceExtendRental(id, newDate) {
        try {
            const payload = { newEndDate: newDate };
            const response = await this._fetch(`${this.baseUrl}/rentals/${id}/force-extend`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            return response.ok;
        } catch (error) {
            console.error('Error force extending rental:', error);
            return false;
        }
    }

    async forceReturnRental(id, condition, notes) {
        try {
            const payload = { condition: condition, notes: notes };
            const response = await this._fetch(`${this.baseUrl}/rentals/${id}/force-return`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            return response.ok;
        } catch (error) {
            console.error('Error force returning rental:', error);
            return false;
        }
    }

    async markRentalLost(id) {
        try {
            const response = await this._fetch(`${this.baseUrl}/rentals/${id}/mark-lost`, {
                method: 'POST'
            });
            if (!response.ok) return null;
            return await response.json();
        } catch (error) {
            console.error('Error marking rental lost:', error);
            return null;
        }
    }

    // --- EQUIPMENT ---
    async getEquipment() {
        try {
            const data = await this._getJson(`${this.baseUrl}/equipment`);
            return (data || []).map(item => ({
                id: item.toolID,
                name: item.toolName,
                serial_number: item.serialNumber,
                model_number: item.modelNumber,
                manufacturer: item.manufacturer,
                category_id: item.categoryID,
                warehouse_id: item.warehouseID,
                status: item.status,
                condition: item.condition || 'Good',
                daily_rental_cost: item.dailyRentalCost,
                purchase_cost: item.purchaseCost,
                purchase_date: item.purchaseDate,
                current_value: item.currentValue,
                location_code: item.locationCode,
                image_path: item.imagePath || '',
                instance_count: item.instanceCount ?? 0,
                instance_next_calibration_min: item.instanceNextCalibrationMin || null,
                last_certification_date: item.lastCalibration,
                certification_interval_months: item.calibrationInterval,
                certificate_expiry_date: item.nextCalibration,
                next_calibration_date: item.nextCalibration,
                requires_certification: !!item.requiresCertification,
                description: item.description || ''
            }));
        } catch (error) {
            console.error('Error fetching equipment:', error);
            return [];
        }
    }

    async createEquipment(equipmentData) {
        try {
            const created = await this._getJson(`${this.baseUrl}/equipment`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(equipmentData)
            });

            // Normalize to the same shape as getEquipment()
            return {
                id: created.toolID,
                name: created.toolName,
                serial_number: created.serialNumber,
                model_number: created.modelNumber,
                manufacturer: created.manufacturer,
                category_id: created.categoryID,
                warehouse_id: created.warehouseID,
                status: created.status,
                condition: created.condition || 'Good',
                daily_rental_cost: created.dailyRentalCost,
                purchase_cost: created.purchaseCost,
                purchase_date: created.purchaseDate,
                current_value: created.currentValue,
                location_code: created.locationCode,
                image_path: created.imagePath || '',
                instance_count: created.instanceCount ?? 0,
                instance_next_calibration_min: created.instanceNextCalibrationMin || null,
                last_certification_date: created.lastCalibration,
                certification_interval_months: created.calibrationInterval,
                certificate_expiry_date: created.nextCalibration,
                next_calibration_date: created.nextCalibration,
                requires_certification: !!created.requiresCertification,
                description: created.description
            };
        } catch (error) {
            console.error('Error creating equipment:', error);
            return null;
        }
    }

    async updateEquipment(id, equipmentData) {
        try {
            const response = await this._fetch(`${this.baseUrl}/equipment/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(equipmentData)
            });

            if (!response.ok) {
                const message = await response.text().catch(() => '');
                throw new Error(`${response.status} ${response.statusText}${message ? ` - ${message}` : ''}`);
            }

            // Fetch latest copy after update
            const refreshed = await this._getJson(`${this.baseUrl}/equipment/${id}`);
            const source = refreshed;

            return {
                id: source.toolID,
                name: source.toolName,
                serial_number: source.serialNumber,
                model_number: source.modelNumber,
                manufacturer: source.manufacturer,
                category_id: source.categoryID,
                warehouse_id: source.warehouseID,
                status: source.status,
                condition: source.condition || 'Good',
                daily_rental_cost: source.dailyRentalCost,
                purchase_cost: source.purchaseCost,
                purchase_date: source.purchaseDate,
                current_value: source.currentValue,
                location_code: source.locationCode,
                image_path: source.imagePath || '',
                instance_count: source.instanceCount ?? 0,
                instance_next_calibration_min: source.instanceNextCalibrationMin || null,
                last_certification_date: source.lastCalibration,
                certification_interval_months: source.calibrationInterval,
                certificate_expiry_date: source.nextCalibration,
                next_calibration_date: source.nextCalibration,
                requires_certification: !!source.requiresCertification,
                description: source.description
            };
        } catch (error) {
            console.error('Error updating equipment:', error);
            return null;
        }
    }

    async uploadEquipmentImage(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await this._fetch(`${this.baseUrl}/equipment/upload-image`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const message = await response.text().catch(() => 'Upload failed');
            throw new Error(message);
        }

        const payload = await response.json();
        return payload.path;
    }

    async getToolInstances(toolId) {
        try {
            return await this._getJson(`${this.baseUrl}/equipment/${toolId}/instances`);
        } catch (error) {
            console.error('Error fetching tool instances:', error);
            return [];
        }
    }

    async createToolInstance(toolId, instanceData) {
        try {
            return await this._getJson(`${this.baseUrl}/equipment/${toolId}/instances`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(instanceData || {})
            });
        } catch (error) {
            console.error('Error creating tool instance:', error);
            return null;
        }
    }

    async updateToolInstance(instanceId, instanceData) {
        try {
            return await this._getJson(`${this.baseUrl}/equipment/instances/${instanceId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(instanceData || {})
            });
        } catch (error) {
            console.error('Error updating tool instance:', error);
            return null;
        }
    }

    async deleteToolInstance(instanceId) {
        try {
            const response = await this._fetch(`${this.baseUrl}/equipment/instances/${instanceId}`, {
                method: 'DELETE'
            });
            return response.ok;
        } catch (error) {
            console.error('Error deleting tool instance:', error);
            return false;
        }
    }

    // --- WAREHOUSE ---
    async getWarehouses() {
        try {
            const data = await this._getJson(`${this.baseUrl}/warehouse`);
            return (data || []).map(w => ({
                id: w.warehouseID,
                name: w.warehouseName,
                grid_columns: w.gridColumns || 26,
                grid_rows: w.gridRows || 50
            }));
        } catch (error) {
            console.error('Error fetching warehouses:', error);
            return [];
        }
    }

    async getWarehouseTools(warehouseId) {
        try {
            const data = await this._getJson(`${this.baseUrl}/warehouse/${warehouseId}/tools`);
            return (data || []).map(t => ({
                id: t.toolInstanceID || t.toolID,
                name: t.toolName,
                serial: t.serialNumber,
                status: t.status,
                location: t.locationCode
            }));
        } catch (error) {
            console.error('Error fetching warehouse tools:', error);
            return [];
        }
    }

    async getWarehouseLocations(warehouseId) {
        try {
            return await this._getJson(`${this.baseUrl}/warehouse/${warehouseId}/locations`);
        } catch (error) {
            console.error('Error fetching warehouse locations:', error);
            return [];
        }
    }

    async generateWarehouseLocations(warehouseId, payload) {
        try {
            return await this._getJson(`${this.baseUrl}/warehouse/${warehouseId}/locations/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload || {})
            });
        } catch (error) {
            console.error('Error generating warehouse locations:', error);
            throw error;
        }
    }

    async getWarehouseInstances(warehouseId) {
        try {
            return await this._getJson(`${this.baseUrl}/warehouse/${warehouseId}/instances`);
        } catch (error) {
            console.error('Error fetching warehouse instances:', error);
            return [];
        }
    }

    async assignToolToLocation(toolId, warehouseId, locationCode) {
        try {
            const payload = {
                toolID: toolId,
                warehouseID: warehouseId,
                locationCode: locationCode
            };
            const response = await this._fetch(`${this.baseUrl}/warehouse/assign`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            return response.ok;
        } catch (error) {
            console.error('Error assigning tool:', error);
            return false;
        }
    }

    // --- DASHBOARD UTILS ---
    async getCalibrationAlerts() {
        try {
            return await this._getJson(`${this.baseUrl}/equipment/calibration-alerts`);
        } catch (error) {
            console.error('Error fetching calibration alerts:', error);
            return [];
        }
    }

}

window.sqlAPI = new SQLServerAPI();

//// SQL Server API Adapter
//// This replaces the simulation and calls the real C# API endpoints

//class SQLServerAPI {
//    constructor() {
//        this.isConnected = true;
//        this.baseUrl = '/api';
//        this.currentUser = null;
//        this.init();
//    }

//    init() {
//        console.log('SQL Server API Adapter initialized');
//        this.getCurrentUser();
//    }

//    // --- EQUIPMENT ---
//    async getEquipment() {
//        try {
//            const response = await fetch(`${this.baseUrl}/equipment`);
//            const data = await response.json();
//            return data.map(item => ({
//                id: item.toolID,
//                name: item.toolName,
//                serial_number: item.serialNumber,
//                model_number: item.modelNumber,
//                manufacturer: item.manufacturer,
//                category_id: item.categoryID,
//                status: item.status,
//                condition: item.condition || 'Good',
//                daily_rental_cost: item.dailyRentalCost,
//                image_path: item.imagePath || '',
//                next_calibration_date: item.nextCalibration
//            }));
//        } catch (error) {
//            console.error('Error fetching equipment:', error);
//            return [];
//        }
//    }

//    async createEquipment(equipmentData) {
//        try {
//            const payload = {
//                toolID: 0,
//                toolName: equipmentData.name,
//                serialNumber: equipmentData.serial_number || "N/A",
//                modelNumber: equipmentData.model_number || "N/A",
//                manufacturer: equipmentData.manufacturer || "Generic",
//                categoryID: equipmentData.category_id || 1,
//                warehouseID: 1,
//                status: 'Available',
//                dailyRentalCost: parseFloat(equipmentData.daily_rental_cost) || 0,
//                description: equipmentData.description || '',
//                requiresCertification: false,
//                purchaseDate: new Date().toISOString()
//            };

//            const response = await fetch(`${this.baseUrl}/equipment`, {
//                method: 'POST',
//                headers: { 'Content-Type': 'application/json' },
//                body: JSON.stringify(payload)
//            });

//            if (response.ok) {
//                console.log("Item Created in SQL Database!");
//                return await response.json();
//            } else {
//                console.error("Server refused:", await response.text());
//            }
//        } catch (error) {
//            console.error('Error creating equipment:', error);
//        }
//        return null;
//    }

//    async deleteEquipment(id) {
//        try {
//            const response = await fetch(`${this.baseUrl}/equipment/${id}`, {
//                method: 'DELETE'
//            });
//            return response.ok;
//        } catch (error) {
//            console.error('Error deleting equipment:', error);
//            return false;
//        }
//    }

//    // --- RENTALS ---
//    async getRentals() {
//        try {
//            const response = await fetch(`${this.baseUrl}/rentals`);
//            return await response.json();
//        } catch (error) {
//            console.error('Error fetching rentals:', error);
//            return [];
//        }
//    }

//    // UPDATED: Simply passes the data through
//    async createRental(rentalData) {
//        try {
//            const response = await fetch(`${this.baseUrl}/rentals`, {
//                method: 'POST',
//                headers: { 'Content-Type': 'application/json' },
//                body: JSON.stringify(rentalData)
//            });

//            if (response.ok) {
//                console.log("Rental Created!");
//                return await response.json();
//            } else {
//                console.error("Rental Creation Failed:", await response.text());
//                return null;
//            }
//        } catch (error) {
//            console.error('Error creating rental:', error);
//            return null;
//        }
//    }

//    async updateRentalStatus(id, action) {
//        try {
//            const response = await fetch(`${this.baseUrl}/rentals/${id}/${action}`, {
//                method: 'POST',
//                headers: { 'Content-Type': 'application/json' }
//            });
//            return response.ok;
//        } catch (error) {
//            console.error(`Error performing ${action}:`, error);
//            return false;
//        }
//    }

//    // --- WAREHOUSE ---
//    async getWarehouses() {
//        try {
//            const response = await fetch(`${this.baseUrl}/warehouse`);
//            const data = await response.json();
//            return data.map(w => ({
//                id: w.warehouseID,
//                name: w.warehouseName,
//                grid_columns: w.gridColumns || 26,
//                grid_rows: w.gridRows || 50
//            }));
//        } catch (error) {
//            console.error('Error fetching warehouses:', error);
//            return [];
//        }
//    }

//    async getWarehouseTools(warehouseId) {
//        try {
//            const response = await fetch(`${this.baseUrl}/warehouse/${warehouseId}/tools`);
//            const data = await response.json();
//            return data.map(t => ({
//                id: t.toolID,
//                name: t.toolName,
//                serial: t.serialNumber,
//                status: t.status,
//                location: t.locationCode
//            }));
//        } catch (error) {
//            console.error('Error fetching warehouse tools:', error);
//            return [];
//        }
//    }

//    async assignToolToLocation(toolId, warehouseId, locationCode) {
//        try {
//            const payload = {
//                toolID: toolId,
//                warehouseID: warehouseId,
//                locationCode: locationCode
//            };
//            const response = await fetch(`${this.baseUrl}/warehouse/assign`, {
//                method: 'POST',
//                headers: { 'Content-Type': 'application/json' },
//                body: JSON.stringify(payload)
//            });
//            return response.ok;
//        } catch (error) {
//            console.error('Error assigning tool:', error);
//            return false;
//        }
//    }

//    // --- UTILS ---
//    async getCalibrationAlerts() {
//        try {
//            const response = await fetch(`${this.baseUrl}/equipment/calibration-alerts`);
//            return await response.json();
//        } catch (error) {
//            return [];
//        }
//    }

//    async getCurrentUser() {
//        this.currentUser = {
//            id: 1,
//            full_name: 'Admin User',
//            role: 'Admin'
//        };
//        return this.currentUser;
//    }
//}

//window.sqlAPI = new SQLServerAPI();

//PI = new SQLServerAPI();
