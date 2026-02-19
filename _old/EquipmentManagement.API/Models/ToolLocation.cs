using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace EquipmentManagement.API.Models
{
    [Table("ToolLocations")]
    public class ToolLocation
    {
        [Key]
        [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
        public int AssignmentID { get; set; }

        public int ToolID { get; set; }

        public int LocationID { get; set; }

        public DateTime AssignedDate { get; set; } = DateTime.Now;

        public int AssignedBy { get; set; } // EmployeeID from TimeApp database

        [StringLength(500)]
        public string? Notes { get; set; }

        public bool IsCurrent { get; set; } = true;

        // Navigation properties
        [ForeignKey("ToolID")]
        public virtual Tool Tool { get; set; } = null!;

        [ForeignKey("LocationID")]
        public virtual WarehouseLocation Location { get; set; } = null!;
    }
}