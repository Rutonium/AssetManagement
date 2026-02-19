// --- START OF FILE Controllers/WarehouseController.cs ---
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using EquipmentManagement.API.Data;
using EquipmentManagement.API.Models;

namespace EquipmentManagement.API.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    public class WarehouseController : ControllerBase
    {
        private readonly AssetManagementContext _context;

        public WarehouseController(AssetManagementContext context)
        {
            _context = context;
        }

        [HttpGet]
        public async Task<ActionResult<IEnumerable<Warehouse>>> GetWarehouses()
        {
            return await _context.Warehouses.ToListAsync();
        }

        [HttpGet("{id}/tools")]
        public async Task<ActionResult<IEnumerable<Tool>>> GetWarehouseTools(int id)
        {
            return await _context.Tools
                .Where(t => t.WarehouseID == id && t.Status != "Retired")
                .ToListAsync();
        }

        // --- NEW ENDPOINT: ASSIGN LOCATION ---
        [HttpPost("assign")]
        public async Task<IActionResult> AssignToolLocation([FromBody] ToolLocationAssignmentDto request)
        {
            var tool = await _context.Tools.FindAsync(request.ToolID);
            if (tool == null) return NotFound("Tool not found");

            // Update the main Tool record
            tool.LocationCode = request.LocationCode;
            tool.WarehouseID = request.WarehouseID;
            tool.UpdatedDate = DateTime.Now;

            // Optional: Log history to ToolLocations table
            var locationRecord = new ToolLocation
            {
                ToolID = tool.ToolID,
                // In a real scenario, you'd map "A-1" to an actual LocationID from WarehouseLocations table
                // For this quick implementation, we assume we have a LocationID or skip foreign key strictness
                // This is a simplification:
                LocationID = 1, // Placeholder: You usually need to lookup the LocationID based on Code "A-1"
                AssignedDate = DateTime.Now,
                IsCurrent = true,
                Notes = "Assigned via Warehouse Grid"
            };

            // _context.ToolLocations.Add(locationRecord); // Uncomment if ToolLocations table is fully populated

            await _context.SaveChangesAsync();
            return Ok(new { message = $"Tool {tool.ToolName} assigned to {request.LocationCode}" });
        }
    }

    public class ToolLocationAssignmentDto
    {
        public int ToolID { get; set; }
        public int WarehouseID { get; set; }
        public string LocationCode { get; set; }
    }
}

//using Microsoft.AspNetCore.Mvc;
//using Microsoft.EntityFrameworkCore;
//using EquipmentManagement.API.Data;
//using EquipmentManagement.API.Models;

//namespace EquipmentManagement.API.Controllers
//{
//    [Route("api/[controller]")]
//    [ApiController]
//    public class WarehouseController : ControllerBase
//    {
//        private readonly AssetManagementContext _context;

//        public WarehouseController(AssetManagementContext context)
//        {
//            _context = context;
//        }

//        // GET: api/Warehouse
//        [HttpGet]
//        public async Task<ActionResult<IEnumerable<Warehouse>>> GetWarehouses()
//        {
//            return await _context.Warehouses.ToListAsync();
//        }

//        // GET: api/Warehouse/5
//        [HttpGet("{id}")]
//        public async Task<ActionResult<Warehouse>> GetWarehouse(int id)
//        {
//            var warehouse = await _context.Warehouses.FindAsync(id);

//            if (warehouse == null)
//            {
//                return NotFound();
//            }

//            return warehouse;
//        }

//        // GET: api/Warehouse/5/tools
//        // Gets all tools assigned to this warehouse to show occupancy
//        [HttpGet("{id}/tools")]
//        public async Task<ActionResult<IEnumerable<Tool>>> GetWarehouseTools(int id)
//        {
//            return await _context.Tools
//                .Where(t => t.WarehouseID == id && t.Status != "Retired")
//                .ToListAsync();
//        }
//    }

//// Controllers/WarehouseController.cs
//[HttpPost("assign")]
//        public async Task<IActionResult> AssignToolLocation([FromBody] ToolLocationAssignmentDto request)
//        {
//            // 1. Find the tool
//            var tool = await _context.Tools.FindAsync(request.ToolID);
//            if (tool == null) return NotFound("Tool not found");

//            // 2. Update the Tool's location code
//            tool.LocationCode = request.LocationCode;
//            tool.WarehouseID = request.WarehouseID;

//            // 3. (Optional) Create a history record in ToolLocations table
//            var history = new ToolLocation
//            {
//                ToolID = tool.ToolID,
//                // You'll need logic to map "A-1" to a LocationID if using the relational table
//                // For now, simpler to update the Tool entity directly
//                AssignedDate = DateTime.Now,
//                IsCurrent = true
//            };

//            _context.ToolLocations.Add(history);
//            await _context.SaveChangesAsync();

//            return Ok(new { message = $"Tool {tool.ToolName} assigned to {request.LocationCode}" });
//        }

//// DTO Class
//public class ToolLocationAssignmentDto
//    {
//        public int ToolID { get; set; }
//        public int WarehouseID { get; set; }
//        public string LocationCode { get; set; } // e.g., "A-1"
//    }
//}


