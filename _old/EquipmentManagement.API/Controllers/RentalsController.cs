using Microsoft.AspNetCore.Mvc;
using EquipmentManagement.API.Models;
using EquipmentManagement.API.Services;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using System;

namespace EquipmentManagement.API.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    public class RentalsController : ControllerBase
    {
        private readonly IRentalService _rentalService;

        public RentalsController(IRentalService rentalService)
        {
            _rentalService = rentalService;
        }

        // GET: api/Rentals
        [HttpGet]
        public async Task<ActionResult<IEnumerable<Rental>>> GetRentals()
        {
            var rentals = await _rentalService.GetAllRentalsAsync();
            return Ok(rentals);
        }

        // GET: api/Rentals/5
        [HttpGet("{id}")]
        public async Task<ActionResult<Rental>> GetRental(int id)
        {
            var rental = await _rentalService.GetRentalByIdAsync(id);
            if (rental == null) return NotFound();
            return Ok(rental);
        }

        // POST: api/Rentals
        // UPDATED: Now accepts a DTO to avoid "RentalNumber Required" errors
        [HttpPost]
        public async Task<ActionResult<Rental>> CreateRental([FromBody] CreateRentalDto request)
        {
            try
            {
                // Map the simple DTO to the complex Database Entity
                var rental = new Rental
                {
                    EmployeeID = request.EmployeeID,
                    Purpose = request.Purpose,
                    ProjectCode = request.ProjectCode,
                    StartDate = request.StartDate,
                    EndDate = request.EndDate,
                    Notes = request.Notes,
                    Status = "Pending",
                    RentalNumber = "TEMP", // Temporary value, Service will overwrite it
                    RentalItems = request.RentalItems.Select(i => new RentalItem
                    {
                        ToolID = i.ToolID,
                        Quantity = i.Quantity,
                        DailyCost = i.DailyCost
                        // We do NOT set 'Tool' or 'Rental' objects here, EF Core handles the IDs
                    }).ToList()
                };

                // The Service will generate the real RentalNumber and save to DB
                var createdRental = await _rentalService.CreateRentalAsync(rental);

                return CreatedAtAction(nameof(GetRental), new { id = createdRental.RentalID }, createdRental);
            }
            catch (Exception ex)
            {
                return BadRequest($"Error creating rental: {ex.Message}");
            }
        }
        // POST: api/Rentals/5/approve
        [HttpPost("{id}/approve")]
        public async Task<IActionResult> ApproveRental(int id)
        {
            // Hardcoded Admin ID 1 for now until we have real login
            var success = await _rentalService.ApproveRentalAsync(id, 1);
            if (!success) return BadRequest("Could not approve rental.");
            return Ok(new { message = "Rental Approved" });
        }

        // POST: api/Rentals/5/extend
        [HttpPost("{id}/extend")]
        public async Task<IActionResult> ExtendRental(int id, [FromBody] ExtensionRequest request)
        {
            var success = await _rentalService.ExtendRentalAsync(id, request.NewEndDate);
            if (!success) return BadRequest("Could not extend rental.");
            return Ok(new { message = "Rental Extended" });
        }

        // POST: api/Rentals/5/cancel
        [HttpPost("{id}/cancel")]
        public async Task<IActionResult> CancelRental(int id)
        {
            // We use the UpdateRentalAsync or create a specific Cancel method
            // For simplicity, we'll fetch, update status, and save.
            var rental = await _rentalService.GetRentalByIdAsync(id);
            if (rental == null) return NotFound();

            rental.Status = "Cancelled";
            await _rentalService.UpdateRentalAsync(rental);

            return Ok(new { message = "Rental Cancelled" });
        }


        [HttpPost("{id}/return")]
        public async Task<IActionResult> ProcessReturn(int id, [FromBody] ReturnRequest request)
        {
            var success = await _rentalService.ProcessReturnAsync(id, request.Condition, request.Notes);
            if (!success) return BadRequest("Could not process return. Check if rental is active.");
            return Ok(new { message = "Return processed successfully" });
        }
    }

    // --- Data Transfer Objects (DTOs) ---
    // These match exactly what api-simulation.js sends
    public class CreateRentalDto
    {
        public int EmployeeID { get; set; }
        public string Purpose { get; set; } = string.Empty;
        public string? ProjectCode { get; set; }
        public DateTime StartDate { get; set; }
        public DateTime EndDate { get; set; }
        public string? Notes { get; set; }
        public string? Status { get; set; } // Added to catch 'Pending' sent from JS
        public List<CreateRentalItemDto> RentalItems { get; set; } = new();
    }

    public class CreateRentalItemDto
    {
        public int ToolID { get; set; }
        public int Quantity { get; set; }
        public decimal? DailyCost { get; set; }
    }

    public class ExtensionRequest
    {
        public DateTime NewEndDate { get; set; }
    }
    public class ReturnRequest
    {
        public string Condition { get; set; } = string.Empty;
        public string? Notes { get; set; }
    }
}