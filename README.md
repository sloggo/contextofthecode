# Device Metrics Collection System

A Python-based system for collecting, aggregating, and reporting device metrics using Flask and SQLAlchemy with SQLite database.

## Architecture Components

1. **Collector Agent**
   - PC Collector: Collects metrics from Device 1
   - 3rd Party Collector: Collects metrics from Device 2
   - Uploader Queue: Manages data upload queue

2. **Web Application**
   - Flask-based REST APIs
   - Flask-SQLAlchemy ORM with SQLite
   - Aggregator and Reporting endpoints

## Setup Instructions

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
   - Copy `.env.example` to `.env`
   - The default SQLite database will be created at `instance/metrics.db`
   - Update other settings as needed

4. Start the Flask application:
```bash
python -m src.web_app.main
```

5. Start the collector agent:
```bash
python -m src.collector.main
```

## Project Structure

```
src/
├── collector/
│   ├── pc_collector.py
│   ├── third_party_collector.py
│   └── uploader_queue.py
├── web_app/
│   ├── routes/
│   │   ├── aggregator.py
│   │   └── reporting.py
│   └── main.py
├── database/
│   ├── models.py
│   └── database.py
└── utils/
    └── config.py
```

## Database

The application uses SQLite as the database backend. The database file will be created automatically at `instance/metrics.db` when you first run the application. This makes it easy to get started without needing to set up a separate database server.

## API Endpoints

### Aggregator API
- POST `/api/v1/aggregator/metrics/`: Submit a single metric
- POST `/api/v1/aggregator/metrics/batch/`: Submit multiple metrics

### Reporting API
- GET `/api/v1/reports/metrics/<device_name>`: Get metrics for a specific device
  - Query parameters: `start_time`, `end_time`
- GET `/api/v1/reports/summary`: Get summary of all metrics
  - Query parameter: `time_range` (hours, default: 24)

## Testing

Run tests using pytest:
```bash
pytest tests/
``` 