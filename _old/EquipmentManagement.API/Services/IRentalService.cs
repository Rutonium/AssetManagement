using EquipmentManagement.API.Models;

namespace EquipmentManagement.API.Services
{
    public interface IRentalService
    {
        Task<IEnumerable<Rental>> GetAllRentalsAsync();
        Task<Rental?> GetRentalByIdAsync(int id);
        Task<Rental> CreateRentalAsync(Rental rental);
        Task<bool> UpdateRentalAsync(Rental rental);
        Task<bool> DeleteRentalAsync(int id);
        Task<bool> ApproveRentalAsync(int rentalId, int approvedBy);
        Task<bool> ExtendRentalAsync(int rentalId, DateTime newEndDate);
        Task<bool> ProcessReturnAsync(int rentalId, string returnCondition, string? returnNotes = null);
        Task<IEnumerable<Rental>> GetRentalsByEmployeeAsync(int employeeId);
        Task<IEnumerable<Rental>> GetRentalsByStatusAsync(string status);
        Task<IEnumerable<Rental>> GetOverdueRentalsAsync();
        Task<Dictionary<string, int>> GetRentalStatusCountsAsync();
        Task<decimal> CalculateTotalRevenueAsync(DateTime? startDate = null, DateTime? endDate = null);
    }
}