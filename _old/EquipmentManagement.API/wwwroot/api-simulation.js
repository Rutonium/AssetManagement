// SQL Server API Adapter
class SQLServerAPI {
    constructor() {
        this.baseUrl = '/api';
        this.currentUser = {
            id: 1,
            full_name: 'Admin User',
            role: 'Admin'
        };
    }

    async _getJson(url, init) {
        const response = await fetch(url, init);
        if (!response.ok) {
            const message = await response.text().catch(() => '');
            throw new Error(`${response.status} ${response.statusText}${message ? ` - ${message}` : ''}`);
        }
        return response.json();
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

    async createRental(rentalData) {
        try {
            const response = await fetch(`${this.baseUrl}/rentals`, {
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

    async updateRentalStatus(id, action) {
        try {
            const response = await fetch(`${this.baseUrl}/rentals/${id}/${action}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            return response.ok;
        } catch (error) {
            console.error(`Error performing ${action}:`, error);
            return false;
        }
    }

    async returnRental(id, condition, notes) {
        try {
            const payload = { condition: condition, notes: notes };
            const response = await fetch(`${this.baseUrl}/rentals/${id}/return`, {
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
            const response = await fetch(`${this.baseUrl}/rentals/${id}/extend`, {
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
            const response = await fetch(`${this.baseUrl}/equipment/${id}`, {
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

        const response = await fetch(`${this.baseUrl}/equipment/upload-image`, {
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
                id: t.toolID,
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

    async assignToolToLocation(toolId, warehouseId, locationCode) {
        try {
            const payload = {
                toolID: toolId,
                warehouseID: warehouseId,
                locationCode: locationCode
            };
            const response = await fetch(`${this.baseUrl}/warehouse/assign`, {
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

    // --- USER (Fixed: This was missing) ---
    async getCurrentUser() {
        return this.currentUser;
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
