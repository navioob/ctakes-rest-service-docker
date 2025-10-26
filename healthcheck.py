#!/usr/bin/env python3
# Script to test the health of the cTAKES REST service API

import requests
import json

url = 'http://ctakes-rest-service/ctakes-web-rest/service/analyze'
params = {'pipeline': 'Default'}
headers = {'cache-control': 'no-cache'}
data = """
The patient is a 67-year-old male presenting to the emergency department with shortness of breath and a persistent cough for the past 48 hours. He reports a subjective fever and general malaise. The patient began experiencing exertional dyspnea two days ago, which has progressed to dyspnea at rest. He has a productive cough with yellow sputum. He denies chest pain or palpitations. He notes that he has had a runny nose for about a week. The patient's history is significant for hypertension diagnosed in 2010, managed with lisinopril 20mg daily. He also has a history of Type 2 Diabetes Mellitus, diagnosed in 2015, for which he takes metformin 1000mg twice a day. No known drug allergies. The patient's vitals are: BP 145/88, HR 95, Temp 100.2°F, RR 22, SpO2 90% on room air. Lungs show diminished breath sounds at the right lower lobe with crackles on auscultation. Cardiovascular is regular rate and rhythm, no murmurs. There is no peripheral edema. The patient's presentation is concerning for community-acquired pneumonia. We will initiate treatment with azithromycin 500mg IV stat and follow with 250mg PO daily. We will also order a chest X-ray and obtain a sputum culture to confirm the diagnosis and identify the causative organism. The patient will be admitted to the hospital for observation and management of his respiratory distress. We will continue his home medications as directed."""

try:
    response = requests.post(url, params=params, headers=headers, data=data)
    response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

    print("Status Code:", response.status_code)
    print("Response Body:")
    print(response.text)

except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")