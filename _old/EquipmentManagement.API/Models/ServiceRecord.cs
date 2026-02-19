using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace EquipmentManagement.API.Models
{
    [Table("Service")]
    public class ServiceRecord
    {
        [Key]
        [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
        public int ServiceID { get; set; }

        public int ToolID { get; set; }

        [Required]
        [StringLength(50)]
        public string ServiceType { get; set; } = string.Empty; // Preventive, Corrective, Inspection, Repair

        [Required]
        [Column(TypeName = "date")]
        public DateTime ServiceDate { get; set; }

        [Required]
        [StringLength(1000)]
        public string Description { get; set; } = string.Empty;

        [Column(TypeName = "decimal(10,2)")]
        public decimal? Cost { get; set; }

        [StringLength(200)]
        public string? PerformedBy { get; set; }

        [Column(TypeName = "date")]
        public DateTime? NextServiceDue { get; set; }

        [StringLength(1000)]
        public string? Notes { get; set; }

        public DateTime CreatedDate { get; set; } = DateTime.Now;

        // Navigation properties
        [ForeignKey("ToolID")]
        public virtual Tool Tool { get; set; } = null!;

        // Helper properties
        [NotMapped]
        public bool IsOverdue => NextServiceDue.HasValue && NextServiceDue < DateTime.Now;

        [NotMapped]
        public bool IsDueSoon => NextServiceDue.HasValue && NextServiceDue <= DateTime.Now.AddDays(30);

        [NotMapped]
        public int DaysUntilNextService => NextServiceDue.HasValue ? (NextServiceDue.Value - DateTime.Now).Days : -1;
    }
}