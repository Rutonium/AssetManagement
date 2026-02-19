using Microsoft.EntityFrameworkCore;
using EquipmentManagement.API.Models;

namespace EquipmentManagement.API.Data
{
    public class AssetManagementContext : DbContext
    {
        public AssetManagementContext(DbContextOptions<AssetManagementContext> options)
            : base(options)
        {
        }

        // --- DbSets ---
        public DbSet<Tool> Tools { get; set; }
        public DbSet<Category> Categories { get; set; }
        public DbSet<Warehouse> Warehouses { get; set; }
        public DbSet<WarehouseLocation> WarehouseLocations { get; set; }
        public DbSet<Rental> Rentals { get; set; }
        public DbSet<RentalItem> RentalItems { get; set; }
        public DbSet<ServiceRecord> ServiceRecords { get; set; }
        public DbSet<Certificate> Certificates { get; set; }
        public DbSet<ToolLocation> ToolLocations { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            // --- 1. TABLE NAME MAPPING ---
            modelBuilder.Entity<Tool>().ToTable("Tools");
            modelBuilder.Entity<Category>().ToTable("Categories");
            modelBuilder.Entity<Warehouse>().ToTable("Warehouses");
            modelBuilder.Entity<WarehouseLocation>().ToTable("WarehouseLocations");
            modelBuilder.Entity<Certificate>().ToTable("Certificates");
            modelBuilder.Entity<RentalItem>().ToTable("RentalItems");
            modelBuilder.Entity<ToolLocation>().ToTable("ToolLocations");
            modelBuilder.Entity<ServiceRecord>().ToTable("Service");

            // *** CRITICAL FIX FOR SQL TRIGGERS ***
            // We configure the table builder (tb) to acknowledge a trigger exists.
            // This forces EF Core to use "OUTPUT INTO" syntax which is compatible with Triggers.
            modelBuilder.Entity<Rental>()
                .ToTable("Rental", tb => tb.HasTrigger("Rental_Trigger"));

            // --- 2. FOREIGN KEY MAPPING ---

            // Tool -> Category
            modelBuilder.Entity<Tool>()
                .HasOne(t => t.Category)
                .WithMany(c => c.Tools)
                .HasForeignKey(t => t.CategoryID)
                .IsRequired(false);

            // Tool -> Warehouse
            modelBuilder.Entity<Tool>()
                .HasOne(t => t.Warehouse)
                .WithMany(w => w.Tools)
                .HasForeignKey(t => t.WarehouseID)
                .IsRequired(false);

            // RentalItem -> Rental
            modelBuilder.Entity<RentalItem>()
                .HasOne(ri => ri.Rental)
                .WithMany(r => r.RentalItems)
                .HasForeignKey(ri => ri.RentalID);

            // RentalItem -> Tool
            modelBuilder.Entity<RentalItem>()
                .HasOne(ri => ri.Tool)
                .WithMany(t => t.RentalItems)
                .HasForeignKey(ri => ri.ToolID);

            // --- 3. PRECISION CONFIGURATION ---
            modelBuilder.Entity<Tool>()
                .Property(p => p.PurchaseCost).HasColumnType("decimal(18,2)");
            modelBuilder.Entity<Tool>()
                .Property(p => p.CurrentValue).HasColumnType("decimal(18,2)");
            modelBuilder.Entity<Tool>()
                .Property(p => p.DailyRentalCost).HasColumnType("decimal(18,2)");

            modelBuilder.Entity<Rental>()
                .Property(p => p.TotalCost).HasColumnType("decimal(18,2)");

            modelBuilder.Entity<RentalItem>()
                .Property(p => p.DailyCost).HasColumnType("decimal(18,2)");
            modelBuilder.Entity<RentalItem>()
                .Property(p => p.TotalCost).HasColumnType("decimal(18,2)");
        }
    }
}