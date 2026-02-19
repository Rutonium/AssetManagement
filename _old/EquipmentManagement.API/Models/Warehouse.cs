using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using System.Text.Json.Serialization;

namespace EquipmentManagement.API.Models
{
    [Table("Warehouses")] // Make sure this matches your SQL Table Name
    public class Warehouse
    {
        [Key]
        public int WarehouseID { get; set; }

        public string? WarehouseName { get; set; }
        public string? Description { get; set; }
        public string? Address { get; set; }
        public int? GridColumns { get; set; }
        public int? GridRows { get; set; }
        public int? ManagerID { get; set; }
        public string? ContactPhone { get; set; }
        public DateTime CreatedDate { get; set; } = DateTime.Now;
        public bool IsActive { get; set; } = true;

        // Navigation Property: Link back to Tools
        // [JsonIgnore] prevents the API from getting stuck in a loop (Warehouse -> Tool -> Warehouse -> Tool...)
        [JsonIgnore]
        public virtual ICollection<Tool>? Tools { get; set; }
    }
}