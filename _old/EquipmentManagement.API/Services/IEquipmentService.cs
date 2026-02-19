using EquipmentManagement.API.Models;

namespace EquipmentManagement.API.Services
{
    public interface IEquipmentService
    {
        Task<IEnumerable<Tool>> GetAllEquipmentAsync();
        Task<Tool?> GetEquipmentByIdAsync(int id);
        Task<IEnumerable<Tool>> GetAvailableEquipmentAsync();
        Task<IEnumerable<object>> GetCalibrationAlertsAsync(int daysAhead = 30);
        Task<Tool> CreateEquipmentAsync(Tool equipment);
        Task<bool> UpdateEquipmentAsync(Tool equipment);
        Task<bool> DeleteEquipmentAsync(int id);
        Task<IEnumerable<Tool>> GetEquipmentByCategoryAsync(int categoryId);
        Task<IEnumerable<Tool>> SearchEquipmentAsync(string searchTerm);
        Task<bool> UpdateEquipmentStatusAsync(int id, string status);
        Task<IEnumerable<Tool>> GetEquipmentRequiringCalibrationAsync();
        Task<Dictionary<string, int>> GetEquipmentStatusCountsAsync();
    }
}