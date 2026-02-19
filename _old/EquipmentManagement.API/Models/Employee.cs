using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace EquipmentManagement.API.Models
{
    [Table("Employees")]
    public class Employee
    {
        [Key]
        [DatabaseGenerated(DatabaseGeneratedOption.Identity)]
        public int EmployeeID { get; set; }

        [Required]
        [StringLength(100)]
        public string WindowsUsername { get; set; } = string.Empty;

        [Required]
        [StringLength(255)]
        public string Email { get; set; } = string.Empty;

        [Required]
        [StringLength(255)]
        public string FullName { get; set; } = string.Empty;

        [StringLength(100)]
        public string Department { get; set; } = string.Empty;

        [StringLength(50)]
        public string Role { get; set; } = "Standard User";

        [StringLength(20)]
        public string? Phone { get; set; }

        public bool IsActive { get; set; } = true;

        public DateTime? LastLogin { get; set; }

        public DateTime HireDate { get; set; }

        public DateTime CreatedDate { get; set; } = DateTime.Now;

        // Helper properties
        [NotMapped]
        public bool IsAdmin => Role == "Admin";

        [NotMapped]
        public bool IsManager => Role == "Manager" || Role == "Admin";

        [NotMapped]
        public string DisplayName => FullName;

        [NotMapped]
        public string RoleDisplay => Role;
    }
}