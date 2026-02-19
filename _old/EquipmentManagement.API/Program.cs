using EquipmentManagement.API.Data;
using Microsoft.EntityFrameworkCore;
using EquipmentManagement.API.Services;
using System.Text.Json.Serialization; // Added for the Swagger fix

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
// This fixes the JSON cycle error in Swagger
builder.Services.AddControllers().AddJsonOptions(options =>
{
    options.JsonSerializerOptions.ReferenceHandler = ReferenceHandler.IgnoreCycles;
});

// Register Database Contexts
builder.Services.AddDbContext<AssetManagementContext>(options =>
    options.UseSqlServer(builder.Configuration.GetConnectionString("AssetManagementDB")));

builder.Services.AddDbContext<TimeAppContext>(options =>
    options.UseSqlServer(builder.Configuration.GetConnectionString("TimeAppDB")));

builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll",
        builder => builder.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader());
});

// Add Swagger/OpenAPI support
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.AddScoped<IEquipmentService, EquipmentService>();
builder.Services.AddScoped<IRentalService, RentalService>();

var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

// --- THESE ENABLE YOUR HTML FILES ---
app.UseDefaultFiles();
app.UseStaticFiles();
// ------------------------------------

app.UseCors("AllowAll");

app.UseAuthorization();

// --- THIS WAS MISSING! IT TURNS ON YOUR API ---
app.MapControllers();
// ---------------------------------------------

app.Run();

