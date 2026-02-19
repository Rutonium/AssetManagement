using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace EquipmentManagement.API.Models
{
    [Table("RentalItems")]
    public class RentalItem
    {
        [Key]
        [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
        public int RentalItemID { get; set; }

        public int RentalID { get; set; }

        public int ToolID { get; set; }

        public int Quantity { get; set; } = 1;

        [Column(TypeName = "decimal(8,2)")]
        public decimal? DailyCost { get; set; }

        [Column(TypeName = "decimal(10,2)")]
        public decimal? TotalCost { get; set; }

        [StringLength(500)]
        public string? CheckoutNotes { get; set; }

        [StringLength(500)]
        public string? ReturnNotes { get; set; }

        // Navigation properties
        [ForeignKey("RentalID")]
        public virtual Rental Rental { get; set; } = null!;

        [ForeignKey("ToolID")]
        public virtual Tool Tool { get; set; } = null!;
    }
}