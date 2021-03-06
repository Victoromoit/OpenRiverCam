import os
import enum
import pika
import json
from sqlalchemy import event, Integer, ForeignKey, String, Column, DateTime, Enum, Float, Text, inspect
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import relationship, object_session
from models.base import Base
from models.movie import Movie, MovieType
import pyproj


class CameraStatus(enum.Enum):
    CAMERA_STATUS_INACTIVE = 0
    CAMERA_STATUS_ACTIVE = 1


class Camera(Base, SerializerMixin):
    __tablename__ = "camera"
    id = Column(Integer, primary_key=True)
    camera_type_id = Column(Integer, ForeignKey("cameratype.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("site.id"), nullable=False)
    status = Column(Enum(CameraStatus), nullable=False, default=CameraStatus.CAMERA_STATUS_ACTIVE)

    site = relationship("Site", foreign_keys=[site_id])
    camera_type = relationship("CameraType", foreign_keys=[camera_type_id])

    def __str__(self):
        return "{}({}) at {}".format(self.camera_type.name, self.id, self.site.name)

    def __repr__(self):
        return "{}".format(self.__str__())


class CameraConfig(Base, SerializerMixin):
    __tablename__ = "configuration"
    id = Column(Integer, primary_key=True)
    camera_id = Column(Integer, ForeignKey("camera.id"), nullable=False)
    time_start = Column(DateTime)
    time_end = Column(DateTime)
    crs = Column(
        Integer)  # Coordinate reference system (EPSG-code) in which ground control points and camera lens position are measured
    movie_setting_resolution = Column(String)
    movie_setting_fps = Column(Float)
    gcps_src_0_x = Column(Integer)
    gcps_src_0_y = Column(Integer)
    gcps_src_1_x = Column(Integer)
    gcps_src_1_y = Column(Integer)
    gcps_src_2_x = Column(Integer)
    gcps_src_2_y = Column(Integer)
    gcps_src_3_x = Column(Integer)
    gcps_src_3_y = Column(Integer)
    gcps_dst_0_x = Column(Float)
    gcps_dst_0_y = Column(Float)
    gcps_dst_1_x = Column(Float)
    gcps_dst_1_y = Column(Float)
    gcps_dst_2_x = Column(Float)
    gcps_dst_2_y = Column(Float)
    gcps_dst_3_x = Column(Float)
    gcps_dst_3_y = Column(Float)
    gcps_z_0 = Column(Float)
    gcps_h_ref = Column(Float)
    corner_up_left_x = Column(Integer)
    corner_up_left_y = Column(Integer)
    corner_up_right_x = Column(Integer)
    corner_up_right_y = Column(Integer)
    corner_down_left_x = Column(Integer)
    corner_down_left_y = Column(Integer)
    corner_down_right_x = Column(Integer)
    corner_down_right_y = Column(Integer)
    lens_position_x = Column(Float)
    lens_position_y = Column(Float)
    lens_position_z = Column(Float)
    projection_pixel_size = Column(Float, default=0.01)
    aoi_bbox = Column(Text)
    aoi_window_size = Column(Integer)

    camera = relationship("Camera", foreign_keys=[camera_id])

    def __str__(self):
        return "{} - configuration {}".format(self.camera.__str__(), self.id)

    def __repr__(self):
        return "{}".format(self.__str__())

    def get_task_json(self):
        """
        Get dict with main properties of camera config for the JSON content towards the processing node.

        :return: dict
        """
        # convert any coordinates to site's EPSG code
        crs_camera_config = pyproj.CRS.from_epsg(
            self.crs if self.crs is not None else 4326)  # assume WGS84 latlon if not provided
        crs_site = pyproj.CRS.from_epsg(self.camera.site.position_crs)
        transform = pyproj.Transformer.from_crs(crs_camera_config, crs_site, always_xy=True)
        dst = [
            list(transform.transform(float(self.gcps_dst_0_x),
                                     float(self.gcps_dst_0_y))) if self.gcps_dst_0_x is not None else [None, None],
            list(transform.transform(float(self.gcps_dst_1_x),
                                     float(self.gcps_dst_1_y))) if self.gcps_dst_1_x is not None else [None, None],
            list(transform.transform(float(self.gcps_dst_2_x),
                                     float(self.gcps_dst_2_y))) if self.gcps_dst_2_x is not None else [None, None],
            list(transform.transform(float(self.gcps_dst_3_x),
                                     float(self.gcps_dst_3_y))) if self.gcps_dst_3_x is not None else [None, None],

        ]
        if self.lens_position_x is not None:
            lensPosition = list(transform.transform(float(self.lens_position_x), float(self.lens_position_y))) + [
                float(self.lens_position_z)]
        else:
            lensPosition = [None, None, None]
        return {
            "id": self.id,
            "camera_type": self.camera.camera_type.get_task_json(),
            "site": self.camera.site.get_task_json(),
            "time_start": str(self.time_start.isoformat()),
            "time_end": str(self.time_end.isoformat()) if self.time_end else None,
            "gcps": {
                "src": [[self.gcps_src_0_x, self.gcps_src_0_y], [self.gcps_src_1_x, self.gcps_src_1_y],
                        [self.gcps_src_2_x, self.gcps_src_2_y], [self.gcps_src_3_x, self.gcps_src_3_y]],
                "dst": dst,
                "z_0": float(self.gcps_z_0) if self.gcps_z_0 is not None else None,
                "h_ref": float(self.gcps_h_ref) if self.gcps_h_ref is not None else None
            },
            "corners": {
                "up_left": [self.corner_up_left_x, self.corner_up_left_y],
                "down_left": [self.corner_down_left_x, self.corner_down_left_y],
                "down_right": [self.corner_down_right_x, self.corner_down_right_y],
                "up_right": [self.corner_up_right_x, self.corner_up_right_y],
            },
            "resolution": float(self.projection_pixel_size) if self.projection_pixel_size else None,
            "lensPosition": lensPosition,
            "aoi": {"bbox": json.loads(self.aoi_bbox) if self.aoi_bbox else {}},
            "aoi_window_size": self.aoi_window_size,
        }


@event.listens_for(CameraConfig, "before_update")
def before_update(mapper, connection, target):
    state = inspect(target)
    field_change = False
    step_2_fields = ["crs",
                     "gcps_src_0_x",
                     "gcps_src_0_y",
                     "gcps_src_1_x",
                     "gcps_src_1_y",
                     "gcps_src_2_x",
                     "gcps_src_2_y",
                     "gcps_src_3_x",
                     "gcps_src_3_y",
                     "gcps_dst_0_x",
                     "gcps_dst_0_y",
                     "gcps_dst_1_x",
                     "gcps_dst_1_y",
                     "gcps_dst_2_x",
                     "gcps_dst_2_y",
                     "gcps_dst_3_x",
                     "gcps_dst_3_y",
                     "gcps_z_0",
                     "gcps_h_ref",
                     "corner_up_left_x",
                     "corner_up_left_y",
                     "corner_up_right_x",
                     "corner_up_right_y",
                     "corner_down_left_x",
                     "corner_down_left_y",
                     "corner_down_right_x",
                     "corner_down_right_y",
                     "lens_position_x",
                     "lens_position_y",
                     "lens_position_z",
                     "projection_pixel_size"]
    for step_2_field in step_2_fields:
        hist = state.attrs.get(step_2_field).load_history()
        if hist.has_changes() and hist.deleted[0]:
            if float(hist.deleted[0]) == float(hist.added[0]):
                field_change = False
            else:
                field_change = True
                break

    if field_change:
        target.aoi_bbox = None


@event.listens_for(CameraConfig, "after_update")
def receive_after_update(mapper, connection, target):
    """
    Send task to processing node if the camera config has the gcps but not the AOI Bbox.

    :param mapper:
    :param connection:
    :param target:
    """
    if not target.aoi_bbox and target.gcps_src_0_x:
        queue_task("run_camera_config", target)


@event.listens_for(CameraConfig, 'before_delete')
def receive_after_update(mapper, connection, target):
    """
    Remove the corresponding config movies which were used during camera config before attempting to delete the camera config.

    :param mapper:
    :param connection:
    :param target:
    """
    Movie.query.filter(Movie.config_id == target.id).filter(Movie.type == MovieType.MOVIE_TYPE_CONFIG).delete()


def queue_task(type, camera_config):
    """
    Send a task to the processing node.

    :param type: task type
    :param camera_config: camera config object instance
    """
    movie = Movie.query.filter(Movie.config_id == camera_config.id).filter(
        Movie.type == MovieType.MOVIE_TYPE_CONFIG).order_by(Movie.id.desc()).first()
    if movie:
        movie_json = movie.get_task_json()
        movie_json["h_a"] = movie_json["camera_config"]["gcps"]["h_ref"]

        connection = pika.BlockingConnection(
            pika.URLParameters(os.getenv("AMQP_CONNECTION_STRING"))
        )
        channel = connection.channel()
        channel.queue_declare(queue="processing")
        channel.basic_publish(
            exchange="",
            routing_key="processing",
            body=json.dumps({"type": type, "kwargs": {"movie": movie_json}})
        )
        connection.close()


class CameraType(Base, SerializerMixin):
    __tablename__ = "cameratype"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    name = Column(String, nullable=False)
    lens_k1 = Column(Float, nullable=False)
    lens_c = Column(Float, nullable=False)
    lens_f = Column(Float, nullable=False)

    def __str__(self):
        return "{}".format(self.name)

    def __repr__(self):
        return "{}: {}".format(self.id, self.__str__())

    def get_task_json(self):
        """
        Get dict with main properties of camera type for the JSON content towards the processing node.

        :return: dict
        """
        return {
            "name": self.name,
            "lensParameters": {
                "k1": float(self.lens_k1) if self.lens_k1 is not None else None,
                "c": float(self.lens_c) if self.lens_c is not None else None,
                "f": float(self.lens_f) if self.lens_f is not None else None
            }
        }
