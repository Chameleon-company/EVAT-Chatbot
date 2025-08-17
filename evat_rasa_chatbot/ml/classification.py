import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from xgboost import XGBRegressor, XGBClassifier
from sklearn.metrics import mean_absolute_error, mean_squared_error, accuracy_score, classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

# Load Dataset
df = pd.read_csv("../data/raw/ml_ev_charging_dataset.csv")

# Drop missing or null values
df.dropna(inplace=True)

# Encode categorical variable (Station_Name)
le = LabelEncoder()
df['Station_Encoded'] = le.fit_transform(df['Station_Name'])

################# REGRESSION MODEL#######################

# derive haversine distance as a feature


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    a = np.sin(delta_phi / 2) ** 2 + \
        np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
    return R * (2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a)))


df['Geo_Distance'] = haversine(df['Latitude'], df['Longitude'],
                               df['Suburb_Location_Lat'], df['Suburb_Location_Lon'])

# Predict ETA_min using coordinates and encoded station
features_reg = ['Longitude', 'Latitude', 'Suburb_Location_Lat',
                'Suburb_Location_Lon', 'Geo_Distance', 'Station_Encoded']
X_reg = df[features_reg]
y_reg = df['ETA_min']

# Train-test split
X_train_reg, X_test_reg, y_train_reg, y_test_reg = train_test_split(
    X_reg, y_reg, test_size=0.2, random_state=42)

# Model 1: Linear Regression
lr = LinearRegression()
lr.fit(X_train_reg, y_train_reg)
y_pred_lr = lr.predict(X_test_reg)

# Model 2: Random Forest Regressor
rf = RandomForestRegressor(random_state=42)
rf.fit(X_train_reg, y_train_reg)
y_pred_rf = rf.predict(X_test_reg)

# Model 3: XGBoost Regressor
xgb = XGBRegressor(random_state=42)
xgb.fit(X_train_reg, y_train_reg)
y_pred_xgb = xgb.predict(X_test_reg)

# Evaluation (Regression)


def regression_results(y_true, y_pred, model_name):
    print(f"\n{model_name} Regression Results:")
    print("MAE:", mean_absolute_error(y_true, y_pred))
    print("RMSE:", np.sqrt(mean_squared_error(y_true, y_pred)))


regression_results(y_test_reg, y_pred_lr, "Linear")
regression_results(y_test_reg, y_pred_rf, "Random Forest")
regression_results(y_test_reg, y_pred_xgb, "XGBoost")

##### CLASSIFICATION MODEL###############ETA PREDICTION###############
# Create classification target: "Short ETA" if ETA <= 5 min
df['ETA_Class'] = df['ETA_min'].apply(lambda x: "Short" if x <= 5 else "Long")

features_clf = features_reg
X_clf = df[features_clf]
y_clf = df['ETA_Class']

X_train_clf, X_test_clf, y_train_clf, y_test_clf = train_test_split(
    X_clf, y_clf, test_size=0.2, random_state=42)

# Encode classification labels
le_eta = LabelEncoder()
y_train_clf_enc = le_eta.fit_transform(y_train_clf)
y_test_clf_enc = le_eta.transform(y_test_clf)

# Model 1: Logistic Regression
log_clf = LogisticRegression(max_iter=1000)
log_clf.fit(X_train_clf, y_train_clf_enc)
y_pred_log = log_clf.predict(X_test_clf)

# Model 2: Random Forest Classifier
rf_clf = RandomForestClassifier(random_state=42)
rf_clf.fit(X_train_clf, y_train_clf_enc)
y_pred_rf_clf = rf_clf.predict(X_test_clf)

# Model 3: XGBoost Classifier
xgb_clf = XGBClassifier(random_state=42)
xgb_clf.fit(X_train_clf, y_train_clf_enc)
y_pred_xgb_clf = xgb_clf.predict(X_test_clf)

# Evaluation (Classification)


def classification_results(y_true, y_pred, model_name):
    print(f"\n{model_name} Classification Results:")
    print("Accuracy:", accuracy_score(y_true, y_pred))
    print(classification_report(y_true, y_pred))
    cm = confusion_matrix(y_true, y_pred)
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
    plt.title(f"{model_name} Confusion Matrix")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.show()


classification_results(y_test_clf_enc, y_pred_log, "Logistic")
classification_results(y_test_clf_enc, y_pred_rf_clf, "Random Forest")
classification_results(y_test_clf_enc, y_pred_xgb_clf, "XGBoost")

##### CLASSIFICATION MODEL###############STATION PREDICTION###############

# Target: Station_Name (assuming the target variable is the Station_Name column)
# Station_Name is the target for multi-class classification
y_clf_station = df['Station_Name']

# Features remain the same (coordinates, ETA, etc.)
X_clf_station = df[features_reg]

# Train-Test Split
X_train_clf, X_test_clf, y_train_clf, y_test_clf = train_test_split(
    X_clf_station, y_clf_station, test_size=0.2, random_state=42)

# Encode station names using LabelEncoder (since it's a multi-class classification task)
le_station = LabelEncoder()
y_train_clf_enc = le_station.fit_transform(y_train_clf)
y_test_clf_enc = le_station.transform(y_test_clf)

# Model 1: Logistic Regression
log_clf_station = LogisticRegression(
    max_iter=1000, multi_class='ovr', solver='lbfgs')  # Multi-class handling
log_clf_station.fit(X_train_clf, y_train_clf_enc)
y_pred_log_station = log_clf.predict(X_test_clf)

# Model 2: Random Forest Classifier
rf_clf_station = RandomForestClassifier(random_state=42)
rf_clf_station.fit(X_train_clf, y_train_clf_enc)
y_pred_rf_clf_station = rf_clf_station.predict(X_test_clf)

# Model 3: XGBoost Classifier
xgb_clf_station = XGBClassifier(random_state=42)
xgb_clf_station.fit(X_train_clf, y_train_clf_enc)
y_pred_xgb_clf_station = xgb_clf_station.predict(X_test_clf)

# Evaluation (Multi-class Classification)


def classification_results_multi_class(y_true, y_pred, model_name):
    print(f"\n{model_name} Classification Results (Station Prediction):")
    print("Accuracy:", accuracy_score(y_true, y_pred))

    # Get unique labels from y_true and y_pred (it should be consistent)
    unique_labels = np.unique(np.concatenate([y_true, y_pred]))

    # Adjusting classification report with correct label classes
    print(classification_report(y_true, y_pred, labels=unique_labels,
                                target_names=[f"Station_{i}" for i in unique_labels]))

    # Confusion Matrix
    cm = confusion_matrix(y_true, y_pred, labels=unique_labels)
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
    plt.title(f"{model_name} Confusion Matrix (Station Prediction)")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.show()


classification_results_multi_class(
    y_test_clf_enc, y_pred_log_station, "Logistic")
classification_results_multi_class(
    y_test_clf_enc, y_pred_rf_clf_station, "Random Forest")
classification_results_multi_class(
    y_test_clf_enc, y_pred_xgb_clf_station, "XGBoost")
