using EquipmentManagement.API.Data;
using EquipmentManagement.API.Models;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading.Tasks;

namespace EquipmentManagement.API.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    public class EquipmentController : ControllerBase
    {
        private readonly AssetManagementContext _context;
        private readonly IWebHostEnvironment _environment;

        public EquipmentController(AssetManagementContext context, IWebHostEnvironment environment)
        {
            _context = context;
            _environment = environment;
        }

        private async Task<string> GenerateNextRegistrationNumberAsync()
        {
            var year = DateTime.Today.Year;
            var prefix = $"SP{year}-";

            // Pull existing numbers for the current year and compute the next sequence.
            // This keeps DB schema unchanged by reusing SerialNumber as the registration number.
            var existing = await _context.Tools
                .Where(t => t.SerialNumber != null && t.SerialNumber.StartsWith(prefix))
                .Select(t => t.SerialNumber!)
                .ToListAsync();

            var maxSeq = 0;
            foreach (var serial in existing)
            {
                // Expected format: SP2025-0004
                var parts = serial.Split('-', StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length != 2) continue;

                if (int.TryParse(parts[1], out var seq))
                {
                    if (seq > maxSeq) maxSeq = seq;
                }
            }

            var nextSeq = maxSeq + 1;
            return $"{prefix}{nextSeq:D4}";
        }

        // GET: api/Equipment
        [HttpGet]
        public async Task<ActionResult<IEnumerable<Tool>>> GetTools()
        {
            return await _context.Tools.ToListAsync();
        }

        private void ApplyCertificationSchedule(Tool tool)
        {
            if (!tool.RequiresCertification)
            {
                tool.CalibrationInterval = null;
                tool.LastCalibration = null;
                tool.NextCalibration = null;
                return;
            }

            if (!tool.LastCalibration.HasValue)
            {
                tool.LastCalibration = DateTime.Today;
            }

            if (tool.CalibrationInterval.HasValue && tool.CalibrationInterval.Value > 0)
            {
                tool.NextCalibration = tool.LastCalibration.Value.AddMonths(tool.CalibrationInterval.Value);
            }
            else
            {
                tool.NextCalibration = null;
            }
        }

        // GET: api/Equipment/calibration-alerts
        [HttpGet("calibration-alerts")]
        public async Task<ActionResult<IEnumerable<object>>> GetCalibrationAlerts()
        {
            var today = DateTime.Today;
            var warningDate = today.AddDays(30); // Alert for items due in next 30 days

            var alerts = await _context.Tools
                .Where(t => t.NextCalibration != null && t.NextCalibration <= warningDate)
                .Select(t => new
                {
                    t.ToolID,
                    t.ToolName,
                    t.SerialNumber,
                    t.NextCalibration
                })
                .OrderBy(t => t.NextCalibration)
                .ToListAsync();

            return alerts;
        }


        // GET: api/Equipment/5
        [HttpGet("{id}")]
        public async Task<ActionResult<Tool>> GetTool(int id)
        {
            var tool = await _context.Tools.FindAsync(id);
            if (tool == null) return NotFound();
            return tool;
        }

        // POST: api/Equipment (CREATE)
        [HttpPost]
        public async Task<ActionResult<Tool>> PostTool(Tool tool)
        {
            try
            {
                // 1. Ensure ID is 0 so SQL generates a new one
                tool.ToolID = 0;

                // Generate the registration number on create if not provided.
                // Format: SP<YEAR>-<4 digits>, resets each year.
                if (string.IsNullOrWhiteSpace(tool.SerialNumber))
                {
                    tool.SerialNumber = await GenerateNextRegistrationNumberAsync();
                }

                tool.UpdatedDate = DateTime.Now;
                ApplyCertificationSchedule(tool);

                // 2. Handle optional relationships 
                // If your DB allows NULL for Warehouse/Category, we might need to handle 0s
                // But for now, let's just try to save.

                _context.Tools.Add(tool);
                await _context.SaveChangesAsync(); // <--- If it fails, it goes to 'catch'

                return CreatedAtAction("GetTool", new { id = tool.ToolID }, tool);
            }
            catch (DbUpdateException dbEx)
            {
                // This catches SQL errors specifically
                var message = dbEx.InnerException?.Message ?? dbEx.Message;
                return BadRequest($"SQL Error: {message}");
            }
            catch (Exception ex)
            {
                // This catches generic C# errors
                return StatusCode(500, $"Internal Server Error: {ex.Message}");
            }
        }

        // PUT: api/Equipment/5 (UPDATE)
        [HttpPut("{id}")]
        public async Task<IActionResult> PutTool(int id, Tool tool)
        {
            if (id != tool.ToolID) return BadRequest();

            var existing = await _context.Tools.AsNoTracking().FirstOrDefaultAsync(t => t.ToolID == id);
            if (existing == null) return NotFound();

            tool.CreatedDate = existing.CreatedDate;
            tool.UpdatedDate = DateTime.Now;
            ApplyCertificationSchedule(tool);
            _context.Entry(tool).State = EntityState.Modified;

            try
            {
                await _context.SaveChangesAsync();
            }
            catch (DbUpdateConcurrencyException)
            {
                if (!_context.Tools.Any(e => e.ToolID == id)) return NotFound();
                else throw;
            }

            return NoContent();
        }

        // DELETE: api/Equipment/5 (DELETE)
        [HttpDelete("{id}")]
        public async Task<IActionResult> DeleteTool(int id)
        {
            var tool = await _context.Tools.FindAsync(id);
            if (tool == null) return NotFound();

            _context.Tools.Remove(tool);
            await _context.SaveChangesAsync();

            return NoContent();
        }

        [HttpPost("upload-image")]
        public async Task<IActionResult> UploadImage([FromForm] IFormFile file)
        {
            if (file == null || file.Length == 0)
            {
                return BadRequest("No file uploaded.");
            }

            var allowedTypes = new[] { "image/jpeg", "image/png", "image/webp", "image/gif" };
            if (!allowedTypes.Contains(file.ContentType))
            {
                return BadRequest("Unsupported file type. Please upload an image (jpg, png, webp, gif).");
            }

            var uploadsRoot = Path.Combine(_environment.WebRootPath ?? "wwwroot", "uploads", "tools");
            Directory.CreateDirectory(uploadsRoot);

            var safeFileName = $"{Guid.NewGuid()}{Path.GetExtension(file.FileName)}";
            var filePath = Path.Combine(uploadsRoot, safeFileName);

            using (var stream = System.IO.File.Create(filePath))
            {
                await file.CopyToAsync(stream);
            }

            var relativePath = $"/uploads/tools/{safeFileName}".Replace("\\", "/");
            return Ok(new { path = relativePath });
        }
    }
}
