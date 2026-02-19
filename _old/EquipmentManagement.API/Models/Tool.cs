using System;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using System.Text.Json.Serialization;

namespace EquipmentManagement.API.Models
{
    [Table("Tools")]
    public class Tool
    {
        [Key]
        public int ToolID { get; set; }

        public string? ToolName { get; set; }
        public string? SerialNumber { get; set; }
        public string? ModelNumber { get; set; }
        public string? Manufacturer { get; set; }

        // --- CATEGORY ---
        public int CategoryID { get; set; }

        [ForeignKey("CategoryID")]
        [JsonIgnore]
        public virtual Category? Category { get; set; }

        // --- DETAILS ---
        public string? Description { get; set; }
        public DateTime? PurchaseDate { get; set; }
        public decimal? PurchaseCost { get; set; }
        public decimal? CurrentValue { get; set; }
        public int? CalibrationInterval { get; set; }
        public DateTime? LastCalibration { get; set; }
        public DateTime? NextCalibration { get; set; }
        public string? Status { get; set; }
        public string? Condition { get; set; }
        public decimal? DailyRentalCost { get; set; }
        public bool RequiresCertification { get; set; }

        // --- WAREHOUSE ---
        public int WarehouseID { get; set; }

        [ForeignKey("WarehouseID")]
        [JsonIgnore]
        public virtual Warehouse? Warehouse { get; set; }

        // --- LOCATION ---
        public string? LocationCode { get; set; }
        public string? ImagePath { get; set; }

        public DateTime CreatedDate { get; set; } = DateTime.Now;
        public DateTime UpdatedDate { get; set; } = DateTime.Now;

        // --- NAVIGATION COLLECTIONS (These were missing!) ---

        [JsonIgnore]
        public virtual ICollection<RentalItem>? RentalItems { get; set; }

        [JsonIgnore]
        public virtual ICollection<Certificate>? Certificates { get; set; }

        [JsonIgnore]
        public virtual ICollection<ToolLocation>? ToolLocations { get; set; }

        [JsonIgnore]
        public virtual ICollection<ServiceRecord>? ServiceRecords { get; set; }
    }
}