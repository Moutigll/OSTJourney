# OSTJourney

## Description: 
OSTJourney is a website designed for streaming audio files with advanced features to ensure uninterrupted and enjoyable listening experiences.

### Key Features:
- **Dynamic rendering:** The website is fully dynamically rendered to ensure seamless listening without interruptions during navigation.
- **Audio player:** A custom audio player with basic controls and detailed metadata display.
- **User Accounts:** Users can create accounts and log in to track their activity.
- **Advanced Statistics:**  Displays insightful stats like total listening time, total songs played, activity trends over time, and peak listening hours.


---

## **Requirements**

Before getting started, ensure your system has the following installed:

- **Python** (version 3.8 or higher) 
- **Pip** (Python's package manager)
- **Virtualenv** (optional but recommended)

---

## **Installation**

### 1. **Clone the Project**
```
git clone https://github.com/Moutigll/OSTJourney.git
cd OSTJourney
```
### 2. **Create and Activate a Virtual Environment**
**Linux/MacOS**
```bash
python -m venv venv
source venv/bin/activate
```
**Windows**
```bash
python -m venv venv
venv\Scripts\activate
```
### 3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

---

## Configuration

### 1. **Set Up Environment Variables**
Create a `.env` file at the root of the project and add the following environment variables:
```
SECRET_KEY = "your_secret_key"
SQLALCHEMY_DATABASE_URI = 'sqlite:///songs.db'
SQLALCHEMY_BINDS = '{"users": "sqlite:///users.db"}'
```

### 2. **Initialize the Databases**
Run:
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```
**Add Songs and Metadata**
Put all your `.mp3` files in the `songs` folder and run the following script to populate the database with song data and extract metadata:
```
python update_db.py
```
**Note:** Depending on the number of files, this may take a few minutes to generate the database containing all the songs and their metadata, including cover art extraction.

---

## Running/Deploying the website

### Start the Flask Development Server:

```bash
flask run
```
**Expected Output:**
```
Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
```
## Deployment
For deploying the website to a production environment:

1. **Set Up a Web Server:** Configure a web server like Nginx or Apache.
2. **Use a WSGI Server:** Serve the Flask app with a WSGI server like Gunicorn:
```
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```
3. **Environment Variables:** Ensure all environment variables are properly set for the production environment.
4. **Disable Debug Mode:** Don't forget to disable Flask's debug mode by setting `app.run(debug=False)` in `app.py` before deploying.



## Contributing

All contributions are welcome!

## License

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**.

For more details, see the full license here: [https://creativecommons.org/licenses/by-nc-sa/4.0/](https://creativecommons.org/licenses/by-nc-sa/4.0/).
