using Microsoft.EntityFrameworkCore;
using EquipmentManagement.API.Data;
using EquipmentManagement.API.Models;

namespace EquipmentManagement.API.Services
{
    public class EquipmentService : IEquipmentService
    {
        private readonly AssetManagementContext _context;
        private readonly ILogger<EquipmentService> _logger;

        public EquipmentService(AssetManagementContext context, ILogger<EquipmentService> logger)
        {
            _context = context;
            _logger = logger;
        }

        public async Task<IEnumerable<Tool>> GetAllEquipmentAsync()
        {
            try
            {
                return await _context.Tools
                    .Include(t => t.Category)
                    .Include(t => t.Warehouse)
                    .OrderBy(t => t.ToolName)
                    .ToListAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving all equipment");
                throw;
            }
        }

        public async Task<Tool?> GetEquipmentByIdAsync(int id)
        {
            try
            {
                return await _context.Tools
                    .Include(t => t.Category)
                    .Include(t => t.Warehouse)
                    .Include(t => t.RentalItems)
                    .Include(t => t.Certificates)
                    .Include(t => t.ServiceRecords)
                    .FirstOrDefaultAsync(t => t.ToolID == id);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving equipment with ID {EquipmentId}", id);
                throw;
            }
        }

        public async Task<IEnumerable<Tool>> GetAvailableEquipmentAsync()
        {
            try
            {
                return await _context.Tools
                    .Include(t => t.Category)
                    .Where(t => t.Status == "Available")
                    .OrderBy(t => t.ToolName)
                    .ToListAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving available equipment");
                throw;
            }
        }

        public async Task<IEnumerable<object>> GetCalibrationAlertsAsync(int daysAhead = 30)
        {
            try
            {
                var today = DateTime.Now.Date;
                var futureDate = today.AddDays(daysAhead);

                var alerts = await _context.Tools
                    .Where(t => t.NextCalibration.HasValue && 
                               t.NextCalibration <= futureDate)
                    .Select(t => new
                    {
                        ToolID = t.ToolID,
                        ToolName = t.ToolName,
                        SerialNumber = t.SerialNumber,
                        NextCalibration = t.NextCalibration,
                        DaysUntilCalibration = t.NextCalibration.HasValue ? 
                            (t.NextCalibration.Value - today).Days : -1,
                        AlertType = t.NextCalibration < today ? "Overdue" :
                                   (t.NextCalibration.Value - today).Days <= 7 ? "Due Soon" :
                                   (t.NextCalibration.Value - today).Days <= daysAhead ? "Upcoming" : "OK"
                    })
                    .OrderBy(a => a.NextCalibration)
                    .ToListAsync();

                return alerts;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving calibration alerts");
                throw;
            }
        }

        public async Task<Tool> CreateEquipmentAsync(Tool equipment)
        {
            try
            {
                _context.Tools.Add(equipment);
                await _context.SaveChangesAsync();
                
                _logger.LogInformation("Created new equipment with ID {EquipmentId}", equipment.ToolID);
                return equipment;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error creating equipment");
                throw;
            }
        }

        public async Task<bool> UpdateEquipmentAsync(Tool equipment)
        {
            try
            {
                var existingEquipment = await _context.Tools.FindAsync(equipment.ToolID);
                
                if (existingEquipment == null)
                    return false;

                // Update properties
                _context.Entry(existingEquipment).CurrentValues.SetValues(equipment);
                existingEquipment.UpdatedDate = DateTime.Now;

                await _context.SaveChangesAsync();
                
                _logger.LogInformation("Updated equipment with ID {EquipmentId}", equipment.ToolID);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error updating equipment with ID {EquipmentId}", equipment.ToolID);
                throw;
            }
        }

        public async Task<bool> DeleteEquipmentAsync(int id)
        {
            try
            {
                var equipment = await _context.Tools.FindAsync(id);
                
                if (equipment == null)
                    return false;

                _context.Tools.Remove(equipment);
                await _context.SaveChangesAsync();
                
                _logger.LogInformation("Deleted equipment with ID {EquipmentId}", id);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error deleting equipment with ID {EquipmentId}", id);
                throw;
            }
        }

        public async Task<IEnumerable<Tool>> GetEquipmentByCategoryAsync(int categoryId)
        {
            try
            {
                return await _context.Tools
                    .Include(t => t.Category)
                    .Where(t => t.CategoryID == categoryId)
                    .OrderBy(t => t.ToolName)
                    .ToListAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving equipment by category {CategoryId}", categoryId);
                throw;
            }
        }

        public async Task<IEnumerable<Tool>> SearchEquipmentAsync(string searchTerm)
        {
            try
            {
                var term = searchTerm.ToLower();
                
                return await _context.Tools
                    .Include(t => t.Category)
                    .Where(t => 
                        t.ToolName.ToLower().Contains(term) ||
                        (t.SerialNumber != null && t.SerialNumber.ToLower().Contains(term)) ||
                        (t.ModelNumber != null && t.ModelNumber.ToLower().Contains(term)) ||
                        (t.Manufacturer != null && t.Manufacturer.ToLower().Contains(term)) ||
                        (t.Description != null && t.Description.ToLower().Contains(term)))
                    .OrderBy(t => t.ToolName)
                    .ToListAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error searching equipment with term {SearchTerm}", searchTerm);
                throw;
            }
        }

        public async Task<bool> UpdateEquipmentStatusAsync(int id, string status)
        {
            try
            {
                var equipment = await _context.Tools.FindAsync(id);
                
                if (equipment == null)
                    return false;

                equipment.Status = status;
                equipment.UpdatedDate = DateTime.Now;

                await _context.SaveChangesAsync();
                
                _logger.LogInformation("Updated status for equipment {EquipmentId} to {Status}", id, status);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error updating equipment status for ID {EquipmentId}", id);
                throw;
            }
        }

        public async Task<IEnumerable<Tool>> GetEquipmentRequiringCalibrationAsync()
        {
            try
            {
                var today = DateTime.Now.Date;
                
                return await _context.Tools
                    .Where(t => t.RequiresCertification && 
                               t.NextCalibration.HasValue &&
                               t.NextCalibration <= today.AddDays(30))
                    .OrderBy(t => t.NextCalibration)
                    .ToListAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving equipment requiring calibration");
                throw;
            }
        }

        public async Task<Dictionary<string, int>> GetEquipmentStatusCountsAsync()
        {
            try
            {
                var counts = await _context.Tools
                    .GroupBy(t => t.Status)
                    .Select(g => new { Status = g.Key, Count = g.Count() })
                    .ToDictionaryAsync(x => x.Status, x => x.Count);

                return counts;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving equipment status counts");
                throw;
            }
        }
    }
}