from sqlalchemy import Column, Integer, String, Boolean
from database import Base

class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(50), nullable=False)      
    module = Column(String(50), nullable=False)    
    can_view = Column(Boolean, default=True)
    can_create = Column(Boolean, default=False)
    can_edit = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    can_approve = Column(Boolean, default=False)