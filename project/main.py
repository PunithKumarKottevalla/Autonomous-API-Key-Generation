from fastapi import FastAPI, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


client = MongoClient("mongodb://localhost:27017/")
db = client["auth_db"]
users_collection = db["Mini_Project"]

@app.post("/register")
def register(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    if users_collection.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    users_collection.insert_one({
        "name": name,
        "email": email,
        "password": password
    })

    return {"message": "User registered successfully"}

@app.post("/login")
def login(
    email: str = Form(...),
    password: str = Form(...)
):
    user = users_collection.find_one({"email": email})

    if not user or user["password"] != password:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    return {"message": "Login successful"}

@app.get("/")
def home():
    return {"message": "Simple backend running (no hashing)"}




from pydantic import BaseModel
from planning_agent_2 import run_agent 

class QueryRequest(BaseModel):
    query: str


@app.post("/query")
def handle_query(req: QueryRequest):
    result = run_agent(req.query)  
    return {"result": result}

