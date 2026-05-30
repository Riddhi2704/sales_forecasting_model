import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor
import pickle
import os
import sys

DATA_FILE = "store_sales.csv"
MODEL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend', 'model.pkl')

def generate_mock_data():
    """Generates mock data if the Kaggle dataset is not present."""
    print("Generating mock dataset for testing...")
    np.random.seed(42)
    n_samples = 1000
    
    quantity = np.random.randint(1, 15, n_samples)
    discount = np.random.uniform(0.0, 0.5, n_samples)
    profit = np.random.uniform(-50, 200, n_samples)
    
    category_list = ['Furniture', 'Office Supplies', 'Technology']
    category = np.random.choice(category_list, n_samples)
    
    # Generate Sales correlated with features
    sales = np.zeros(n_samples)
    for i in range(n_samples):
        base = 50
        cat_mult = 1.5 if category[i] == 'Technology' else (1.2 if category[i] == 'Furniture' else 1.0)
        sales[i] = base + (quantity[i] * 30 * cat_mult) + (profit[i] * 0.5) - (discount[i] * 100) + np.random.normal(0, 20)
        sales[i] = max(10, sales[i]) # ensure positive sales
        
    data = {
        'Order Date': pd.date_range(start='1/1/2020', periods=n_samples, freq='D'),
        'Ship Mode': np.random.choice(['Standard Class', 'Second Class', 'First Class', 'Same Day'], n_samples),
        'Segment': np.random.choice(['Consumer', 'Corporate', 'Home Office'], n_samples),
        'Category': category,
        'Sub-Category': np.random.choice(['Bookcases', 'Chairs', 'Labels', 'Tables', 'Storage'], n_samples),
        'Quantity': quantity,
        'Discount': discount,
        'Profit': profit,
        'Sales': sales
    }
    
    # Introduce some nulls to test imputation
    for col in ['Quantity', 'Discount']:
        mask = np.random.rand(n_samples) < 0.05
        data[col] = np.where(mask, np.nan, data[col])
        
    df = pd.DataFrame(data)
    df.to_csv(DATA_FILE, index=False)
    print(f"Mock data saved to {DATA_FILE}")
    return df

def load_data():
    if os.path.exists(DATA_FILE):
        print(f"Loading data from {DATA_FILE}...")
        df = pd.read_csv(DATA_FILE)
    else:
        df = generate_mock_data()
    return df

def preprocess_and_train():
    df = load_data()
    
    # 1. Feature Engineering
    if 'Order Date' in df.columns:
        df['Order Date'] = pd.to_datetime(df['Order Date'])
        df['Month'] = df['Order Date'].dt.month
        df['DayOfWeek'] = df['Order Date'].dt.dayofweek
        df = df.drop('Order Date', axis=1)

    # 2. Handle missing values and outliers
    # We focus on numerical columns for simplicity
    num_cols = ['Quantity', 'Discount', 'Profit', 'Month', 'DayOfWeek']
    cat_cols = ['Ship Mode', 'Segment', 'Category', 'Sub-Category']
    
    # Fill numerical nulls
    imputer = SimpleImputer(strategy='median')
    df[num_cols] = imputer.fit_transform(df[num_cols])
    
    # Label encoding for categorical columns
    label_encoders = {}
    for col in cat_cols:
        if col in df.columns:
            le = LabelEncoder()
            df[col] = df[col].astype(str)
            df[col] = le.fit_transform(df[col])
            label_encoders[col] = le
            
    # 3. Split features and target
    X = df.drop(['Sales'], axis=1)
    y = df['Sales']
    
    # 4. Train/Test Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 5. StandardScaler
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 6. Model & Hyperparameter Tuning (Random Forest)
    print("Training Random Forest with Hyperparameter tuning...")
    rf_model = RandomForestRegressor(random_state=42)
    
    param_grid = {
        'n_estimators': [50, 100],
        'max_depth': [3, 5, 10]
    }
    
    grid_search = GridSearchCV(estimator=rf_model, param_grid=param_grid, cv=3, scoring='neg_mean_squared_error', verbose=1)
    grid_search.fit(X_train_scaled, y_train)
    
    best_model = grid_search.best_estimator_
    print(f"Best Parameters: {grid_search.best_params_}")
    
    # Evaluate
    train_score = best_model.score(X_train_scaled, y_train)
    test_score = best_model.score(X_test_scaled, y_test)
    print(f"Train R2 Score: {train_score:.4f}")
    print(f"Test R2 Score: {test_score:.4f}")
    
    # 7. Save Model and preprocessors
    os.makedirs(os.path.dirname(MODEL_FILE), exist_ok=True)
    pipeline = {
        'model': best_model,
        'scaler': scaler,
        'label_encoders': label_encoders,
        'imputer': imputer,
        'features': X.columns.tolist()
    }
    
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump(pipeline, f)
    print(f"Model and pipeline saved to {MODEL_FILE}")

if __name__ == "__main__":
    preprocess_and_train()
