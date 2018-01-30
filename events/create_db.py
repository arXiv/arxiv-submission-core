from events.factory import create_web_app
from events.services import database

app = create_web_app()
app.app_context().push()
database.db.create_all()
