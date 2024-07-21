from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, String, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from passlib.context import CryptContext
from uuid import uuid4
import shutil

DATABASE_URL = "postgresql+psycopg2://postgres:Melvin%40123@localhost/db"



app = FastAPI()

# Database setup
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    phone = Column(String, unique=True)
    profile = relationship("Profile", back_populates="user", uselist=False)

class Profile(Base):
    __tablename__ = "profiles"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    profile_picture = Column(String)
    user = relationship("User", back_populates="profile")

Base.metadata.create_all(bind=engine)

# Pydantic schemas
class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    phone: str

class UserRead(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    phone: str

class ProfileRead(BaseModel):
    profile_picture: str

class UserProfileRead(UserRead):
    profile: ProfileRead

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility functions
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

@app.post("/register", response_model=UserProfileRead)
async def register_user(
    full_name: str = Form(...),
    email: EmailStr = Form(...),
    password: str = Form(...),
    phone: str = Form(...),
    profile_picture: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Check if email or phone already exists
    if db.query(User).filter((User.email == email) | (User.phone == phone)).first():
        raise HTTPException(status_code=400, detail="Email or phone number already registered")

    # Hash the password
    hashed_password = hash_password(password)

    # Create a new user
    user_id = str(uuid4())
    db_user = User(
        id=user_id,
        full_name=full_name,
        email=email,
        password=hashed_password,
        phone=phone
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Save profile picture
    profile_id = str(uuid4())
    profile_picture_path = f"profile_pictures/{profile_id}.jpg"
    with open(profile_picture_path, "wb") as buffer:
        shutil.copyfileobj(profile_picture.file, buffer)
    
    db_profile = Profile(
        id=profile_id,
        user_id=user_id,
        profile_picture=profile_picture_path
    )
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)

    return UserProfileRead(
        id=user_id,
        full_name=full_name,
        email=email,
        phone=phone,
        profile=ProfileRead(profile_picture=profile_picture_path)
    )

@app.get("/user/{user_id}", response_model=UserProfileRead)
async def get_user(user_id: str, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_profile = db_user.profile
    return UserProfileRead(
        id=db_user.id,
        full_name=db_user.full_name,
        email=db_user.email,
        phone=db_user.phone,
        profile=ProfileRead(profile_picture=db_profile.profile_picture)
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
