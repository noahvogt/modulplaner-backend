import logging

import numpy
from pdfplumber.page import Page

from .models import Area


def is_mostly_white_area(page: Page, area: Area) -> bool:
    """
    Checks wether an Area can be considered mostly white.
    Intended for detecting empty timetable cells.
    """
    img = (
        page.crop((area.x1, area.y1, area.x2, area.y2))
        .to_image(resolution=150)
        .original.convert("RGB")
    )
    arr = numpy.array(img)
    total_pixels = arr.shape[0] * arr.shape[1]

    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)

    min_rgb = numpy.minimum(numpy.minimum(r, g), b)
    max_rgb = numpy.maximum(numpy.maximum(r, g), b)
    channel_spread = max_rgb - min_rgb

    is_whitish = (min_rgb >= 250) & (channel_spread <= 25)

    total_pixels = arr.shape[0] * arr.shape[1]
    whitish_percentage = is_whitish.sum() / total_pixels
    logging.debug("whitish: %.2f%%", whitish_percentage * 100)

    return whitish_percentage > 0.9
