import os
import enum
import pika
import json
from sqlalchemy import event, Integer, ForeignKey, String, Column, DateTime, Enum, Float, Text
from sqlalchemy_serializer import SerializerMixin
from sqlalchemy.orm import relationship
from models.base import Base
from models.movie import Movie


class CameraStatus(enum.Enum):
    CAMERA_STATUS_INACTIVE = 0
    CAMERA_STATUS_ACTIVE = 1


class Camera(Base, SerializerMixin):
    __tablename__ = "camera"
    id = Column(Integer, primary_key=True)
    camera_type_id = Column(Integer, ForeignKey("cameratype.id"))
    site_id = Column(Integer, ForeignKey("site.id"))
    status = Column(Enum(CameraStatus))

    site = relationship("Site")
    camera_type = relationship("CameraType")

    def __str__(self):
        return "{}({}) at {}".format(self.camera_type.name, self.id, self.site.name)

    def __repr__(self):
        return "{}".format(self.__str__())


class CameraConfig(Base, SerializerMixin):
    __tablename__ = "configuration"
    id = Column(Integer, primary_key=True)
    camera_id = Column(Integer, ForeignKey("camera.id"))
    time_start = Column(DateTime)
    time_end = Column(DateTime)
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
    projection_pixel_size = Column(Float)
    aoi_bbox = Column(Text)
    aoi_window_size = Column(Integer)

    camera = relationship("Camera")

    def __str__(self):
        return "{} - configuration {}".format(self.camera.__str__(), self.id)

    def __repr__(self):
        return "{}".format(self.__str__())

    def get_task_json(self):
        return {
            "id": self.id,
            "camera_type": self.camera.camera_type.get_task_json(),
            "site": self.camera.site.get_task_json(),
            "time_start": str(self.time_start.isoformat()),
            "time_end": str(self.time_end.isoformat()),
            "gcps": {
                "src": [ [self.gcps_src_0_x, self.gcps_src_0_y], [self.gcps_src_1_x, self.gcps_src_1_y ], [self.gcps_src_2_x, self.gcps_src_2_y ], [self.gcps_src_3_x, self.gcps_src_3_y ] ],
                "dst": [
                    [float(self.gcps_dst_0_x) if self.gcps_dst_0_x is not None else None, float(self.gcps_dst_0_y) if self.gcps_dst_0_y is not None else None],
                    [float(self.gcps_dst_1_x) if self.gcps_dst_1_x is not None else None, float(self.gcps_dst_1_y) if self.gcps_dst_1_y is not None else None],
                    [float(self.gcps_dst_2_x) if self.gcps_dst_2_x is not None else None, float(self.gcps_dst_2_y) if self.gcps_dst_2_y is not None else None],
                    [float(self.gcps_dst_3_x) if self.gcps_dst_3_x is not None else None, float(self.gcps_dst_3_y) if self.gcps_dst_3_y is not None else None]
                ],
                "z_0": float(self.gcps_z_0) if self.gcps_z_0 is not None else None,
                "h_ref": float(self.gcps_h_ref) if self.gcps_h_ref is not None else None
            },
            "corners": {
                "up_left": [ self.corner_up_left_x, self.corner_up_left_y ],
                "down_left": [ self.corner_down_left_x, self.corner_down_left_y ],
                "down_right": [ self.corner_down_right_x, self.corner_down_right_y ],
                "up_right": [ self.corner_up_right_x, self.corner_up_right_y ],
            },
            "resolution": float(self.projection_pixel_size) if self.projection_pixel_size else None,
            "lensPosition": [
                float(self.lens_position_x) if self.lens_position_x is not None else None,
                float(self.lens_position_y) if self.lens_position_y is not None else None,
                float(self.lens_position_z) if self.lens_position_z is not None else None
            ],
            "aoi": { "bbox": json.loads(self.aoi_bbox) if self.aoi_bbox else {} },
            "aoi_window_size": self.aoi_window_size,
        }

@event.listens_for(CameraConfig, "after_update")
def receive_after_update(mapper, connection, target):
    if not target.aoi_bbox and target.gcps_src_0_x:
        queue_task("run_camera_config", target)

def queue_task(type, camera_config):
    movie = Movie.query.filter(Movie.config_id == camera_config.id).order_by(Movie.id.desc()).first()
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
            body=json.dumps({"type": type, "kwargs": {"movie": movie_json }})
        )
        connection.close()


class CameraType(Base, SerializerMixin):
    __tablename__ = "cameratype"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    lens_k1 = Column(Float)
    lens_c = Column(Float)
    lens_f = Column(Float)

    def __str__(self):
        return "{}".format(self.name)

    def __repr__(self):
        return "{}: {}".format(self.id, self.__str__())

    def get_task_json(self):
        return {
            "name": self.name,
            "lensParameters": {
                "k1": float(self.lens_k1) if self.lens_k1 is not None else None,
                "c": float(self.lens_c) if self.lens_c is not None else None,
                "f": float(self.lens_f) if self.lens_f is not None else None
            }
        }
