import os
import sys


def resource_path(*parts):
    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    if not hasattr(sys, "_MEIPASS"):
        base_path = os.path.abspath(os.path.join(base_path, os.pardir))
    return os.path.join(base_path, *parts)


def asset_path(filename):
    return resource_path("assets", filename)
