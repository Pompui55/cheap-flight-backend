from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Header, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import random
import bcrypt
import jwt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'cheap_flight')]

# Aviationstack API
AVIATIONSTACK_API_KEY = os.environ.get('AVIATIONSTACK_API_KEY', '')

# JWT Secret
JWT_SECRET = os.environ.get('JWT_SECRET', 'cheap-flight-secret-key-2026')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 7

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the main app
app = FastAPI(title="CHEAP FLIGHT API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer(auto_error=False)

# ============= AUTH MODELS =============
class UserRegister(BaseModel):
    email: str
    password: str
    name: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    created_at: str
Ajoutons les Favoris et Alertes au Backend
Étape 1 : Ouvrez server.py avec nano
nano ~/Cheap-flight/backend/server.py
Étape 2 : Trouvez la section # ============= AUTH MODELS =============
Juste APRÈS les modèles d'authentification (après class UserResponse), ajoutez ce code :

# ============= FAVORITES MODELS =============
class FavoriteCreate(BaseModel):
    origin: str
    destination: str
    origin_city: str = ""
    destination_city: str = ""

class FavoriteResponse(BaseModel):
    favorite_id: str
    user_id: str
    origin: str
    destination: str
    origin_city: str
    destination_city: str
    created_at: str

# ============= ALERTS MODELS =============
class AlertCreate(BaseModel):
    origin: str
    destination: str
    origin_city: str = ""
    destination_city: str = ""
    target_price: float

class AlertResponse(BaseModel):
    alert_id: str
    user_id: str
    origin: str
    destination: str
    origin_city: str
    destination_city: str
    target_price: float
    is_active: bool
    created_at: str
Étape 3 : Trouvez la fin du fichier (avant app.add_middleware)
Ajoutez ces nouveaux endpoints AVANT la ligne app.add_middleware( :

# ============= FAVORITES ROUTES =============

@api_router.get("/favorites")
async def get_favorites(current_user: dict = Depends(get_current_user)):
    favorites = await db.favorites.find({"user_id": current_user["user_id"]}).to_list(100)
    return [{
        "favorite_id": f["favorite_id"],
        "user_id": f["user_id"],
        "origin": f["origin"],
        "destination": f["destination"],
        "origin_city": f.get("origin_city", f["origin"]),
        "destination_city": f.get("destination_city", f["destination"]),
        "created_at": f["created_at"]
    } for f in favorites]

@api_router.post("/favorites")
async def add_favorite(favorite: FavoriteCreate, current_user: dict = Depends(get_current_user)):
    # Check if already exists
    existing = await db.favorites.find_one({
        "user_id": current_user["user_id"],
        "origin": favorite.origin.upper(),
        "destination": favorite.destination.upper()
    })
    if existing:
        raise HTTPException(status_code=400, detail="Favorite already exists")
    
    favorite_id = str(uuid.uuid4())
    fav = {
        "favorite_id": favorite_id,
        "user_id": current_user["user_id"],
        "origin": favorite.origin.upper(),
        "destination": favorite.destination.upper(),
        "origin_city": favorite.origin_city or favorite.origin.upper(),
        "destination_city": favorite.destination_city or favorite.destination.upper(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.favorites.insert_one(fav)
    return {"favorite_id": favorite_id, "message": "Favorite added"}

@api_router.delete("/favorites/{favorite_id}")
async def delete_favorite(favorite_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.favorites.delete_one({
        "favorite_id": favorite_id,
        "user_id": current_user["user_id"]
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favorite not found")
    return {"message": "Favorite deleted"}

# ============= ALERTS ROUTES =============

@api_router.get("/alerts")
async def get_alerts(current_user: dict = Depends(get_current_user)):
    alerts = await db.alerts.find({"user_id": current_user["user_id"]}).to_list(100)
    return [{
        "alert_id": a["alert_id"],
        "user_id": a["user_id"],
        "origin": a["origin"],
        "destination": a["destination"],
        "origin_city": a.get("origin_city", a["origin"]),
        "destination_city": a.get("destination_city", a["destination"]),
        "target_price": a["target_price"],
        "is_active": a.get("is_active", True),
        "created_at": a["created_at"]
    } for a in alerts]

@api_router.post("/alerts")
async def create_alert(alert: AlertCreate, current_user: dict = Depends(get_current_user)):
    alert_id = str(uuid.uuid4())
    alert_doc = {
        "alert_id": alert_id,
        "user_id": current_user["user_id"],
        "origin": alert.origin.upper(),
        "destination": alert.destination.upper(),
        "origin_city": alert.origin_city or alert.origin.upper(),
        "destination_city": alert.destination_city or alert.destination.upper(),
        "target_price": alert.target_price,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.alerts.insert_one(alert_doc)
    return {"alert_id": alert_id, "message": "Alert created"}

@api_router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str, current_user: dict = Depends(get_current_user)):
    result = await db.alerts.delete_one({
        "alert_id": alert_id,
        "user_id": current_user["user_id"]
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert deleted"}

@api_router.patch("/alerts/{alert_id}/toggle")
async def toggle_alert(alert_id: str, current_user: dict = Depends(get_current_user)):
    alert = await db.alerts.find_one({
        "alert_id": alert_id,
        "user_id": current_user["user_id"]
    })
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    new_status = not alert.get("is_active", True)
    await db.alerts.update_one(
        {"alert_id": alert_id},
        {"$set": {"is_active": new_status}}
    )
    return {"is_active": new_status, "message": f"Alert {'activated' if new_status else 'deactivated'}"}
Étape 4 : Sauvegardez et quittez nano
Ctrl+O → Enter (sauvegarder)
Ctrl+X (quitter)
# ============= AUTH HELPERS =============
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRATION_DAYS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    payload = decode_token(credentials.credentials)
    user = await db.users.find_one({"user_id": payload["user_id"]})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ============= MODELS =============
class Flight(BaseModel):
    flight_id: str
    airline: str
    airline_logo: Optional[str] = None
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    duration: str
    price: float
    currency: str = "EUR"
    stops: int = 0
    flight_number: str = ""
    available_seats: int = 0

class SearchRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    adults: int = 1

# ============= AIRPORTS DATA =============
AIRPORTS = {
    "CDG": {"city": "Paris", "country": "France", "name": "Charles de Gaulle"},
    "ORY": {"city": "Paris", "country": "France", "name": "Orly"},
    "LHR": {"city": "London", "country": "UK", "name": "Heathrow"},
    "JFK": {"city": "New York", "country": "USA", "name": "John F. Kennedy"},
    "LAX": {"city": "Los Angeles", "country": "USA", "name": "Los Angeles Intl"},
    "DXB": {"city": "Dubai", "country": "UAE", "name": "Dubai Intl"},
    "SIN": {"city": "Singapore", "country": "Singapore", "name": "Changi"},
    "HND": {"city": "Tokyo", "country": "Japan", "name": "Haneda"},
    "FCO": {"city": "Rome", "country": "Italy", "name": "Fiumicino"},
    "BCN": {"city": "Barcelona", "country": "Spain", "name": "El Prat"},
    "MAD": {"city": "Madrid", "country": "Spain", "name": "Barajas"},
    "AMS": {"city": "Amsterdam", "country": "Netherlands", "name": "Schiphol"},
    "FRA": {"city": "Frankfurt", "country": "Germany", "name": "Frankfurt"},
    "IST": {"city": "Istanbul", "country": "Turkey", "name": "Istanbul"},
    "BKK": {"city": "Bangkok", "country": "Thailand", "name": "Suvarnabhumi"},
    "CMN": {"city": "Casablanca", "country": "Morocco", "name": "Mohammed V"},
    "ALG": {"city": "Algiers", "country": "Algeria", "name": "Houari Boumediene"},
    "TUN": {"city": "Tunis", "country": "Tunisia", "name": "Carthage"},
    "ABJ": {"city": "Abidjan", "country": "Ivory Coast", "name": "Felix-Houphouet-Boigny"},
    "DKR": {"city": "Dakar", "country": "Senegal", "name": "Blaise Diagne"},
    "NYC": {"city": "New York", "country": "USA", "name": "All Airports"},
    "PAR": {"city": "Paris", "country": "France", "name": "All Airports"},
    "LON": {"city": "London", "country": "UK", "name": "All Airports"},
}

AIRLINES = [
    {"code": "AF", "name": "Air France"},
    {"code": "LH", "name": "Lufthansa"},
    {"code": "BA", "name": "British Airways"},
    {"code": "EK", "name": "Emirates"},
    {"code": "QR", "name": "Qatar Airways"},
    {"code": "TK", "name": "Turkish Airlines"},
    {"code": "KL", "name": "KLM"},
    {"code": "IB", "name": "Iberia"},
    {"code": "AT", "name": "Royal Air Maroc"},
    {"code": "AH", "name": "Air Algerie"},
]

# ============= FLIGHT SEARCH =============
async def get_aviationstack_flights(origin: str, destination: str, flight_date: str):
    if not AVIATIONSTACK_API_KEY:
        logger.warning("Aviationstack API key not found")
        return []
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            params = {
                'access_key': AVIATIONSTACK_API_KEY,
                'dep_iata': origin.upper(),
                'arr_iata': destination.upper(),
                'limit': 20
            }
            
            response = await http_client.get(
                'http://api.aviationstack.com/v1/flights',
                params=params
            )
            
            if response.status_code != 200:
                logger.error(f"Aviationstack API error: {response.status_code}")
                return []
            
            data = response.json()
            flights = data.get('data', [])
            
            transformed_flights = []
            for flight in flights:
                try:
                    dep_time = flight.get('departure', {}).get('scheduled')
                    arr_time = flight.get('arrival', {}).get('scheduled')
                    
                    if dep_time and arr_time:
                        dep_dt = datetime.fromisoformat(dep_time.replace('Z', '+00:00'))
                        arr_dt = datetime.fromisoformat(arr_time.replace('Z', '+00:00'))
                        duration_mins = int((arr_dt - dep_dt).total_seconds() / 60)
                        duration = f"{duration_mins // 60}h {duration_mins % 60}m"
                    else:
                        duration = "N/A"
                    
                    base_price = 50 + (duration_mins // 60 * 30) + random.randint(-20, 50)
                    
                    transformed_flight = {
                        "flight_id": flight.get('flight', {}).get('iata', f"FL{uuid.uuid4().hex[:8].upper()}"),
                        "airline": flight.get('airline', {}).get('name', 'Unknown Airline'),
                        "airline_logo": f"https://images.kiwi.com/airlines/64/{flight.get('airline', {}).get('iata', 'XX')}.png",
                        "origin": flight.get('departure', {}).get('iata', origin),
                        "destination": flight.get('arrival', {}).get('iata', destination),
                        "departure_time": dep_time or f"{flight_date}T00:00:00",
                        "arrival_time": arr_time or f"{flight_date}T00:00:00",
                        "duration": duration,
                        "price": float(base_price),
                        "currency": "EUR",
                        "stops": 0,
                        "flight_number": flight.get('flight', {}).get('iata', 'N/A'),
                        "available_seats": random.randint(5, 50)
                    }
                    transformed_flights.append(transformed_flight)
                except Exception as e:
                    logger.error(f"Error transforming flight: {e}")
                    continue
            
            return transformed_flights
            
    except Exception as e:
        logger.error(f"Aviationstack API error: {e}")
        return []

def generate_mock_flights(origin: str, destination: str, flight_date: str, count: int = 8):
    flights = []
    
    base_prices = {
        ("CDG", "JFK"): 450, ("PAR", "NYC"): 450, ("CDG", "DXB"): 380,
        ("CDG", "BCN"): 85, ("CDG", "LHR"): 95, ("PAR", "LON"): 95,
        ("CDG", "FCO"): 110, ("CDG", "CMN"): 120,
    }
    base_price = base_prices.get((origin.upper(), destination.upper()), random.randint(150, 600))
    
    for i in range(count):
        airline = random.choice(AIRLINES)
        hour = random.randint(6, 22)
        minute = random.choice([0, 15, 30, 45])
        
        duration_hours = random.randint(8, 14) if len(origin) == 3 and len(destination) == 3 else random.randint(2, 5)
        duration_mins = random.choice([0, 15, 30, 45])
        
        arr_hour = (hour + duration_hours) % 24
        arr_minute = (minute + duration_mins) % 60
        
        price_var = random.uniform(0.8, 1.3)
        stops = random.choices([0, 1], weights=[70, 30])[0]
        if stops > 0:
            price_var *= 0.85
        
        flight = {
            "flight_id": f"FL{uuid.uuid4().hex[:8].upper()}",
            "airline": airline["name"],
            "airline_logo": f"https://images.kiwi.com/airlines/64/{airline['code']}.png",
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departure_time": f"{flight_date}T{hour:02d}:{minute:02d}:00",
            "arrival_time": f"{flight_date}T{arr_hour:02d}:{arr_minute:02d}:00",
            "duration": f"{duration_hours}h {duration_mins}m",
            "price": round(base_price * price_var, 2),
            "currency": "EUR",
            "stops": stops,
            "flight_number": f"{airline['code']}{random.randint(100, 9999)}",
            "available_seats": random.randint(3, 45)
        }
        flights.append(flight)
    
    flights.sort(key=lambda x: x["price"])
    return flights

# ============= API ROUTES =============

@api_router.get("/")
async def root():
    return {"message": "CHEAP FLIGHT API", "status": "online", "version": "3.0"}

# ============= AUTH ROUTES =============

@api_router.post("/auth/register")
async def register(user_data: UserRegister):
    existing = await db.users.find_one({"email": user_data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    if len(user_data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    user_id = str(uuid.uuid4())
    user = {
        "user_id": user_id,
        "email": user_data.email.lower(),
        "name": user_data.name,
        "password_hash": hash_password(user_data.password),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user)
    token = create_token(user_id)
    
    return {
        "user": {"user_id": user_id, "email": user["email"], "name": user["name"], "created_at": user["created_at"]},
        "token": token
    }

@api_router.post("/auth/login")
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email.lower()})
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_token(user["user_id"])
    
    return {
        "user": {"user_id": user["user_id"], "email": user["email"], "name": user["name"], "created_at": user["created_at"]},
        "token": token
    }

@api_router.get("/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {"user_id": current_user["user_id"], "email": current_user["email"], "name": current_user["name"], "created_at": current_user["created_at"]}

@api_router.post("/auth/logout")
async def logout():
    return {"message": "Logged out successfully"}

@api_router.get("/airports")
async def get_airports(query: str = None):
    if not query or len(query) < 2:
        return [{"code": k, **v} for k, v in list(AIRPORTS.items())[:10]]
    
    query_lower = query.lower()
    results = []
    for code, info in AIRPORTS.items():
        if (query_lower in code.lower() or query_lower in info["city"].lower() or query_lower in info["country"].lower()):
            results.append({"code": code, **info})
    return results[:10]

@api_router.post("/flights/search")
async def search_flights(search: SearchRequest):
    origin = search.origin.upper()
    destination = search.destination.upper()
    
    city_to_airport = {"PAR": "CDG", "NYC": "JFK", "LON": "LHR"}
    origin = city_to_airport.get(origin, origin)
    destination = city_to_airport.get(destination, destination)
    
    flights = await get_aviationstack_flights(origin, destination, search.departure_date)
    
    if not flights:
        flights = generate_mock_flights(origin, destination, search.departure_date)
    
    await db.search_history.insert_one({
        "id": str(uuid.uuid4()),
        "origin": origin,
        "destination": destination,
        "departure_date": search.departure_date,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return {"flights": flights, "count": len(flights)}

@api_router.get("/flights/popular")
async def get_popular():
    return [
        {"origin": "CDG", "destination": "BCN", "city": "Barcelona", "country": "Spain", "price_from": 85},
        {"origin": "CDG", "destination": "LHR", "city": "London", "country": "UK", "price_from": 95},
        {"origin": "CDG", "destination": "FCO", "city": "Rome", "country": "Italy", "price_from": 99},
        {"origin": "CDG", "destination": "MAD", "city": "Madrid", "country": "Spain", "price_from": 89},
        {"origin": "CDG", "destination": "AMS", "city": "Amsterdam", "country": "Netherlands", "price_from": 79},
        {"origin": "CDG", "destination": "CMN", "city": "Casablanca", "country": "Morocco", "price_from": 120},
        {"origin": "CDG", "destination": "JFK", "city": "New York", "country": "USA", "price_from": 380},
        {"origin": "CDG", "destination": "DXB", "city": "Dubai", "country": "UAE", "price_from": 350},
    ]

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
