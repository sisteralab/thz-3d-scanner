import numpy as np


def generate_colors(self, z):
    colors = np.empty((z.shape[0], z.shape[1], 4), dtype=np.ubyte)
    min_val = np.min(z)
    max_val = np.max(z)
    for i in range(z.shape[0]):
        for j in range(z.shape[1]):
            val = (z[i, j] - min_val) / (max_val - min_val)
            colors[i, j] = [0, int(255 * val), int(255 * (1 - val)), 255]


def convert_seconds(seconds: int):
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    if days > 0:
        return f"{days} day {hours:02}:{minutes:02}:{seconds:02}"
    else:
        return f"{hours:02}:{minutes:02}:{seconds:02}"


def steps_to_seconds(steps: int):
    sec_per_step = 1
    return steps * sec_per_step


def steps_to_time(steps: int):
    return convert_seconds(steps_to_seconds(steps))
