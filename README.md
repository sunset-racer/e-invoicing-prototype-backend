## ASP Invoicing Prototype - Backend

This is the backend API for the ASP (Accredited Service Provider) Invoicing Prototype. It simulates a tax authority compliance engine, handling invoice creation, validation,mock signing, and storage

Built with Python (Flask) and MongoDB, designed to demonstrate a robust architecture for e-invoicing compliance (ZATCA/PEPPOL style).

### Features

- RESTful API: Endpoints for creating, retrieving, updating, and deleting invoices.

- MongoDB Integration: Flexible document storage for invoice data.

- Pydantic Validation: Strict schema enforcement for financial data integrity.

- Mock API Gateway: Simulates external authority latency, validation rules, and "Clearance ID" stamping.

- Business Logic: Handles tax calculations (Subtotal, Tax, Total) and status transitions (Draft -> Signed).


### Tech Stack

Language: Python 3.11+

Framework: Flask

Database: MongoDB (Atlas Cloud)

Validation: Pydantic

Server: Gunicorn (Production), Flask Dev Server (Local)

### Setup & Installation

- Clone the repository using
`git clone`

- Set Up and Activate Virtual Environment in the following order:

- `python -m venv venv` 

- `venv\Scripts\activate` (For Windows)

- `source venv/bin/activate` (For Mac/Linux)

- Install Dependencies using
`pip install -r requirements.txt`

### Environment Configuration
Create a .env file in the root directory and add your MongoDB connection string.

Example:
`# MONGO_URI = Your URI from MongoDB Atlas`

### Run the Server
`python app.py`