using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace EquipmentManagement.API.Models
{
    [Table("WarehouseLocations")]
    public class WarehouseLocation
    {
        [Key]
        [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
        public int LocationID { get; set; }

        public int WarehouseID { get; set; }

        [Required]
        [StringLength(2)]
        public string GridColumn { get; set; } = string.Empty;

        public int GridRow { get; set; }

        [StringLength(20)]
        public string? ShelfNumber { get; set; }

        [StringLength(50)]
        public string? Zone { get; set; }

        [StringLength(200)]
        public string? CapacityDescription { get; set; }

        public bool IsActive { get; set; } = true;

        public DateTime CreatedDate { get; set; } = DateTime.Now;

        // Navigation properties
        [ForeignKey("WarehouseID")]
        public virtual Warehouse Warehouse { get; set; } = null!;

        public virtual ICollection<ToolLocation> ToolLocations { get; set; } = new List<ToolLocation>();

        // Helper properties
        [NotMapped]
        public string LocationCode => $"{GridColumn}-{GridRow}";

        [NotMapped]
        public bool IsOccupied => ToolLocations?.Any(tl => tl.IsCurrent) ?? false;
    }
}