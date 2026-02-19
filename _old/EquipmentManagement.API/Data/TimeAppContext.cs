using Microsoft.EntityFrameworkCore;
using EquipmentManagement.API.Models;

namespace EquipmentManagement.API.Data
{
    public class TimeAppContext : DbContext
    {
        public TimeAppContext(DbContextOptions<TimeAppContext> options)
            : base(options)
        {
        }

        public DbSet<Employee> Employees { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder);

            // Configure table name
            modelBuilder.Entity<Employee>().ToTable("Employees");

            // Configure default values
            modelBuilder.Entity<Employee>()
                .Property(e => e.IsActive)
                .HasDefaultValue(true);

            modelBuilder.Entity<Employee>()
                .Property(e => e.CreatedDate)
                .HasDefaultValue(DateTime.Now);
        }
    }
}