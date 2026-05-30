from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import pickle
import os
from pymongo import MongoClient
import datetime

app = FastAPI(title="Sales Forecasting API")

# Setup CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to MongoDB
try:
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
    db = client.sales_db
    collection = db.predictions
    # Ping to check if mongodb is alive
    client.admin.command('ping')
    mongodb_available = True
    print("Connected to MongoDB successfully.")
except Exception as e:
    mongodb_available = False
    print(f"Warning: Could not connect to MongoDB. Logging will be disabled. Error: {e}")

MODEL_FILE = os.path.join(os.path.dirname(__file__), 'model.pkl')
model_pipeline = None

@app.on_event("startup")
def load_model():
    global model_pipeline
    if os.path.exists(MODEL_FILE):
        with open(MODEL_FILE, 'rb') as f:
            model_pipeline = pickle.load(f)
        print("Model loaded successfully.")
    else:
        print(f"Warning: Model file not found at {MODEL_FILE}. Please train the model first.")

class PredictionRequest(BaseModel):
    ship_mode: str
    segment: str
    category: str
    sub_category: str
    quantity: float
    discount: float
    profit: float
    month: int
    day_of_week: int

@app.get("/")
def read_root():
    return {"message": "Sales Forecasting API is running"}

@app.post("/predict")
def predict_sales(req: PredictionRequest):
    if model_pipeline is None:
        raise HTTPException(status_code=500, detail="Model is not loaded. Train the model first.")
    
    try:
        # 1. Format input as DataFrame
        input_data = pd.DataFrame([{
            'Ship Mode': req.ship_mode,
            'Segment': req.segment,
            'Category': req.category,
            'Sub-Category': req.sub_category,
            'Quantity': req.quantity,
            'Discount': req.discount,
            'Profit': req.profit,
            'Month': req.month,
            'DayOfWeek': req.day_of_week
        }])
        
        # We need to make sure the columns match exactly the features the model was trained on
        # model_pipeline['features'] gives the order
        features_order = model_pipeline['features']
        
        # Label Encoding
        for col, le in model_pipeline['label_encoders'].items():
            if col in input_data.columns:
                # Handle unseen labels gracefully
                try:
                    input_data[col] = le.transform(input_data[col].astype(str))
                except ValueError:
                    # Assign a default class if unseen
                    input_data[col] = le.transform([le.classes_[0]])[0]
                    
        # Ensure column order
        input_data = input_data[features_order]
        
        # Scaling
        input_scaled = model_pipeline['scaler'].transform(input_data)
        
        # Predict
        prediction = model_pipeline['model'].predict(input_scaled)[0]
        prediction = float(prediction)
        
        # Log to MongoDB
        if mongodb_available:
            log_entry = req.dict()
            log_entry['predicted_sales'] = prediction
            log_entry['timestamp'] = datetime.datetime.utcnow()
            collection.insert_one(log_entry)
            
        return {"predicted_sales": prediction, "status": "success"}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
