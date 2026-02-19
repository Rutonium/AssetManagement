using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace EquipmentManagement.API.Models
{
    [Table("Certificates")]
    public class Certificate
    {
        [Key]
        [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
        public int CertificateID { get; set; }

        public int ToolID { get; set; }

        [Required]
        [StringLength(100)]
        public string CertificateNumber { get; set; } = string.Empty;

        [Required]
        [StringLength(50)]
        public string CertificateType { get; set; } = string.Empty; // Calibration, Certification, Inspection

        [Required]
        [Column(TypeName = "date")]
        public DateTime IssueDate { get; set; }

        [Column(TypeName = "date")]
        public DateTime? ExpiryDate { get; set; }

        [StringLength(200)]
        public string? IssuingAuthority { get; set; }

        [StringLength(500)]
        public string? CertificatePath { get; set; }

        [Column(TypeName = "decimal(8,2)")]
        public decimal? Cost { get; set; }

        [StringLength(500)]
        public string? Notes { get; set; }

        public DateTime CreatedDate { get; set; } = DateTime.Now;

        // Navigation properties
        [ForeignKey("ToolID")]
        public virtual Tool Tool { get; set; } = null!;

        // Helper properties
        [NotMapped]
        public bool IsExpired => ExpiryDate.HasValue && ExpiryDate < DateTime.Now;

        [NotMapped]
        public bool IsExpiringSoon => ExpiryDate.HasValue && ExpiryDate <= DateTime.Now.AddDays(30);

        [NotMapped]
        public int DaysUntilExpiry => ExpiryDate.HasValue ? (ExpiryDate.Value - DateTime.Now).Days : -1;
    }
}