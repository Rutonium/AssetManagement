using Microsoft.EntityFrameworkCore;
using EquipmentManagement.API.Data;
using EquipmentManagement.API.Models;

namespace EquipmentManagement.API.Services
{
    public class RentalService : IRentalService
    {
        private readonly AssetManagementContext _context;
        private readonly ILogger<RentalService> _logger;

        public RentalService(AssetManagementContext context, ILogger<RentalService> logger)
        {
            _context = context;
            _logger = logger;
        }

        public async Task<IEnumerable<Rental>> GetAllRentalsAsync()
        {
            try
            {
                return await _context.Rentals
                    .Include(r => r.RentalItems)
                        .ThenInclude(ri => ri.Tool)
                    .OrderByDescending(r => r.CreatedDate)
                    .ToListAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving all rentals");
                throw;
            }
        }

        public async Task<Rental?> GetRentalByIdAsync(int id)
        {
            try
            {
                return await _context.Rentals
                    .Include(r => r.RentalItems)
                        .ThenInclude(ri => ri.Tool)
                    .FirstOrDefaultAsync(r => r.RentalID == id);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving rental with ID {RentalId}", id);
                throw;
            }
        }

        public async Task<bool> ExtendRentalAsync(int rentalId, DateTime newEndDate)
        {
            try
            {
                var rental = await _context.Rentals
                    .Include(r => r.RentalItems) // Include items to recalculate cost
                    .FirstOrDefaultAsync(r => r.RentalID == rentalId);

                if (rental == null || rental.Status != "Active") return false;

                // Update Date
                rental.EndDate = newEndDate;
                rental.UpdatedDate = DateTime.Now;

                // Recalculate Total Cost based on new duration
                int days = (newEndDate - rental.StartDate).Days;
                if (days < 1) days = 1;

                decimal newTotal = 0;
                foreach (var item in rental.RentalItems)
                {
                    newTotal += (item.DailyCost ?? 0) * days * item.Quantity;
                }
                rental.TotalCost = newTotal;

                _context.Entry(rental).State = EntityState.Modified;
                await _context.SaveChangesAsync();

                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error extending rental {RentalId}", rentalId);
                throw;
            }
        }
        public async Task<Rental> CreateRentalAsync(Rental rental)
        {
            try
            {
                // Generate rental number
                rental.RentalNumber = await GenerateRentalNumberAsync();
                
                // Set initial status
                rental.Status = "Pending";
                rental.CreatedDate = DateTime.Now;
                rental.UpdatedDate = DateTime.Now;

                _context.Rentals.Add(rental);
                await _context.SaveChangesAsync();

                _logger.LogInformation("Created new rental with ID {RentalId}", rental.RentalID);
                return rental;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error creating rental");
                throw;
            }
        }

        public async Task<bool> UpdateRentalAsync(Rental rental)
        {
            try
            {
                var existingRental = await _context.Rentals.FindAsync(rental.RentalID);
                
                if (existingRental == null)
                    return false;

                _context.Entry(existingRental).CurrentValues.SetValues(rental);
                existingRental.UpdatedDate = DateTime.Now;

                await _context.SaveChangesAsync();

                _logger.LogInformation("Updated rental with ID {RentalId}", rental.RentalID);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error updating rental with ID {RentalId}", rental.RentalID);
                throw;
            }
        }

        public async Task<bool> DeleteRentalAsync(int id)
        {
            try
            {
                var rental = await _context.Rentals.FindAsync(id);
                
                if (rental == null)
                    return false;

                _context.Rentals.Remove(rental);
                await _context.SaveChangesAsync();

                _logger.LogInformation("Deleted rental with ID {RentalId}", id);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error deleting rental with ID {RentalId}", id);
                throw;
            }
        }

        public async Task<bool> ApproveRentalAsync(int rentalId, int approvedBy)
        {
            try
            {
                var rental = await _context.Rentals.FindAsync(rentalId);
                
                if (rental == null || rental.Status != "Pending")
                    return false;

                rental.Status = "Approved";
                rental.ApprovedBy = approvedBy;
                rental.ApprovalDate = DateTime.Now;
                rental.UpdatedDate = DateTime.Now;

                await _context.SaveChangesAsync();

                _logger.LogInformation("Approved rental {RentalId} by employee {ApprovedBy}", rentalId, approvedBy);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error approving rental {RentalId}", rentalId);
                throw;
            }
        }

        public async Task<bool> ProcessReturnAsync(int rentalId, string returnCondition, string? returnNotes = null)
        {
            try
            {
                var rental = await _context.Rentals
                    .Include(r => r.RentalItems)
                    .FirstOrDefaultAsync(r => r.RentalID == rentalId);

                if (rental == null || rental.Status != "Active")
                    return false;

                // Update rental status
                rental.Status = "Returned";
                rental.ActualEnd = DateTime.Now;
                rental.ReturnCondition = returnCondition;
                rental.UpdatedDate = DateTime.Now;

                if (!string.IsNullOrEmpty(returnNotes))
                {
                    rental.Notes = string.IsNullOrEmpty(rental.Notes) ? 
                        returnNotes : rental.Notes + "\n" + returnNotes;
                }

                // Update tool statuses
                foreach (var item in rental.RentalItems)
                {
                    var tool = await _context.Tools.FindAsync(item.ToolID);
                    if (tool != null)
                    {
                        tool.Status = "Available";
                        tool.UpdatedDate = DateTime.Now;
                    }
                }

                await _context.SaveChangesAsync();

                _logger.LogInformation("Processed return for rental {RentalId}", rentalId);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error processing return for rental {RentalId}", rentalId);
                throw;
            }
        }

        public async Task<IEnumerable<Rental>> GetRentalsByEmployeeAsync(int employeeId)
        {
            try
            {
                return await _context.Rentals
                    .Include(r => r.RentalItems)
                        .ThenInclude(ri => ri.Tool)
                    .Where(r => r.EmployeeID == employeeId)
                    .OrderByDescending(r => r.CreatedDate)
                    .ToListAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving rentals for employee {EmployeeId}", employeeId);
                throw;
            }
        }

        public async Task<IEnumerable<Rental>> GetRentalsByStatusAsync(string status)
        {
            try
            {
                return await _context.Rentals
                    .Include(r => r.RentalItems)
                        .ThenInclude(ri => ri.Tool)
                    .Where(r => r.Status == status)
                    .OrderByDescending(r => r.CreatedDate)
                    .ToListAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving rentals with status {Status}", status);
                throw;
            }
        }

        public async Task<IEnumerable<Rental>> GetOverdueRentalsAsync()
        {
            try
            {
                var today = DateTime.Now.Date;
                
                return await _context.Rentals
                    .Include(r => r.RentalItems)
                        .ThenInclude(ri => ri.Tool)
                    .Where(r => r.Status == "Active" && r.EndDate < today)
                    .OrderBy(r => r.EndDate)
                    .ToListAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving overdue rentals");
                throw;
            }
        }

        public async Task<Dictionary<string, int>> GetRentalStatusCountsAsync()
        {
            try
            {
                var counts = await _context.Rentals
                    .GroupBy(r => r.Status)
                    .Select(g => new { Status = g.Key, Count = g.Count() })
                    .ToDictionaryAsync(x => x.Status, x => x.Count);

                return counts;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error retrieving rental status counts");
                throw;
            }
        }

        public async Task<decimal> CalculateTotalRevenueAsync(DateTime? startDate = null, DateTime? endDate = null)
        {
            try
            {
                var query = _context.Rentals.AsQueryable();

                if (startDate.HasValue)
                    query = query.Where(r => r.CreatedDate >= startDate.Value);

                if (endDate.HasValue)
                    query = query.Where(r => r.CreatedDate <= endDate.Value);

                var totalRevenue = await query
                    .Where(r => r.Status == "Returned" || r.Status == "Active")
                    .SumAsync(r => r.TotalCost ?? 0);

                return totalRevenue;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error calculating total revenue");
                throw;
            }
        }

        private async Task<string> GenerateRentalNumberAsync()
        {
            var lastRental = await _context.Rentals
                .OrderByDescending(r => r.RentalID)
                .FirstOrDefaultAsync();

            int nextNumber = 1;
            if (lastRental != null)
            {
                var lastNumber = lastRental.RentalNumber.Replace("RNT-", "");
                if (int.TryParse(lastNumber, out int lastNum))
                {
                    nextNumber = lastNum + 1;
                }
            }

            return $"RNT-{nextNumber:D3}";
        }
    }
}