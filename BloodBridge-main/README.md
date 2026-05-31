# LifeLink - Blood Donation Management System

LifeLink is a modern, responsive web application designed to streamline blood donation management and emergency blood requests. The system connects donors, hospitals, and blood banks in real-time to ensure efficient blood resource management.

## Features

- Real-time emergency blood request system
- Donor management and scheduling
- Blood bank inventory tracking
- Modern, responsive UI with animations
- Real-time notifications
- Interactive dashboard for all user types

## Tech Stack

- Backend: Python/Flask
- Frontend: JavaScript, TailwindCSS
- Database: SQLAlchemy
- Real-time updates: Socket.IO
- Authentication: Flask-Login

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
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Initialize the database:
```bash
flask db init
flask db migrate
flask db upgrade
```

5. Run the application:
```bash
flask run
```

## Project Structure

```
lifelink/
├── app/
│   ├── __init__.py
│   ├── models/
│   ├── routes/
│   ├── static/
│   └── templates/
├── migrations/
├── tests/
├── .env
├── .env.example
├── config.py
└── run.py
```

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 