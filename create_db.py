from submit.factory import create_web_app
from submit.services import database

app = create_web_app()
app.app_context().push()
database.db.create_all()
