import math


def collide(point, top_left, bottom_right) -> bool:
    return top_left[0] < point[0] < bottom_right[0] and top_left[1] < point[1] < bottom_right[1]


def are_intersecting(c1: tuple, c2: tuple):
    return math.sqrt((c2[0] - c1[0]) ** 2 + (c2[1] - c1[1]) ** 2) <= c1[2] + c2[2]


def get_intersecting_circles(circles):
    """
    :param circles: {"id1": [x1, y1, r1], "id2": [x2, y2, r2], ...}
    :return: intersecting ids: {id1: [id2, id3], id4: {id8}, ...}
    """

    keys = list(circles.keys())
    ret = {}
    for i in range(len(keys)):
        for i2 in range(i + 1, len(circles)):
            if are_intersecting(circles[keys[i]], circles[keys[i2]]):
                ret[keys[i]] = ret[keys[i]] + [keys[i2]] if keys[i] in ret else [keys[i2]]

    return ret
