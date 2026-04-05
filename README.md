# High-Frequency RF Signal Measurement and Heat Mapping Prototype

## 📖 Overview
This project is a portable, cost-effective prototype system designed to measure the signal strength of 2.4 GHz high-frequency radio waves (such as Wi-Fi and Bluetooth) and visualize the data as an interactive heatmap. It serves as an affordable alternative to professional spectrum analyzers, helping users analyze spatial signal distribution, identify dead zones, and optimize wireless network planning in real-world environments.

## ✨ Key Features
* **Accurate Signal Measurement:** Utilizes an AD8317 logarithmic power detector combined with a 2.4 GHz Band-Pass Filter (BPF) to measure signal power (dBm).
* **Location Mapping:** Integrates a Neo-6M GPS module to bind signal strength data with precise geographical coordinates (latitude/longitude).
* **Interactive Web Heatmap:** Features a web application that renders an interactive heatmap, allowing users to zoom, pan, and check signal strength at specific coordinates.
* **Data Export:** Supports exporting mapped data for further geographical analysis.
* **Portable Design:** Built around an ESP32-S3 and Raspberry Pi 4, making it highly suitable for outdoor field surveys and walk-through data collection.

## 🛠️ Hardware Components
* **Microcontroller:** ESP32-S3-DevKitC-1 (Reads ADC from AD8317 and processes GPS data)
* **Edge Computing:** Raspberry Pi 4 Model B 4GB (Data storage and web hosting)
* **RF Power Detector:** AD8317
* **Filter:** SAW BPF Module 2.4 GHz
* **GPS Module:** Neo-6M
* **Antenna:** MX1847 600-6000MHz 8dBi
* **Display:** 0.96-inch OLED Module

## 💻 Tech Stack
* **Hardware Interfacing:** C/C++ (ESP32)
* **Backend Framework:** Python (Flask)
* **Frontend Visualization:** JavaScript, Leaflet.js (Map), and Heatmap.js
