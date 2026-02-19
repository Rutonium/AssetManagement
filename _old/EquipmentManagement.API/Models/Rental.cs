using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace EquipmentManagement.API.Models
{
    [Table("Rental")]
    public class Rental
    {
        [Key]
        [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
        public int RentalID { get; set; }

        [Required]
        [StringLength(50)]
        public string RentalNumber { get; set; } = string.Empty;

        public int EmployeeID { get; set; } // References TimeApp.Employees

        [Required]
        [StringLength(1000)]
        public string Purpose { get; set; } = string.Empty;

        [StringLength(50)]
        public string? ProjectCode { get; set; }

        [StringLength(20)]
        public string Status { get; set; } = "Pending"; // Pending, Approved, Active, Returned, Overdue, Cancelled

        [Required]
        [Column(TypeName = "date")]
        public DateTime StartDate { get; set; }

        [Required]
        [Column(TypeName = "date")]
        public DateTime EndDate { get; set; }

        [Column(TypeName = "date")]
        public DateTime? ActualStart { get; set; }

        [Column(TypeName = "date")]
        public DateTime? ActualEnd { get; set; }

        [Column(TypeName = "decimal(10,2)")]
        public decimal? TotalCost { get; set; }

        public int? ApprovedBy { get; set; } // EmployeeID from TimeApp database

        [Column(TypeName = "date")]
        public DateTime? ApprovalDate { get; set; }

        [StringLength(500)]
        public string? CheckoutCondition { get; set; }

        [StringLength(500)]
        public string? ReturnCondition { get; set; }

        [StringLength(1000)]
        public string? Notes { get; set; }

        public DateTime CreatedDate { get; set; } = DateTime.Now;

        public DateTime UpdatedDate { get; set; } = DateTime.Now;

        // Navigation properties
        public virtual ICollection<RentalItem> RentalItems { get; set; } = new List<RentalItem>();

        // Helper properties for frontend
        [NotMapped]
        public string StatusDisplay => Status;

        [NotMapped]
        public bool IsActive => Status == "Active";

        [NotMapped]
        public bool IsPending => Status == "Pending";

        [NotMapped]
        public bool IsOverdue => Status == "Overdue";

        [NotMapped]
        public int DaysRemaining => (EndDate - DateTime.Now).Days;

        
        public decimal CalculateTotalCost()
        {
            // Use Count instead of Any() for better performance
            if (RentalItems == null || RentalItems.Count == 0)
                return 0;

            decimal total = 0;

            // Calculate days
            int rentalDays = (EndDate - StartDate).Days;

            // Safety check: if rented/returned same day, count as 1 day
            if (rentalDays == 0) rentalDays = 1;

            foreach (var item in RentalItems)
            {
                total += (item.DailyCost ?? 0) * rentalDays * item.Quantity;
            }

            return total;
        }

        [NotMapped]
        public bool CanApprove => Status == "Pending";

        [NotMapped]
        public bool CanReturn => Status == "Active";

        [NotMapped]
        public bool CanEdit => Status == "Pending" || Status == "Approved";
    }
}