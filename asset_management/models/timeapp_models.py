from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String
from sqlalchemy.sql import func

from db.base import Base


class Employee(Base):
    __tablename__ = "Employees"
    __table_args__ = {"schema": "dbo"}

    EmployeeID = Column(Integer, primary_key=True)
    WindowsUsername = Column(String(100), nullable=False)
    Email = Column(String(255), nullable=False)
    FullName = Column(String(255), nullable=False)
    Department = Column(String(100))
    Role = Column(String(50), default="Standard User")
    Phone = Column(String(20))
    IsActive = Column(Boolean, default=True)
    LastLogin = Column(DateTime)
    HireDate = Column(Date)
    CreatedDate = Column(DateTime, server_default=func.now())
