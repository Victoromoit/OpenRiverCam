import flask_admin as admin

# Models for CRUD views.
from models import db
from models.camera import CameraType, Camera, CameraConfig
from models.site import Site
from models.movie import Movie

from views.camera import CameraConfigView
from views.movie import MovieView
from views.ratingcurve import RatingCurveView
from views.general import LogoutMenuLink, LoginMenuLink, UserModelView
from views.help import HelpView

admin = admin.Admin(name="OpenRiverCam", template_mode="bootstrap4", url="/portal")

# Login/logout menu links.
admin.add_link(LogoutMenuLink(name="Logout", category="", url="/logout"))
admin.add_link(LoginMenuLink(name="Login", category="", url="/login"))

# Generic CRUD views.
admin.add_view(UserModelView(Site, db, name="Sites", url="sites", category="Setup"))
admin.add_view(
    UserModelView(
        CameraType, db, name="Camera types", url="camera-types", category="Setup"
    )
)
admin.add_view(
    UserModelView(Camera, db, name="Cameras", url="cameras", category="Setup")
)
admin.add_view(
    CameraConfigView(
        CameraConfig,
        db,
        name="Camera configuration",
        url="camera-config",
        category="Setup",
    )
)
admin.add_view(MovieView(Movie, db, name="Movies", url="movies"))

# Custom user views.
admin.add_view(RatingCurveView(name="Rating curves", url="ratingcurves"))

# Publicly visible pages.
admin.add_view(HelpView(name="Help", url="help"))
