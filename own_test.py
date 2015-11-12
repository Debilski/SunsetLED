#!/usr/bin/env python3

from __future__ import print_function

import datetime
import json
import math
import optparse
import random
import sys
import time

import numpy as np
import pysolar
import pytz
try:
    pass#from skimage import io
except ImportError:
    pass

from pixeltools import fastopc as opc
from pixeltools import color_utils
from sunsetled.effect import Effect


def sample_int(imgarr, x, y):
    return imgarr[x % imgarr.shape[0], y % imgarr.shape[1]]

def sample(imgarr, fx, fy):
    ix = int(fx)
    iy = int(fy)

    if not 0 <= fx <= imgarr.shape[0]:
        return None
    if not 0 <= fy <= imgarr.shape[1]:
        return None

    print("i:", ix, iy)

    # Sample four points
    aa = sample_int(imgarr, ix,     iy)
    ba = sample_int(imgarr, ix + 1, iy)
    ab = sample_int(imgarr, ix,     iy + 1)
    bb = sample_int(imgarr, ix + 1, iy + 1)

    # X interpolation
    ca = aa + (ba - aa) * (fx - ix)
    cb = ab + (bb - ab) * (fx - ix)

    # Y interpolation
    return ca + (cb - ca) * (fy - iy)

NUM_COLS = 3 # rgb

def read_image(file):
    try:
        ar = io.imread(file).astype(np.float64)
        np.save(file + ".npy", ar)
    except NameError:
        print("No scikits-image. Try to load from saved file.")
        ar = np.load(file + ".npy")
    while ar.shape[2] > NUM_COLS:
        ar = np.delete(ar, NUM_COLS, axis=2)
    ar /= 255.
    return ar

#-------------------------------------------------------------------------------
# command line

parser = optparse.OptionParser()
parser.add_option('-l', '--layout', dest='layout',
                    action='store', type='string',
                    help='layout file')
parser.add_option('-s', '--server', dest='server', default='127.0.0.1:7890',
                    action='store', type='string',
                    help='ip and port of server')
parser.add_option('-f', '--fps', dest='fps', default=20,
                    action='store', type='int',
                    help='frames per second')

options, args = parser.parse_args()

if not options.layout:
    parser.print_help()
    print()
    print('ERROR: you must specify a layout file using --layout')
    print()
    sys.exit(1)


#-------------------------------------------------------------------------------
# parse layout file

print()
print('    parsing layout file')
print()

coordinates = np.array([item['point']
    for item in json.load(open(options.layout))
    if 'point' in item])

#-------------------------------------------------------------------------------
# connect to server

client = opc.FastOPC(options.server)
#if client.can_connect():
#    print('    connected to %s' % options.server)
#else:
    # can't connect, but keep running in case the server appears later
#    print('    WARNING: could not connect to %s' % options.server)
print()


#-------------------------------------------------------------------------------
# color function

def pixel_color(t, coord, ii, n_pixels, random_values):
    """Compute the color of a given pixel.

    t: time in seconds since the program started.
    ii: which pixel this is, starting at 0
    coord: the (x, y, z) position of the pixel as a tuple
    n_pixels: the total number of pixels
    random_values: a list containing a constant random value for each pixel

    Returns an (r, g, b) tuple in the range 0-255

    """
    # make moving stripes for x, y, and z
    x, y, z = coord
    y += color_utils.cos(x + 0.2*z, offset=0, period=1, minn=0, maxx=0.6)
    z += color_utils.cos(x, offset=0, period=1, minn=0, maxx=0.3)
    x += color_utils.cos(y + z, offset=0, period=1.5, minn=0, maxx=0.2)

    # rotate
    x, y, z = y, z, x

    # shift some of the pixels to a new xyz location
    if ii % 7 == 0:
        x += ((ii*123)%5) / n_pixels * 32.12
        y += ((ii*137)%5) / n_pixels * 22.23
        z += ((ii*147)%7) / n_pixels * 44.34

    # make x, y, z -> r, g, b sine waves
    r = color_utils.cos(x, offset=t / 4, period=2, minn=0, maxx=1)
    g = color_utils.cos(y, offset=t / 4, period=2, minn=0, maxx=1)
    b = color_utils.cos(z, offset=t / 4, period=2, minn=0, maxx=1)
    r, g, b = color_utils.contrast((r, g, b), 0.5, 1.5)

    # a moving wave across the pixels, usually dark.
    # lines up with the wave of twinkles
    fade = color_utils.cos(t - ii/n_pixels, offset=0, period=7, minn=0, maxx=1) ** 20
    r *= fade
    g *= fade
    b *= fade

#     # stretched vertical smears
#     v = color_utils.cos(ii / n_pixels, offset=t*0.1, period = 0.07, minn=0, maxx=1) ** 5 * 0.3
#     r += v
#     g += v
#     b += v

    # twinkle occasional LEDs
    twinkle_speed = 0.07
    twinkle_density = 0.1
    twinkle = (random_values[ii]*7 + time.time()*twinkle_speed) % 1
    twinkle = abs(twinkle*2 - 1)
    twinkle = color_utils.remap(twinkle, 0, 1, -1/twinkle_density, 1.1)
    twinkle = color_utils.clamp(twinkle, -0.5, 1.1)
    twinkle **= 5
    twinkle *= color_utils.cos(t - ii/n_pixels, offset=0, period=7, minn=0, maxx=1) ** 20
    twinkle = color_utils.clamp(twinkle, -0.3, 1)
    r += twinkle
    g += twinkle
    b += twinkle

    # apply gamma curve
    # only do this on live leds, not in the simulator
    #r, g, b = color_utils.gamma((r, g, b), 2.2)

    return (r*256, g*256, b*256)

#-------------------------------------------------------------------------------
# send pixels

print('    sending pixels forever (control-c to exit)...')
print()

tz = pytz.timezone('Pacific/Chatham')
# tz = pytz.timezone('Europe/Berlin')



#n_pixels = len(coordinates)
#random_values = [random.random() for ii in range(n_pixels)]


class ImageAnimation(Effect):
    def __init__(self, coordinates, time, image, path):
        self.coordinates = coordinates
        self.start_time = time
        self.image = image
        self.path = path

class ImageTrafo:
    def __init__(self):
        self.matrix = np.eye(4)

    def rotate(self, axis, theta):
        self.matrix = np.dot(self.matrix, self.rotation_matrix(axis, theta))
        return self

    def translate(self, translation):
        self.matrix = np.dot(self.matrix, self.translation_matrix(translation))
        return self

    def scale(self, scale):
        self.matrix *= scale
        return self

    @staticmethod
    def translation_matrix(translation):
        return np.array([[1, 0, 0, translation[0]],
                         [0, 1, 0, translation[1]],
                         [0, 0, 1, translation[2]],
                         [0, 0, 0, 1]], dtype=np.float64)

    @staticmethod
    def rotation_matrix(axis, theta):
        """
        Return the rotation matrix associated with counterclockwise rotation about
        the given axis by theta radians.
        """
        axis = np.asarray(axis)
        theta = np.asarray(theta)
        axis = axis/math.sqrt(np.dot(axis, axis))
        a = math.cos(theta/2)
        b, c, d = -axis*math.sin(theta/2)
        aa, bb, cc, dd = a*a, b*b, c*c, d*d
        bc, ad, ac, ab, bd, cd = b*c, a*d, a*c, a*b, b*d, c*d
        return np.array([[aa+bb-cc-dd, 2*(bc+ad), 2*(bd-ac), 0],
                         [2*(bc-ad), aa+cc-bb-dd, 2*(cd+ab), 0],
                         [2*(bd+ac), 2*(cd-ab), aa+dd-bb-cc, 0],
                         [0, 0, 0, 1]], dtype=np.float64)

    def apply(self, vec):
        n = np.dot(self.matrix, np.append(vec, 1))
#        print(self.matrix)
        return n[0:3]


def path(time_delta):
    return ImageTrafo(pos=(0,0,0), scale=1, rot=0)

#image_anim = ImageAnimation(None, None, dot, path=path)



class Sun(Effect):
    def __init__(self, time, image, rot):
        self.start_time = time
        self.image = image
        self.rot = rot
        self.tick = 0

    def begin_frame(self):
        maxsize = np.max(self.image.shape)
        self.tick += random.randint(0, 10) / 100.
        self.M0 = ImageTrafo().rotate([0, 2, 0], self.time).scale(maxsize).translate([math.sin(self.time)*1, 0.0, math.sin(self.time+self.tick)*1]) # .rotate([0, 2, 0], time.time() + self.rot)# .translate(np.array([1, 1, 1]) * math.sin(time.time()) * 0.2)

    def shader(self, color, pixel_info):
        pos = pixel_info

        x, _, y = self.M0.apply(pos)

        import pdb
        #pdb.set_trace()

        try:
            r, g, b = sample(self.image, x, y)
        except TypeError:
            return color

        return [r, g, b]

class Flash(Effect):
    def __init__(self, time):
        self.start_time = time

    def shader(self, color, pixel_info):
        if random.randint(0, 200) == 0:
            return [1., 1., 1.]
        else:
            return color


start_time = time.time()

dot = read_image("line.png")
reddot = read_image("redline.png")

sun = Sun(start_time, dot, 0)
redmoon = Sun(start_time, reddot, 10)
flash = Flash(start_time)

effects = [
    sun,
    redmoon,
    flash
]


def load_weather(timezone):
    with open("weather.json") as f:
        weather = json.load(f)
        data = weather["query"]["results"]["channel"]
        astronomy = data["astronomy"]
        wind = data["wind"]["speed"]

        lat = float(data["item"]["lat"])
        long = float(data["item"]["long"])

        now = datetime.datetime.now(tz=timezone)
        sr, ss = pysolar.util.get_sunrise_sunset(lat, long, now)
        print(sr)
        print(ss)

        return {
            "sun": astronomy,
            "wind": wind,
            "temperature": data["item"]["condition"]["temp"],
            "lat": lat,
            "long": long,
            "sunrise": sr,
            "sunset": ss,
        }


min_time_delta = 1. / 30

current_delay = 0
filtered_time_delta = 0
time_delta = 0
filter_gain = 0.05

#while True:
for _ in range(500):
    now = datetime.datetime.now(tz=tz)
    print(now)
    t = time.time() - start_time
    print(t)

    print(load_weather(tz))
#    break

    # reset the pixels
    pixels = np.zeros((coordinates.shape[0], NUM_COLS))

    for effect in effects:
        effect.render(pixels, coordinates, t)

    client.put_pixels(0, pixels)

    filtered_time_delta += (time_delta - filtered_time_delta) * filter_gain

    current_delay += (min_time_delta - time_delta) * filter_gain

    filteredTimeDelta = max(filtered_time_delta, current_delay)

    time.sleep(current_delay)
#    time.sleep(1 / options.fps)
